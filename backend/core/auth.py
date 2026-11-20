"""
allauth adapters.

Our User model has a single `name` field rather than Django's first_name /
last_name pair, so both adapters are here to populate it correctly , otherwise
a Google or GitHub sign-in produces a user with a blank display name.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


def _display_name(data):
    """Best available human name from a provider's `extra_data`."""
    for key in ("name", "full_name", "login"):
        value = (data.get(key) or "").strip()
        if value:
            return value[:150]

    first = (data.get("given_name") or data.get("first_name") or "").strip()
    last = (data.get("family_name") or data.get("last_name") or "").strip()
    return f"{first} {last}".strip()[:150]


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        user.email = (user.email or "").strip().lower()
        if not user.name:
            user.name = user.email.split("@")[0]
        if commit:
            user.save()
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.email = (user.email or data.get("email") or "").strip().lower()
        user.name = _display_name({**data, **(sociallogin.account.extra_data or {})})
        if not user.name and user.email:
            user.name = user.email.split("@")[0]
        return user
