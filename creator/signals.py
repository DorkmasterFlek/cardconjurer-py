from allauth.socialaccount import app_settings
from allauth.socialaccount.signals import social_account_added, social_account_updated
from django.dispatch import receiver


@receiver([social_account_added, social_account_updated])
def social_account_login_receiver(request, sociallogin, **kwargs):
    """Check if a social account is a staff and/or superuser when they log in."""

    settings = app_settings.PROVIDERS.get(sociallogin.account.provider, {})
    staff_uids = settings.get('STAFF_UIDS')
    superuser_uids = settings.get('SUPERUSER_UIDS')

    uid = sociallogin.account.uid
    is_superuser = superuser_uids and uid in superuser_uids
    is_staff = is_superuser or (staff_uids and uid in staff_uids)

    if is_staff or is_superuser:
        if is_staff:
            request.user.is_staff = True
        if is_superuser:
            request.user.is_superuser = True

        request.user.save()
