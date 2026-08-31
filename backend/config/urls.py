"""Root URLconf.

The frontend is a React SPA (``frontend/``). In production Django + whitenoise
serves the built bundle from ``frontend/dist/`` (index.html + ``/assets/*``);
in development the Vite server serves it and proxies ``/api`` + ``/admin`` here.
Everything the SPA needs from Django is under ``/api/`` and ``/admin/``.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
]

# Serve uploaded media (Staff photos, Item images) in local dev.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# SPA catch-all — anything not claimed above (and not served by whitenoise as a
# real file) renders index.html so React Router handles the client-side route,
# including direct loads and refreshes of deep links.
urlpatterns += [
    re_path(
        r"^(?!api/|admin/|media/|static/).*$",
        TemplateView.as_view(template_name="index.html"),
        name="spa",
    ),
]
