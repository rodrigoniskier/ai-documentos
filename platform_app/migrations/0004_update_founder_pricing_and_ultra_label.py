from django.db import migrations, models


def update_founder_catalog(apps, schema_editor):
    Plan = apps.get_model("platform_app", "Plan")
    Lead = apps.get_model("platform_app", "Lead")

    Plan.objects.filter(code="PRO").update(price_label="R$ 19,90/mês")
    Plan.objects.filter(code="PREMIUM").update(
        name="Ultra",
        price_label="R$ 49,90/mês",
    )
    Lead.objects.filter(plan="ULTRA").update(plan="PREMIUM")


def restore_previous_catalog(apps, schema_editor):
    Plan = apps.get_model("platform_app", "Plan")

    Plan.objects.filter(code="PRO").update(price_label="R$ 39,90/mês")
    Plan.objects.filter(code="PREMIUM").update(
        name="Premium",
        price_label="R$ 89,90/mês",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("platform_app", "0003_alter_user_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lead",
            name="plan",
            field=models.CharField(
                choices=[
                    ("PRO", "Pro"),
                    ("PREMIUM", "Ultra"),
                    ("INSTITUTIONAL", "Institucional"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(update_founder_catalog, restore_previous_catalog),
    ]
