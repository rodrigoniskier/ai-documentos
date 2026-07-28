from .models import Plan


PAID_PLAN_LIMITS = {
    "PRO": {
        "monthly_credits": 60,
        "institution_limit": 4,
        "discipline_limit": 20,
        "source_limit": 60,
        "daily_limit": 20,
    },
    "PREMIUM": {
        "monthly_credits": 180,
        "institution_limit": 12,
        "discipline_limit": 60,
        "source_limit": 200,
        "daily_limit": 60,
    },
}


def apply_paid_plan_limits():
    for code, values in PAID_PLAN_LIMITS.items():
        Plan.objects.filter(code=code).update(**values)
