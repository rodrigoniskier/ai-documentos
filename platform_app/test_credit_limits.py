from django.test import TestCase

from .models import CreditEntry, User
from .services import (
    ensure_plans,
    provision_free_account,
    refund_credits,
    reserve_credits,
)


class DailyCreditLimitTests(TestCase):
    def setUp(self):
        ensure_plans()
        self.user = User.objects.create_user(
            email="credit-limit@example.com",
            password="SenhaForte123!",
            full_name="Professora Créditos",
            professional_name="Profa. Créditos",
        )
        provision_free_account(self.user)

    def test_refunded_attempts_do_not_consume_daily_limit(self):
        for index in range(1, 3):
            reference = f"failed-attempt:{index}"
            reserve_credits(
                self.user,
                2,
                idempotency_key=f"reserve:{index}",
                reference=reference,
            )
            refund_credits(
                self.user,
                2,
                idempotency_key=f"refund:{index}",
                reference=reference,
            )

        self.assertEqual(
            CreditEntry.objects.filter(
                user=self.user,
                kind="refunded",
            ).count(),
            2,
        )

        reserve_credits(
            self.user,
            2,
            idempotency_key="reserve:successful",
            reference="successful-attempt",
        )

        self.user.wallet.refresh_from_db()
        self.assertEqual(self.user.wallet.balance, 3)
        self.assertEqual(
            CreditEntry.objects.filter(
                user=self.user,
                kind="reserve",
            ).count(),
            1,
        )
