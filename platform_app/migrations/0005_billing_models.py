import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("platform_app", "0004_update_founder_pricing_and_ultra_label"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingCustomer",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(default="asaas", max_length=20)),
                (
                    "provider_customer_id",
                    models.CharField(
                        blank=True,
                        max_length=80,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "external_reference",
                    models.CharField(max_length=120, unique=True),
                ),
                ("cpf_cnpj", models.CharField(blank=True, max_length=20)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_customer",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BillingCheckout",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "external_reference",
                    models.CharField(max_length=200, unique=True),
                ),
                (
                    "provider_checkout_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
                ("checkout_url", models.URLField(blank=True, max_length=500)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Criado"),
                            ("pending", "Pendente"),
                            ("paid", "Pago"),
                            ("cancelled", "Cancelado"),
                            ("expired", "Expirado"),
                            ("failed", "Falhou"),
                        ],
                        default="created",
                        max_length=20,
                    ),
                ),
                ("provider_status", models.CharField(blank=True, max_length=40)),
                (
                    "request_snapshot",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "response_snapshot",
                    models.JSONField(blank=True, default=dict),
                ),
                ("error", models.CharField(blank=True, max_length=500)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="platform_app.plan",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_checkouts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="BillingSubscription",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(default="asaas", max_length=20)),
                (
                    "provider_subscription_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "external_reference",
                    models.CharField(max_length=120, unique=True),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendente"),
                            ("active", "Ativa"),
                            ("past_due", "Em atraso"),
                            ("cancelled", "Cancelada"),
                            ("refunded", "Estornada"),
                            ("expired", "Expirada"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("last_payment_id", models.CharField(blank=True, max_length=100)),
                (
                    "current_period_start",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "current_period_end",
                    models.DateField(blank=True, null=True),
                ),
                ("next_due_date", models.DateField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="platform_app.plan",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_subscription",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BillingEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("provider", models.CharField(default="asaas", max_length=20)),
                (
                    "provider_event_id",
                    models.CharField(max_length=180, unique=True),
                ),
                ("event_type", models.CharField(max_length=80)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("received", "Recebido"),
                            ("processed", "Processado"),
                            ("ignored", "Ignorado"),
                            ("failed", "Falhou"),
                        ],
                        default="received",
                        max_length=20,
                    ),
                ),
                ("payment_id", models.CharField(blank=True, max_length=100)),
                (
                    "provider_subscription_id",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "external_reference",
                    models.CharField(blank=True, max_length=200),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("error", models.CharField(blank=True, max_length=500)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "checkout",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="platform_app.billingcheckout",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="billing_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-received_at"]},
        ),
    ]
