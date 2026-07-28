import json
import secrets
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from django.conf import settings
from django.urls import reverse


WEBHOOK_EVENTS = [
    "CHECKOUT_CREATED",
    "CHECKOUT_CANCELED",
    "CHECKOUT_EXPIRED",
    "CHECKOUT_PAID",
    "PAYMENT_CREATED",
    "PAYMENT_UPDATED",
    "PAYMENT_CONFIRMED",
    "PAYMENT_RECEIVED",
    "PAYMENT_OVERDUE",
    "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
    "PAYMENT_REFUNDED",
    "PAYMENT_PARTIALLY_REFUNDED",
    "PAYMENT_DELETED",
]


class AsaasError(RuntimeError):
    pass


def _parse_json_response(raw: bytes):
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _format_asaas_error(status: int, payload) -> str:
    errors = payload.get("errors", []) if isinstance(payload, dict) else []
    descriptions = [
        str(item.get("description", "")).strip()
        for item in errors
        if isinstance(item, dict) and item.get("description")
    ]
    detail = "; ".join(descriptions) or "resposta não detalhada"
    return f"Asaas respondeu HTTP {status}: {detail}"


def asaas_request(
    method: str,
    path: str,
    payload=None,
    query=None,
    *,
    require_enabled: bool = False,
):
    if require_enabled and not settings.ASAAS_ENABLED:
        raise AsaasError("A cobrança pelo Asaas ainda não está habilitada.")
    if not settings.ASAAS_API_KEY:
        raise AsaasError("A chave da API do Asaas ainda não foi configurada.")

    url = f"{settings.ASAAS_BASE_URL}/{path.lstrip('/')}"
    if query:
        url = f"{url}?{urlencode(query)}"

    body = None
    headers = {
        "accept": "application/json",
        "access_token": settings.ASAAS_API_KEY,
        "User-Agent": "RN-DocumentAI/1.0",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json"

    request = Request(url, data=body, method=method.upper(), headers=headers)
    try:
        with urlopen(request, timeout=settings.ASAAS_HTTP_TIMEOUT) as response:
            return _parse_json_response(response.read())
    except HTTPError as exc:
        response_payload = _parse_json_response(exc.read())
        raise AsaasError(_format_asaas_error(exc.code, response_payload)) from exc
    except (URLError, TimeoutError) as exc:
        raise AsaasError("Não foi possível comunicar com o Asaas.") from exc


def absolute_url(base_url: str, route_name: str, **kwargs) -> str:
    path = reverse(route_name, kwargs=kwargs)
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def configure_asaas_webhook(base_url: str) -> dict:
    if not settings.ASAAS_API_KEY:
        raise AsaasError("ASAAS_API_KEY não configurada.")
    if len(settings.ASAAS_WEBHOOK_TOKEN) < 32:
        raise AsaasError("ASAAS_WEBHOOK_TOKEN deve ter ao menos 32 caracteres.")

    webhook_url = absolute_url(base_url, "asaas_webhook")
    desired = {
        "name": settings.ASAAS_WEBHOOK_NAME,
        "url": webhook_url,
        "email": settings.ASAAS_WEBHOOK_EMAIL,
        "enabled": True,
        "interrupted": False,
        "apiVersion": 3,
        "authToken": settings.ASAAS_WEBHOOK_TOKEN,
        "sendType": "SEQUENTIALLY",
        "events": WEBHOOK_EVENTS,
    }

    existing_payload = asaas_request(
        "GET",
        "/webhooks",
        query={"offset": 0, "limit": 100},
    )
    if isinstance(existing_payload, dict):
        existing_items = (
            existing_payload.get("data")
            or existing_payload.get("items")
            or []
        )
    elif isinstance(existing_payload, list):
        existing_items = existing_payload
    else:
        existing_items = []

    existing = next(
        (
            item
            for item in existing_items
            if isinstance(item, dict)
            and (
                item.get("url") == webhook_url
                or item.get("name") == settings.ASAAS_WEBHOOK_NAME
            )
        ),
        None,
    )
    if existing and existing.get("id"):
        update_payload = {
            key: desired[key]
            for key in (
                "name",
                "url",
                "enabled",
                "interrupted",
                "authToken",
                "sendType",
                "events",
            )
        }
        result = asaas_request(
            "PUT",
            f"/webhooks/{existing['id']}",
            update_payload,
        )
        return {"action": "updated", "webhook": result}

    result = asaas_request("POST", "/webhooks", desired)
    return {"action": "created", "webhook": result}


def validate_webhook_token(received_token: str) -> bool:
    expected = settings.ASAAS_WEBHOOK_TOKEN
    return bool(
        expected
        and received_token
        and secrets.compare_digest(str(received_token), str(expected))
    )
