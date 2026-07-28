from .models import Plan


PAID_PLAN_LIMITS = {
    "PRO": {
        "monthly_credits": 60,
        "institution_limit": 3,
        "discipline_limit": 15,
        "source_limit": 40,
        "daily_limit": 16,
    },
    "PREMIUM": {
        "monthly_credits": 160,
        "institution_limit": 7,
        "discipline_limit": 40,
        "source_limit": 140,
        "daily_limit": 40,
    },
}


def apply_paid_plan_limits():
    for code, values in PAID_PLAN_LIMITS.items():
        Plan.objects.filter(code=code).update(**values)
