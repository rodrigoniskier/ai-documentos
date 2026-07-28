from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .asaas_client import AsaasError, absolute_url, asaas_request
from .models import BillingCheckout, BillingSubscription, Plan, Subscription


PLAN_PRICES = {
    "PRO": Decimal("19.90"),
    "PREMIUM": Decimal("49.90"),
}


def _safe_checkout_snapshot(payload: dict) -> dict:
    return {
        "billingTypes": payload.get("billingTypes", []),
        "chargeTypes": payload.get("chargeTypes", []),
        "minutesToExpire": payload.get("minutesToExpire"),
        "externalReference": payload.get("externalReference", ""),
        "items": [
            {
                "externalReference": item.get("externalReference", ""),
                "name": item.get("name", ""),
                "quantity": item.get("quantity"),
                "value": item.get("value"),
            }
            for item in payload.get("items", [])
            if isinstance(item, dict)
        ],
        "subscription": payload.get("subscription", {}),
    }


def _billing_types() -> list[str]:
    configured = [
        item.strip().upper()
        for item in settings.ASAAS_BILLING_TYPES.split(",")
        if item.strip()
    ]
    allowed = [item for item in configured if item in {"CREDIT_CARD", "PIX"}]
    return allowed or ["CREDIT_CARD"]


@transaction.atomic
def create_recurring_checkout(user, plan: Plan, base_url: str) -> BillingCheckout:
    if plan.code not in PLAN_PRICES:
        raise AsaasError("Este plano não está disponível para assinatura.")
    if not settings.ASAAS_ENABLED:
        raise AsaasError("A assinatura online ainda não está habilitada.")

    now = timezone.now()
    active_subscription = (
        BillingSubscription.objects.select_for_update()
        .filter(
            user=user,
            status__in=["active", "past_due", "cancelled"],
        )
        .first()
    )
    if active_subscription:
        period_is_open = (
            active_subscription.current_period_end is None
            or active_subscription.current_period_end >= timezone.localdate()
        )
        if period_is_open:
            if (
                active_subscription.plan_id == plan.id
                and not active_subscription.cancel_at_period_end
            ):
                raise AsaasError("Você já possui este plano ativo.")
            raise AsaasError(
                "Já existe uma assinatura vigente. Cancele a renovação atual e "
                "aguarde o fim do período pago antes de assinar outro plano."
            )

    reusable = (
        BillingCheckout.objects.select_for_update()
        .filter(
            user=user,
            plan=plan,
            status__in=["created", "pending"],
            expires_at__gt=now,
        )
        .exclude(checkout_url="")
        .first()
    )
    if reusable:
        return reusable

    checkout = BillingCheckout(
        user=user,
        plan=plan,
        amount=PLAN_PRICES[plan.code],
        status="created",
        expires_at=now
        + timedelta(minutes=settings.ASAAS_CHECKOUT_EXPIRATION_MINUTES),
    )
    checkout.external_reference = f"rndoc-checkout-{checkout.id}"
    checkout.save()

    # The first monthly charge is due immediately. Future charges are generated
    # by Asaas according to the MONTHLY cycle.
    next_due = timezone.localtime(now).strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "billingTypes": _billing_types(),
        "chargeTypes": ["RECURRENT"],
        "minutesToExpire": settings.ASAAS_CHECKOUT_EXPIRATION_MINUTES,
        "externalReference": checkout.external_reference,
        "callback": {
            "successUrl": absolute_url(
                base_url,
                "billing_result",
                result="success",
            ),
            "cancelUrl": absolute_url(
                base_url,
                "billing_result",
                result="cancel",
            ),
            "expiredUrl": absolute_url(
                base_url,
                "billing_result",
                result="expired",
            ),
        },
        "items": [
            {
                "externalReference": plan.code,
                "name": f"RN DocumentAI — Plano {plan.name}",
                "description": "Assinatura mensal da plataforma RN DocumentAI.",
                "quantity": 1,
                "value": float(PLAN_PRICES[plan.code]),
            }
        ],
        "customerData": {
            "name": user.full_name,
            "email": user.email,
        },
        "subscription": {
            "cycle": "MONTHLY",
            "nextDueDate": next_due,
            "externalReference": checkout.external_reference,
        },
    }
    checkout.request_snapshot = _safe_checkout_snapshot(payload)
    checkout.save(update_fields=["request_snapshot", "updated_at"])

    try:
        response = asaas_request(
            "POST",
            "/checkouts",
            payload,
            require_enabled=True,
        )
    except Exception as exc:
        checkout.status = "failed"
        checkout.error = str(exc)[:500]
        checkout.save(update_fields=["status", "error", "updated_at"])
        raise

    provider_id = str(response.get("id") or "")
    checkout.provider_checkout_id = provider_id or None
    checkout.checkout_url = str(response.get("link") or "")
    if not checkout.checkout_url and provider_id:
        host = (
            "https://sandbox.asaas.com"
            if "sandbox" in settings.ASAAS_BASE_URL
            else "https://asaas.com"
        )
        checkout.checkout_url = f"{host}/checkoutSession/show/{provider_id}"
    checkout.provider_status = str(response.get("status") or "")
    checkout.status = "pending"
    checkout.response_snapshot = {
        key: response.get(key)
        for key in (
            "id",
            "link",
            "status",
            "billingTypes",
            "chargeTypes",
            "minutesToExpire",
            "externalReference",
        )
        if response.get(key) is not None
    }
    checkout.error = ""
    checkout.save()
    return checkout


@transaction.atomic
def cancel_billing_subscription(user) -> BillingSubscription:
    subscription = (
        BillingSubscription.objects.select_for_update()
        .filter(user=user)
        .first()
    )
    if not subscription or subscription.status not in {"active", "past_due"}:
        raise AsaasError("Não há assinatura ativa para cancelar.")

    if not subscription.provider_subscription_id:
        lookup = asaas_request(
            "GET",
            "/subscriptions",
            query={
                "externalReference": subscription.external_reference,
                "limit": 10,
                "offset": 0,
            },
            require_enabled=True,
        )
        items = lookup.get("data", []) if isinstance(lookup, dict) else []
        matched = next(
            (
                item
                for item in items
                if isinstance(item, dict)
                and item.get("externalReference")
                == subscription.external_reference
            ),
            None,
        )
        if matched and matched.get("id"):
            subscription.provider_subscription_id = str(matched["id"])
            subscription.save(
                update_fields=["provider_subscription_id", "updated_at"]
            )
        else:
            raise AsaasError(
                "O identificador da assinatura ainda não chegou pelo Webhook. "
                "Tente novamente após a confirmação da cobrança."
            )

    asaas_request(
        "DELETE",
        f"/subscriptions/{subscription.provider_subscription_id}",
        require_enabled=True,
    )
    subscription.status = "cancelled"
    subscription.cancel_at_period_end = True
    subscription.cancelled_at = timezone.now()
    subscription.current_period_end = (
        subscription.current_period_end
        or timezone.localdate() + timedelta(days=30)
    )
    subscription.save()
    Subscription.objects.filter(user=user).update(
        status="cancel_at_period_end"
    )
    return subscription


@transaction.atomic
def expire_user_subscription_if_due(user) -> bool:
    billing_subscription = (
        BillingSubscription.objects.select_related("plan")
        .filter(
            user=user,
            status__in=["cancelled", "expired", "refunded"],
            current_period_end__lte=timezone.localdate(),
        )
        .first()
    )
    if not billing_subscription:
        return False

    free_plan = Plan.objects.get(code="FREE")
    local_subscription, _ = Subscription.objects.get_or_create(
        user=user,
        defaults={"plan": free_plan, "status": "active"},
    )
    changed = (
        local_subscription.plan_id != free_plan.id
        or local_subscription.status != "active"
    )
    if changed:
        local_subscription.plan = free_plan
        local_subscription.status = "active"
        local_subscription.save(update_fields=["plan", "status"])
    if billing_subscription.status != "expired":
        billing_subscription.status = "expired"
        billing_subscription.save(update_fields=["status", "updated_at"])
    return changed


@transaction.atomic
def expire_cancelled_subscriptions() -> int:
    today = timezone.localdate()
    user_ids = list(
        BillingSubscription.objects.filter(
            status__in=["cancelled", "expired", "refunded"],
            current_period_end__lte=today,
        ).values_list("user_id", flat=True)
    )
    count = 0
    for user_id in user_ids:
        subscription = BillingSubscription.objects.select_related("user").get(
            user_id=user_id
        )
        if expire_user_subscription_if_due(subscription.user):
            count += 1
    return count
