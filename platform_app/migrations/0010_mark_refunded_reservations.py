from django.db import migrations


def mark_refunded_reservations(apps, schema_editor):
    CreditEntry = apps.get_model("platform_app", "CreditEntry")
    refunds = (
        CreditEntry.objects.filter(kind="refund")
        .exclude(reference="")
        .values_list("user_id", "reference")
        .iterator()
    )
    for user_id, reference in refunds:
        CreditEntry.objects.filter(
            user_id=user_id,
            kind="reserve",
            reference=reference,
        ).update(kind="refunded")


class Migration(migrations.Migration):
    dependencies = [("platform_app", "0009_cleanup_failed_document_uploads")]
    operations = [
        migrations.RunPython(
            mark_refunded_reservations,
            migrations.RunPython.noop,
        )
    ]
