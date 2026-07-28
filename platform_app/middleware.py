from .billing import expire_user_subscription_if_due


class BillingExpiryMiddleware:
    """Lazily expires cancelled subscriptions after the paid period."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            expire_user_subscription_if_due(user)
        return self.get_response(request)
