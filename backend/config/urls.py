"""Root URL configuration for the BiasHawk backend."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    # allauth headless: email/password, Google and GitHub, session-cookie based.
    # Browser endpoints live under /_allauth/browser/v1/.
    path("_allauth/", include("allauth.headless.urls")),
    # Required even with HEADLESS_ONLY. The OAuth provider sends the browser
    # back to Django's own callback view, and the provider reverses that URL
    # name to build redirect_uri , without this, starting a social login fails
    # with NoReverseMatch for '<provider>_callback'.
    path("accounts/", include("allauth.urls")),
]
