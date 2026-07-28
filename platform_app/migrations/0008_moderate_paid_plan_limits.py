from django.db import migrations


def moderate_limits(apps, schema_editor):
    Plan = apps.get_model("platform_app", "Plan")
    Plan.objects.filter(code="PRO").update(
        monthly_credits=60,
        institution_limit=3,
        discipline_limit=15,
        source_limit=40,
        daily_limit=16,
    )
    Plan.objects.filter(code="PREMIUM").update(
        monthly_credits=160,
        institution_limit=7,
        discipline_limit=40,
        source_limit=140,
        daily_limit=40,
    )


class Migration(migrations.Migration):
    dependencies = [("platform_app", "0007_increase_paid_plan_limits")]
    operations = [migrations.RunPython(moderate_limits, migrations.RunPython.noop)]
