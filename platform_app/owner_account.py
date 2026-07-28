from django.db import transaction

from .access import has_unlimited_credits
from .models import Plan, Subscription, Wallet


OWNER_CAPACITY = 1_000_000


@transaction.atomic
def ensure_owner_account(user) -> bool:
    """Mantém a conta proprietária em um plano interno sem limites práticos."""
    if not has_unlimited_credits(user):
        return False

    plan, _ = Plan.objects.update_or_create(
        code="OWNER",
        defaults={
            "name": "Proprietário",
            "price_label": "Acesso interno",
            "initial_credits": OWNER_CAPACITY,
            "monthly_credits": OWNER_CAPACITY,
            "institution_limit": OWNER_CAPACITY,
            "discipline_limit": OWNER_CAPACITY,
            "source_limit": OWNER_CAPACITY,
            "daily_limit": OWNER_CAPACITY,
            "watermark": False,
            "display_order": 99,
            "active": False,
        },
    )
    subscription, _ = Subscription.objects.get_or_create(
        user=user, defaults={"plan": plan, "status": "active"}
    )
    if subscription.plan_id != plan.id or subscription.status != "active":
        subscription.plan = plan
        subscription.status = "active"
        subscription.save(update_fields=["plan", "status"])

    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=user)
    if wallet.balance < OWNER_CAPACITY:
        wallet.balance = OWNER_CAPACITY
        wallet.save(update_fields=["balance", "updated_at"])
    return True
