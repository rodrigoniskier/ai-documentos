# Generated for RN DocumentAI initial schema.

import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=60)),
                ("price_label", models.CharField(max_length=60)),
                ("initial_credits", models.PositiveIntegerField(default=0)),
                ("monthly_credits", models.PositiveIntegerField(default=0)),
                ("institution_limit", models.PositiveIntegerField(default=1)),
                ("discipline_limit", models.PositiveIntegerField(default=1)),
                ("source_limit", models.PositiveIntegerField(default=3)),
                ("daily_limit", models.PositiveIntegerField(default=4)),
                ("watermark", models.BooleanField(default=True)),
                ("display_order", models.PositiveSmallIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["display_order"]},
        ),
        migrations.CreateModel(
            name="User",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False, help_text="Designates that this user has all permissions without explicitly assigning them.", verbose_name="superuser status")),
                ("first_name", models.CharField(blank=True, max_length=150, verbose_name="first name")),
                ("last_name", models.CharField(blank=True, max_length=150, verbose_name="last name")),
                ("is_staff", models.BooleanField(default=False, help_text="Designates whether the user can log into this admin site.", verbose_name="staff status")),
                ("is_active", models.BooleanField(default=True, help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.", verbose_name="active")),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now, verbose_name="date joined")),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="e-mail")),
                ("full_name", models.CharField(max_length=180, verbose_name="nome completo")),
                ("professional_name", models.CharField(max_length=180, verbose_name="nome profissional")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("groups", models.ManyToManyField(blank=True, help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", related_name="user_set", related_query_name="user", to="auth.group", verbose_name="groups")),
                ("user_permissions", models.ManyToManyField(blank=True, help_text="Specific permissions for this user.", related_name="user_set", related_query_name="user", to="auth.permission", verbose_name="user permissions")),
            ],
            options={"abstract": False},
            managers=[("objects", django.contrib.auth.models.UserManager())],
        ),
        migrations.CreateModel(
            name="Institution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("acronym", models.CharField(blank=True, max_length=30)),
                ("logo", models.ImageField(blank=True, upload_to="institutions/logos/%Y/%m/")),
                ("city", models.CharField(blank=True, max_length=100)),
                ("state", models.CharField(blank=True, max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="institutions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("level", models.CharField(blank=True, max_length=80)),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="courses", to="platform_app.institution")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="courses", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Discipline",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("workload", models.PositiveIntegerField(default=40)),
                ("semester", models.CharField(blank=True, max_length=40)),
                ("syllabus", models.TextField(verbose_name="ementa")),
                ("objectives", models.TextField(blank=True, verbose_name="objetivos")),
                ("bibliography", models.TextField(blank=True, verbose_name="bibliografia")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="disciplines", to="platform_app.course")),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="disciplines", to="platform_app.institution")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="disciplines", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Generation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(default="processing", max_length=20)),
                ("idempotency_key", models.CharField(max_length=120, unique=True)),
                ("output", models.JSONField(blank=True, default=dict)),
                ("error", models.CharField(blank=True, max_length=500)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("discipline", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="platform_app.discipline")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="generations", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="GeneratedDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30, unique=True)),
                ("title", models.CharField(max_length=220)),
                ("content", models.JSONField(default=dict)),
                ("file", models.FileField(upload_to="generated/%Y/%m/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("generation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="platform_app.generation")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(max_length=254)),
                ("organization", models.CharField(blank=True, max_length=180)),
                ("plan", models.CharField(choices=[("PRO", "Pro"), ("PREMIUM", "Premium"), ("INSTITUTIONAL", "Institucional")], max_length=20)),
                ("message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("kind", models.CharField(choices=[("PPC", "PPC"), ("DCN", "DCN"), ("REGULATION", "Regulamento"), ("SYLLABUS", "Ementa"), ("CALENDAR", "Calendário"), ("OTHER", "Outro")], max_length=30)),
                ("file", models.FileField(upload_to="sources/%Y/%m/")),
                ("extracted_text", models.TextField(blank=True)),
                ("status", models.CharField(default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("discipline", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="platform_app.discipline")),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="platform_app.institution")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sources", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(default="active", max_length=20)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="platform_app.plan")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="subscription", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Wallet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("balance", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="wallet", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="CreditEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=20)),
                ("amount", models.IntegerField()),
                ("balance_before", models.PositiveIntegerField()),
                ("balance_after", models.PositiveIntegerField()),
                ("idempotency_key", models.CharField(max_length=120, unique=True)),
                ("reason", models.CharField(max_length=255)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credit_entries", to=settings.AUTH_USER_MODEL)),
                ("wallet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="platform_app.wallet")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
