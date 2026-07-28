from django.core.management.base import BaseCommand

from platform_app.services import ensure_plans


class Command(BaseCommand):
    help = "Cria ou atualiza os planos comerciais padrão."

    def handle(self, *args, **options):
        ensure_plans()
        self.stdout.write(self.style.SUCCESS("Planos configurados com sucesso."))
