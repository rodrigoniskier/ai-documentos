from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("platform_app", "0002_alter_user_managers"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="user",
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
            },
        ),
    ]
