from django.core.management.base import BaseCommand

from platform_app.product_plans import apply_paid_plan_limits
from platform_app.services import ensure_plans


class Command(BaseCommand):
    help = "Cria ou atualiza os planos comerciais padrão."

    def handle(self, *args, **options):
        ensure_plans()
        apply_paid_plan_limits()
        self.stdout.write(self.style.SUCCESS("Planos configurados com sucesso."))
