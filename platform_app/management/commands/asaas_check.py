from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from platform_app.billing import AsaasError, asaas_request


class Command(BaseCommand):
    help = "Valida a chave e o acesso à API do Asaas sem criar cobranças."

    def handle(self, *args, **options):
        if not settings.ASAAS_API_KEY:
            raise CommandError("ASAAS_API_KEY não configurada.")
        try:
            payload = asaas_request(
                "GET",
                "/webhooks",
                query={"offset": 0, "limit": 1},
            )
        except AsaasError as exc:
            raise CommandError(str(exc)) from exc

        count = 0
        if isinstance(payload, dict):
            data = payload.get("data") or payload.get("items") or []
            count = len(data) if isinstance(data, list) else 0
        elif isinstance(payload, list):
            count = len(payload)

        environment = "sandbox" if "sandbox" in settings.ASAAS_BASE_URL else "produção"
        self.stdout.write(
            self.style.SUCCESS(
                f"Conexão com o Asaas validada ({environment}). "
                f"Webhooks visíveis nesta página: {count}."
            )
        )
