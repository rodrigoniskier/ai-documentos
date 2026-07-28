from .billing import expire_user_subscription_if_due
from .owner_account import ensure_owner_account


class BillingExpiryMiddleware:
    """Expira assinaturas e mantém o acesso interno da conta proprietária."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            expire_user_subscription_if_due(user)
            ensure_owner_account(user)
        return self.get_response(request)
