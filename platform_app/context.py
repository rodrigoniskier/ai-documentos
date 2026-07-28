from django.conf import settings


PUBLIC_SUPPORT_EMAIL = "backuprodrigoniskier@gmail.com"


def platform(request):
    site_url = settings.PUBLIC_BASE_URL or request.build_absolute_uri("/").rstrip("/")
    return {
        "support_email": PUBLIC_SUPPORT_EMAIL,
        "site_url": site_url,
        "canonical_url": f"{site_url}{request.path}",
        "social_image_url": f"{site_url}/social-card.png",
    }
