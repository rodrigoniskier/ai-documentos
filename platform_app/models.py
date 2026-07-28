import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField("nome completo", max_length=180)
    professional_name = models.CharField("nome profissional", max_length=180)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "professional_name"]
    objects = UserManager()

    def __str__(self):
        return self.professional_name or self.email


class Plan(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=60)
    price_label = models.CharField(max_length=60)
    initial_credits = models.PositiveIntegerField(default=0)
    monthly_credits = models.PositiveIntegerField(default=0)
    institution_limit = models.PositiveIntegerField(default=1)
    discipline_limit = models.PositiveIntegerField(default=1)
    source_limit = models.PositiveIntegerField(default=3)
    daily_limit = models.PositiveIntegerField(default=4)
    watermark = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="subscription",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="active")
    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.plan}"


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="wallet",
        on_delete=models.CASCADE,
    )
    balance = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}: {self.balance} créditos"


class CreditEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="credit_entries",
        on_delete=models.CASCADE,
    )
    wallet = models.ForeignKey(Wallet, related_name="entries", on_delete=models.CASCADE)
    kind = models.CharField(max_length=20)
    amount = models.IntegerField()
    balance_before = models.PositiveIntegerField()
    balance_after = models.PositiveIntegerField()
    idempotency_key = models.CharField(max_length=120, unique=True)
    reason = models.CharField(max_length=255)
    reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Institution(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="institutions",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=180)
    acronym = models.CharField(max_length=30, blank=True)
    logo = models.ImageField(upload_to="institutions/logos/%Y/%m/", blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="courses",
        on_delete=models.CASCADE,
    )
    institution = models.ForeignKey(
        Institution,
        related_name="courses",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=180)
    level = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.name


class Discipline(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="disciplines",
        on_delete=models.CASCADE,
    )
    institution = models.ForeignKey(
        Institution,
        related_name="disciplines",
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        Course,
        related_name="disciplines",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=180)
    workload = models.PositiveIntegerField(default=40)
    semester = models.CharField(max_length=40, blank=True)
    syllabus = models.TextField("ementa")
    objectives = models.TextField("objetivos", blank=True)
    bibliography = models.TextField("bibliografia", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Source(models.Model):
    SOURCE_TYPES = [
        ("PPC", "PPC"),
        ("DCN", "DCN"),
        ("REGULATION", "Regulamento"),
        ("SYLLABUS", "Ementa"),
        ("CALENDAR", "Calendário"),
        ("OTHER", "Outro"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="sources",
        on_delete=models.CASCADE,
    )
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    discipline = models.ForeignKey(
        Discipline,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=30, choices=SOURCE_TYPES)
    file = models.FileField(upload_to="sources/%Y/%m/")
    extracted_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Generation(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="generations",
        on_delete=models.CASCADE,
    )
    discipline = models.ForeignKey(Discipline, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="processing")
    idempotency_key = models.CharField(max_length=120, unique=True)
    output = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class GeneratedDocument(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="documents",
        on_delete=models.CASCADE,
    )
    generation = models.OneToOneField(Generation, on_delete=models.CASCADE)
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=220)
    content = models.JSONField(default=dict)
    file = models.FileField(upload_to="generated/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Lead(models.Model):
    PLAN_CHOICES = [
        ("PRO", "Pro"),
        ("PREMIUM", "Ultra"),
        ("INSTITUTIONAL", "Institucional"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    name = models.CharField(max_length=180)
    email = models.EmailField()
    organization = models.CharField(max_length=180, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BillingCustomer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="billing_customer",
        on_delete=models.CASCADE,
    )
    provider = models.CharField(max_length=20, default="asaas")
    provider_customer_id = models.CharField(
        max_length=80, null=True, blank=True, unique=True
    )
    external_reference = models.CharField(max_length=120, unique=True)
    cpf_cnpj = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Asaas — {self.user}"


class BillingCheckout(models.Model):
    STATUS_CHOICES = [
        ("created", "Criado"),
        ("pending", "Pendente"),
        ("paid", "Pago"),
        ("cancelled", "Cancelado"),
        ("expired", "Expirado"),
        ("failed", "Falhou"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="billing_checkouts",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    external_reference = models.CharField(max_length=200, unique=True)
    provider_checkout_id = models.CharField(
        max_length=100, null=True, blank=True, unique=True
    )
    checkout_url = models.URLField(max_length=500, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="created"
    )
    provider_status = models.CharField(max_length=40, blank=True)
    request_snapshot = models.JSONField(default=dict, blank=True)
    response_snapshot = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.plan} — {self.status}"


class BillingSubscription(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pendente"),
        ("active", "Ativa"),
        ("past_due", "Em atraso"),
        ("cancelled", "Cancelada"),
        ("refunded", "Estornada"),
        ("expired", "Expirada"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="billing_subscription",
        on_delete=models.CASCADE,
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    provider = models.CharField(max_length=20, default="asaas")
    provider_subscription_id = models.CharField(
        max_length=100, null=True, blank=True, unique=True
    )
    external_reference = models.CharField(max_length=120, unique=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    last_payment_id = models.CharField(max_length=100, blank=True)
    current_period_start = models.DateField(null=True, blank=True)
    current_period_end = models.DateField(null=True, blank=True)
    next_due_date = models.DateField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.plan} — {self.status}"


class BillingEvent(models.Model):
    STATUS_CHOICES = [
        ("received", "Recebido"),
        ("processed", "Processado"),
        ("ignored", "Ignorado"),
        ("failed", "Falhou"),
    ]

    provider = models.CharField(max_length=20, default="asaas")
    provider_event_id = models.CharField(max_length=180, unique=True)
    event_type = models.CharField(max_length=80)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="received"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_events",
    )
    checkout = models.ForeignKey(
        BillingCheckout,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    payment_id = models.CharField(max_length=100, blank=True)
    provider_subscription_id = models.CharField(max_length=100, blank=True)
    external_reference = models.CharField(max_length=200, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_type} — {self.provider_event_id}"
