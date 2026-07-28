from django.core.management.base import BaseCommand

from platform_app.billing import expire_cancelled_subscriptions


class Command(BaseCommand):
    help = "Rebaixa para o plano gratuito assinaturas canceladas cujo período terminou."

    def handle(self, *args, **options):
        count = expire_cancelled_subscriptions()
        self.stdout.write(
            self.style.SUCCESS(f"Assinaturas expiradas processadas: {count}.")
        )
