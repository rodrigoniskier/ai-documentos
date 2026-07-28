from django.conf import settings


def has_unlimited_credits(user) -> bool:
    """Retorna True para contas autorizadas a gerar sem consumir créditos."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    email = (getattr(user, "email", "") or "").strip().lower()
    return email in settings.UNLIMITED_CREDIT_EMAILS
