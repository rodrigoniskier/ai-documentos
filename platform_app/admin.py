from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    BillingCheckout,
    BillingCustomer,
    BillingEvent,
    BillingSubscription,
    Course,
    CreditEntry,
    Discipline,
    GeneratedDocument,
    Generation,
    Institution,
    Lead,
    Plan,
    Source,
    Subscription,
    User,
    Wallet,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "professional_name", "is_staff", "is_active")
    search_fields = ("email", "full_name", "professional_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Perfil", {"fields": ("full_name", "professional_name")}),
        (
            "Permissões",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "professional_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(BillingCheckout)
class BillingCheckoutAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "provider_status",
        "amount",
        "created_at",
    )
    list_filter = ("status", "provider_status", "plan")
    search_fields = (
        "user__email",
        "external_reference",
        "provider_checkout_id",
    )
    readonly_fields = (
        "id",
        "external_reference",
        "provider_checkout_id",
        "checkout_url",
        "request_snapshot",
        "response_snapshot",
        "created_at",
        "updated_at",
        "paid_at",
    )


@admin.register(BillingSubscription)
class BillingSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "status",
        "current_period_end",
        "next_due_date",
        "updated_at",
    )
    list_filter = ("status", "plan", "cancel_at_period_end")
    search_fields = (
        "user__email",
        "provider_subscription_id",
        "external_reference",
        "last_payment_id",
    )
    readonly_fields = ("created_at", "updated_at", "activated_at", "cancelled_at")


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "status",
        "user",
        "payment_id",
        "received_at",
    )
    list_filter = ("status", "event_type")
    search_fields = (
        "provider_event_id",
        "payment_id",
        "provider_subscription_id",
        "external_reference",
        "user__email",
    )
    readonly_fields = (
        "provider_event_id",
        "event_type",
        "payload",
        "received_at",
        "processed_at",
    )


@admin.register(BillingCustomer)
class BillingCustomerAdmin(admin.ModelAdmin):
    list_display = ("user", "provider_customer_id", "updated_at")
    search_fields = (
        "user__email",
        "provider_customer_id",
        "external_reference",
    )
    readonly_fields = ("created_at", "updated_at")


admin.site.register(Plan)
admin.site.register(Subscription)
admin.site.register(Wallet)
admin.site.register(CreditEntry)
admin.site.register(Institution)
admin.site.register(Course)
admin.site.register(Discipline)
admin.site.register(Source)
admin.site.register(Generation)
admin.site.register(GeneratedDocument)
admin.site.register(Lead)
