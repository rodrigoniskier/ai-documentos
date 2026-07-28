import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .billing import (
    AsaasError,
    cancel_billing_subscription,
    create_recurring_checkout,
    process_asaas_event,
    validate_webhook_token,
)
from .models import BillingCheckout, BillingSubscription, Plan


def _public_base_url(request) -> str:
    if settings.PUBLIC_BASE_URL:
        return settings.PUBLIC_BASE_URL.rstrip("/")
    return request.build_absolute_uri("/").rstrip("/")


@login_required
def subscription_page(request):
    paid_plans = Plan.objects.filter(
        code__in=["PRO", "PREMIUM"],
        active=True,
    ).order_by("display_order")
    billing_subscription = (
        BillingSubscription.objects.filter(user=request.user)
        .select_related("plan")
        .first()
    )
    recent_checkouts = (
        BillingCheckout.objects.filter(user=request.user)
        .select_related("plan")
        .order_by("-created_at")[:5]
    )
    return render(
        request,
        "subscription.html",
        {
            "paid_plans": paid_plans,
            "billing_subscription": billing_subscription,
            "recent_checkouts": recent_checkouts,
            "billing_enabled": settings.ASAAS_ENABLED,
        },
    )


@login_required
@require_POST
def billing_start(request, plan_code):
    plan = get_object_or_404(Plan, code=plan_code, active=True)
    if plan.code not in {"PRO", "PREMIUM"}:
        messages.error(request, "Este plano não está disponível para assinatura.")
        return redirect("subscription")

    try:
        checkout = create_recurring_checkout(
            request.user,
            plan,
            _public_base_url(request),
        )
    except AsaasError as exc:
        messages.error(request, str(exc))
        return redirect("subscription")
    except Exception:
        messages.error(
            request,
            "Não foi possível iniciar o checkout. Tente novamente em instantes.",
        )
        return redirect("subscription")

    if not checkout.checkout_url.startswith("https://"):
        messages.error(request, "O Asaas não retornou uma URL segura de checkout.")
        return redirect("subscription")
    return HttpResponseRedirect(checkout.checkout_url)


@login_required
def billing_result(request, result):
    if result not in {"success", "cancel", "expired"}:
        return redirect("subscription")
    return render(
        request,
        "billing_result.html",
        {
            "result": result,
            "billing_subscription": (
                BillingSubscription.objects.filter(user=request.user)
                .select_related("plan")
                .first()
            ),
        },
    )


@login_required
@require_POST
def billing_cancel(request):
    try:
        cancel_billing_subscription(request.user)
    except AsaasError as exc:
        messages.error(request, str(exc))
    except Exception:
        messages.error(request, "Não foi possível cancelar a recorrência neste momento.")
    else:
        messages.success(
            request,
            "A recorrência foi cancelada. O acesso permanece até o fim do período pago.",
        )
    return redirect("subscription")


@csrf_exempt
@require_POST
def asaas_webhook(request):
    received_token = request.headers.get("asaas-access-token", "")
    if not validate_webhook_token(received_token):
        return JsonResponse({"status": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"status": "invalid_json"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"status": "invalid_payload"}, status=400)

    try:
        event, duplicate = process_asaas_event(payload)
    except AsaasError as exc:
        return JsonResponse(
            {"status": "invalid_event", "detail": str(exc)},
            status=400,
        )
    except Exception:
        return JsonResponse({"status": "processing_error"}, status=500)

    return JsonResponse(
        {
            "status": "duplicate" if duplicate else event.status,
            "event": event.event_type,
        }
    )
