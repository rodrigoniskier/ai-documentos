from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CreditEntry


@receiver(post_save, sender=CreditEntry)
def mark_reserve_as_refunded(sender, instance, created, **kwargs):
    if not created or instance.kind != "refund" or not instance.reference:
        return

    CreditEntry.objects.filter(
        user=instance.user,
        kind="reserve",
        reference=instance.reference,
    ).update(kind="refunded")
