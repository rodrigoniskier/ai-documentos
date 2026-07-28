import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .billing import create_recurring_checkout
from .models import BillingCheckout, BillingEvent, Plan, User
from .services import ensure_plans, provision_free_account


@override_settings(
    ASAAS_ENABLED=True,
    ASAAS_API_KEY="sandbox-key",
    ASAAS_WEBHOOK_TOKEN="x" * 40,
    ASAAS_BASE_URL="https://api-sandbox.asaas.com/v3",
    PUBLIC_BASE_URL="https://rn-document-platform.onrender.com",
)
class BillingWebhookTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user = User.objects.create_user(
            email="billing@example.com",
            password="SenhaForte123!",
            full_name="Professor Billing",
            professional_name="Prof. Billing",
        )
        provision_free_account(self.user)
        self.pro = Plan.objects.get(code="PRO")
        self.checkout = BillingCheckout.objects.create(
            user=self.user,
            plan=self.pro,
            external_reference="rndoc-checkout-test",
            provider_checkout_id="checkout-test",
            checkout_url="https://sandbox.asaas.com/checkoutSession/show/test",
            amount="19.90",
            status="pending",
        )
        self.payload = {
            "id": "evt_checkout_paid_001",
            "event": "CHECKOUT_PAID",
            "dateCreated": "2026-07-25 12:00:00",
            "checkout": {
                "id": "checkout-test",
                "status": "PAID",
                "externalReference": "rndoc-checkout-test",
                "customer": "cus_test",
                "subscription": {
                    "id": "sub_test",
                    "cycle": "MONTHLY",
                    "nextDueDate": "2026-08-25",
                },
            },
        }

    def post_webhook(self, payload=None, token=None):
        return self.client.post(
            reverse("asaas_webhook"),
            data=json.dumps(payload or self.payload),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN=token or ("x" * 40),
        )

    def test_webhook_rejects_invalid_token(self):
        response = self.post_webhook(token="invalid")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(BillingEvent.objects.exists())

    def test_paid_checkout_activates_plan_and_grants_credits_once(self):
        response = self.post_webhook()
        self.assertEqual(response.status_code, 200)

        self.user.subscription.refresh_from_db()
        self.user.wallet.refresh_from_db()
        self.checkout.refresh_from_db()

        self.assertEqual(self.user.subscription.plan.code, "PRO")
        self.assertEqual(self.user.wallet.balance, 45)
        self.assertEqual(self.checkout.status, "paid")
        self.assertEqual(self.user.billing_subscription.status, "active")
        self.assertEqual(
            self.user.billing_subscription.provider_subscription_id,
            "sub_test",
        )

        duplicate = self.post_webhook()
        self.assertEqual(duplicate.status_code, 200)
        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, 45)
        self.assertEqual(
            BillingEvent.objects.filter(
                provider_event_id="evt_checkout_paid_001"
            ).count(),
            1,
        )


@override_settings(
    ASAAS_ENABLED=True,
    ASAAS_API_KEY="sandbox-key",
    ASAAS_WEBHOOK_TOKEN="x" * 40,
    ASAAS_BASE_URL="https://api-sandbox.asaas.com/v3",
    PUBLIC_BASE_URL="https://rn-document-platform.onrender.com",
    ASAAS_BILLING_TYPES="CREDIT_CARD",
)
class BillingCheckoutServiceTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user = User.objects.create_user(
            email="service-checkout@example.com",
            password="SenhaForte123!",
            full_name="Professor Serviço",
            professional_name="Prof. Serviço",
        )
        provision_free_account(self.user)
        self.pro = Plan.objects.get(code="PRO")

    @patch("platform_app.billing_checkout.asaas_request")
    def test_recurring_checkout_charges_on_current_date(self, asaas_request):
        asaas_request.return_value = {
            "id": "checkout-service-test",
            "link": "https://sandbox.asaas.com/checkoutSession/show/service-test",
            "status": "ACTIVE",
        }

        checkout = create_recurring_checkout(
            self.user,
            self.pro,
            "https://rn-document-platform.onrender.com",
        )

        payload = asaas_request.call_args.args[2]
        self.assertEqual(payload["chargeTypes"], ["RECURRENT"])
        self.assertEqual(payload["billingTypes"], ["CREDIT_CARD"])
        self.assertEqual(
            payload["subscription"]["nextDueDate"][:10],
            timezone.localdate().isoformat(),
        )
        self.assertEqual(payload["items"][0]["value"], 19.9)
        self.assertEqual(checkout.status, "pending")


@override_settings(
    ASAAS_ENABLED=True,
    ASAAS_API_KEY="sandbox-key",
    ASAAS_WEBHOOK_TOKEN="x" * 40,
    PUBLIC_BASE_URL="https://rn-document-platform.onrender.com",
)
class BillingCheckoutViewTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user = User.objects.create_user(
            email="checkout@example.com",
            password="SenhaForte123!",
            full_name="Professor Checkout",
            professional_name="Prof. Checkout",
        )
        provision_free_account(self.user)
        self.client.force_login(self.user)

    @patch("platform_app.billing_views.create_recurring_checkout")
    def test_start_checkout_redirects_to_asaas(self, create_checkout):
        create_checkout.return_value = SimpleNamespace(
            checkout_url="https://sandbox.asaas.com/checkoutSession/show/test"
        )
        response = self.client.post(
            reverse("billing_start", kwargs={"plan_code": "PRO"})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://sandbox.asaas.com/checkoutSession/show/test",
        )


class FounderCatalogTests(TestCase):
    def test_founder_catalog_uses_pro_and_ultra_prices(self):
        ensure_plans()
        pro = Plan.objects.get(code="PRO")
        ultra = Plan.objects.get(code="PREMIUM")
        self.assertEqual(pro.price_label, "R$ 19,90/mês")
        self.assertEqual(ultra.name, "Ultra")
        self.assertEqual(ultra.price_label, "R$ 49,90/mês")
