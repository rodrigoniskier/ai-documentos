from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .asaas_client import AsaasError
from .models import (
    BillingCheckout,
    BillingCustomer,
    BillingEvent,
    BillingSubscription,
    Plan,
    Subscription,
)
from .services import grant_credits


SUCCESS_EVENTS = {
    "CHECKOUT_PAID",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
}
PAST_DUE_EVENTS = {
    "PAYMENT_OVERDUE",
    "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
}
CANCEL_EVENTS = {
    "CHECKOUT_CANCELED",
    "CHECKOUT_EXPIRED",
    "PAYMENT_DELETED",
}
REFUND_EVENTS = {
    "PAYMENT_REFUNDED",
    "PAYMENT_PARTIALLY_REFUNDED",
}


def _safe_event_snapshot(payload: dict) -> dict:
    snapshot = {
        "id": payload.get("id", ""),
        "event": payload.get("event", ""),
        "dateCreated": payload.get("dateCreated", ""),
    }
    for key in ("checkout", "payment"):
        value = payload.get(key)
        if not isinstance(value, dict):
            continue
        snapshot[key] = {
            field: value.get(field)
            for field in (
                "id",
                "status",
                "externalReference",
                "subscription",
                "customer",
                "checkoutSession",
                "value",
                "netValue",
                "billingType",
                "dueDate",
                "paymentDate",
                "confirmedDate",
            )
            if value.get(field) is not None
        }
    return snapshot


def _subscription_id(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("id") or value.get("subscription") or "")
    return ""


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _find_checkout(checkout_data: dict, payment_data: dict):
    external_reference = str(
        payment_data.get("externalReference")
        or checkout_data.get("externalReference")
        or ""
    )
    checkout_id = str(
        checkout_data.get("id")
        or payment_data.get("checkoutSession")
        or payment_data.get("checkout")
        or ""
    )
    queryset = BillingCheckout.objects.select_related("user", "plan")
    checkout = None
    if external_reference:
        checkout = queryset.filter(external_reference=external_reference).first()
    if not checkout and checkout_id:
        checkout = queryset.filter(provider_checkout_id=checkout_id).first()
    return checkout, external_reference, checkout_id


def _get_or_update_customer(user, provider_customer_id: str):
    if not user:
        return None
    customer, _ = BillingCustomer.objects.get_or_create(
        user=user,
        defaults={"external_reference": f"rndoc-user-{user.pk}"},
    )
    if provider_customer_id and customer.provider_customer_id != provider_customer_id:
        conflict = BillingCustomer.objects.filter(
            provider_customer_id=provider_customer_id
        ).exclude(pk=customer.pk)
        if not conflict.exists():
            customer.provider_customer_id = provider_customer_id
            customer.save(update_fields=["provider_customer_id", "updated_at"])
    return customer


def _period_key(payment_data: dict) -> str:
    due = _parse_date(
        payment_data.get("dueDate")
        or payment_data.get("paymentDate")
        or payment_data.get("confirmedDate")
    )
    due = due or timezone.localdate()
    return due.strftime("%Y-%m")


@transaction.atomic
def _activate_entitlement(
    *,
    user,
    plan,
    checkout=None,
    payment_data=None,
    checkout_data=None,
):
    payment_data = payment_data or {}
    checkout_data = checkout_data or {}
    today = timezone.localdate()
    payment_id = str(payment_data.get("id") or "")
    provider_subscription_id = _subscription_id(
        payment_data.get("subscription") or checkout_data.get("subscription")
    )
    checkout_subscription = checkout_data.get("subscription")
    checkout_next_due = (
        checkout_subscription.get("nextDueDate")
        if isinstance(checkout_subscription, dict)
        else None
    )
    next_due_date = _parse_date(payment_data.get("dueDate") or checkout_next_due)

    local_subscription, _ = Subscription.objects.select_for_update().get_or_create(
        user=user,
        defaults={"plan": plan, "status": "active"},
    )
    local_subscription.plan = plan
    local_subscription.status = "active"
    local_subscription.save(update_fields=["plan", "status"])

    billing_subscription, _ = (
        BillingSubscription.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                "plan": plan,
                "external_reference": (
                    checkout.external_reference
                    if checkout
                    else f"rndoc-subscription-{user.pk}"
                ),
            },
        )
    )
    billing_subscription.plan = plan
    if checkout:
        billing_subscription.external_reference = checkout.external_reference
    billing_subscription.status = "active"
    billing_subscription.activated_at = (
        billing_subscription.activated_at or timezone.now()
    )
    billing_subscription.cancel_at_period_end = False
    billing_subscription.cancelled_at = None
    billing_subscription.current_period_start = today
    billing_subscription.current_period_end = today + timedelta(days=30)
    billing_subscription.next_due_date = next_due_date
    if payment_id:
        billing_subscription.last_payment_id = payment_id
    if provider_subscription_id:
        duplicate = BillingSubscription.objects.filter(
            provider_subscription_id=provider_subscription_id
        ).exclude(pk=billing_subscription.pk)
        if not duplicate.exists():
            billing_subscription.provider_subscription_id = provider_subscription_id
    billing_subscription.save()

    if checkout:
        checkout.status = "paid"
        checkout.provider_status = str(checkout_data.get("status") or "PAID")
        checkout.paid_at = checkout.paid_at or timezone.now()
        checkout.save(
            update_fields=["status", "provider_status", "paid_at", "updated_at"]
        )

    period_key = _period_key(payment_data)
    grant_credits(
        user=user,
        amount=plan.monthly_credits,
        idempotency_key=f"billing-period:{user.pk}:{plan.code}:{period_key}",
        reason=f"Créditos mensais do plano {plan.name}",
    )
    return billing_subscription


@transaction.atomic
def _downgrade_after_refund(user):
    free_plan = Plan.objects.get(code="FREE")
    local_subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": free_plan, "status": "active"},
    )
    local_subscription.plan = free_plan
    local_subscription.status = "active"
    local_subscription.save(update_fields=["plan", "status"])


@transaction.atomic
def process_asaas_event(payload: dict):
    provider_event_id = str(payload.get("id") or "").strip()
    event_type = str(payload.get("event") or "").strip()
    if not provider_event_id or not event_type:
        raise AsaasError("Evento do Asaas sem id ou tipo.")

    event, created = BillingEvent.objects.get_or_create(
        provider_event_id=provider_event_id,
        defaults={
            "event_type": event_type,
            "payload": _safe_event_snapshot(payload),
        },
    )
    if not created:
        event = BillingEvent.objects.select_for_update().get(pk=event.pk)
        if event.status in {"processed", "ignored"}:
            return event, True
        event.event_type = event_type
        event.payload = _safe_event_snapshot(payload)
        event.status = "received"
        event.error = ""
        event.processed_at = None
        event.save(
            update_fields=[
                "event_type",
                "payload",
                "status",
                "error",
                "processed_at",
            ]
        )

    checkout_data = payload.get("checkout")
    payment_data = payload.get("payment")
    checkout_data = checkout_data if isinstance(checkout_data, dict) else {}
    payment_data = payment_data if isinstance(payment_data, dict) else {}

    checkout, external_reference, checkout_id = _find_checkout(
        checkout_data, payment_data
    )
    provider_subscription_id = _subscription_id(
        payment_data.get("subscription") or checkout_data.get("subscription")
    )
    billing_subscription = None
    if not checkout and provider_subscription_id:
        billing_subscription = (
            BillingSubscription.objects.select_related("user", "plan")
            .filter(provider_subscription_id=provider_subscription_id)
            .first()
        )

    user = checkout.user if checkout else getattr(billing_subscription, "user", None)
    plan = checkout.plan if checkout else getattr(billing_subscription, "plan", None)

    event.checkout = checkout
    event.user = user
    event.payment_id = str(payment_data.get("id") or "")
    event.provider_subscription_id = provider_subscription_id
    event.external_reference = external_reference
    event.save(
        update_fields=[
            "checkout",
            "user",
            "payment_id",
            "provider_subscription_id",
            "external_reference",
        ]
    )

    try:
        provider_customer_id = str(
            payment_data.get("customer") or checkout_data.get("customer") or ""
        )
        _get_or_update_customer(user, provider_customer_id)

        if event_type == "CHECKOUT_CREATED" and checkout:
            checkout.status = "pending"
            checkout.provider_status = str(checkout_data.get("status") or "ACTIVE")
            checkout.provider_checkout_id = checkout.provider_checkout_id or (
                checkout_id or None
            )
            checkout.save()

        elif event_type in SUCCESS_EVENTS and user and plan:
            _activate_entitlement(
                user=user,
                plan=plan,
                checkout=checkout,
                payment_data=payment_data,
                checkout_data=checkout_data,
            )

        elif event_type in PAST_DUE_EVENTS and user:
            if billing_subscription is None:
                billing_subscription = BillingSubscription.objects.filter(
                    user=user
                ).first()
            if billing_subscription:
                billing_subscription.status = "past_due"
                billing_subscription.save(update_fields=["status", "updated_at"])
            Subscription.objects.filter(user=user).update(status="past_due")

        elif event_type in REFUND_EVENTS and user:
            if billing_subscription is None:
                billing_subscription = BillingSubscription.objects.filter(
                    user=user
                ).first()
            if billing_subscription:
                billing_subscription.status = "refunded"
                billing_subscription.current_period_end = timezone.localdate()
                billing_subscription.save(
                    update_fields=["status", "current_period_end", "updated_at"]
                )
            _downgrade_after_refund(user)

        elif event_type in CANCEL_EVENTS:
            if checkout:
                checkout.status = (
                    "expired" if event_type == "CHECKOUT_EXPIRED" else "cancelled"
                )
                checkout.provider_status = str(
                    checkout_data.get("status") or event_type
                )
                checkout.save(
                    update_fields=["status", "provider_status", "updated_at"]
                )
            if event_type == "PAYMENT_DELETED" and user:
                if billing_subscription is None:
                    billing_subscription = BillingSubscription.objects.filter(
                        user=user
                    ).first()
                if billing_subscription:
                    billing_subscription.status = "cancelled"
                    billing_subscription.cancel_at_period_end = True
                    billing_subscription.cancelled_at = timezone.now()
                    billing_subscription.save(
                        update_fields=[
                            "status",
                            "cancel_at_period_end",
                            "cancelled_at",
                            "updated_at",
                        ]
                    )

        else:
            event.status = "ignored"
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "processed_at"])
            return event, False

        event.status = "processed"
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])
        return event, False
    except Exception as exc:
        event.status = "failed"
        event.error = str(exc)[:500]
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "error", "processed_at"])
        raise
