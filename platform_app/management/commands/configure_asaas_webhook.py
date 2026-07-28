from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from platform_app.billing import AsaasError, configure_asaas_webhook


class Command(BaseCommand):
    help = "Cria ou atualiza o Webhook do Asaas de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-url",
            dest="base_url",
            help="URL pública da aplicação, por exemplo https://app.onrender.com",
        )

    def handle(self, *args, **options):
        base_url = (options.get("base_url") or settings.PUBLIC_BASE_URL).rstrip("/")
        if not base_url.startswith("https://"):
            raise CommandError(
                "Informe uma URL HTTPS válida com --base-url ou PUBLIC_BASE_URL."
            )

        try:
            result = configure_asaas_webhook(base_url)
        except AsaasError as exc:
            raise CommandError(str(exc)) from exc

        webhook = result.get("webhook") or {}
        webhook_id = webhook.get("id", "não informado")
        self.stdout.write(
            self.style.SUCCESS(
                f"Webhook {result['action']} com sucesso. ID: {webhook_id}."
            )
        )
