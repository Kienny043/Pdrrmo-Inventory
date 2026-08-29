"""Server-rendered page routes (mounted at / by config/urls.py).

Kept separate from urls.py (the /api/ router) so the DRF surface and the
plain-template pages don't share a prefix.
"""

from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="personnel-matrix", permanent=False)),
    path("personnel/", views.personnel_matrix_page, name="personnel-matrix"),
]
