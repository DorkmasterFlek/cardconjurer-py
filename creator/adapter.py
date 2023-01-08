from allauth.account.adapter import DefaultAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from allauth.socialaccount import app_settings
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    """Disable new user signups for regular accounts."""

    def is_open_for_signup(self, request):
        return False


class NewSocialUserAccountAdapter(DefaultSocialAccountAdapter):
    """
    Adapter to check new social users attempting to sign up.
    """

    def pre_social_login(self, request, socialaccount):
        """Check if the social provider has restricted UID settings."""

        allowed_uids = app_settings.PROVIDERS.get(socialaccount.account.provider, {}).get("ALLOWED_UIDS")
        if allowed_uids is not None and socialaccount.account.uid not in allowed_uids:
            messages.error(request, "Sorry, you cannot access this site.")
            raise ImmediateHttpResponse(HttpResponseRedirect(settings.LOGIN_URL))

    def is_open_for_signup(self, request, socialaccount):
        # Need to override True here because it normally calls the default handler (above which is False).
        return True
