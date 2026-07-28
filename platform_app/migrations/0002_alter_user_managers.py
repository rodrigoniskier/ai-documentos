import platform_app.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("platform_app", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", platform_app.models.UserManager()),
            ],
        ),
    ]
