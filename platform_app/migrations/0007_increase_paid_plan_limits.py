from django.db import migrations


def increase_limits(apps, schema_editor):
    Plan = apps.get_model("platform_app", "Plan")
    Plan.objects.filter(code="PRO").update(
        monthly_credits=60,
        institution_limit=4,
        discipline_limit=20,
        source_limit=60,
        daily_limit=20,
    )
    Plan.objects.filter(code="PREMIUM").update(
        monthly_credits=180,
        institution_limit=12,
        discipline_limit=60,
        source_limit=200,
        daily_limit=60,
    )


class Migration(migrations.Migration):
    dependencies = [("platform_app", "0006_document_workflow")]
    operations = [migrations.RunPython(increase_limits, migrations.RunPython.noop)]
