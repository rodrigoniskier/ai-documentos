from django.test import TestCase

from .models import Lead, Plan
from .services import ensure_plans


class PlanCatalogTests(TestCase):
    def test_founder_prices_and_ultra_label(self):
        ensure_plans()

        pro = Plan.objects.get(code="PRO")
        ultra = Plan.objects.get(code="PREMIUM")

        self.assertEqual(pro.name, "Pro")
        self.assertEqual(pro.price_label, "R$ 19,90/mês")
        self.assertEqual(ultra.name, "Ultra")
        self.assertEqual(ultra.price_label, "R$ 49,90/mês")

    def test_paid_interest_choices_present_ultra_name(self):
        choices = dict(Lead._meta.get_field("plan").choices)

        self.assertEqual(choices["PRO"], "Pro")
        self.assertEqual(choices["PREMIUM"], "Ultra")
