UNLIMITED_CREDIT_EMAILS = {"niskier.rodrigo@gmail.com"}


def has_unlimited_credits(user) -> bool:
    """Retorna True para contas autorizadas a gerar sem consumir créditos."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    email = (getattr(user, "email", "") or "").strip().lower()
    return email in UNLIMITED_CREDIT_EMAILS
