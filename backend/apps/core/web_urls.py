"""Server-rendered page routes (mounted at / by config/urls.py).

Kept separate from urls.py (the /api/ router) so the DRF surface and the
plain-template pages don't share a prefix. Pages not yet built in Step 7
point at ``coming_soon_page`` so the shared nav can link them all now.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home_page, name="home"),
    path("personnel/", views.personnel_matrix_page, name="personnel-matrix"),
    path("categories/", views.categories_page, name="categories-page"),
    path("staff/", views.staff_page, name="staff-page"),
    path("equipment/", views.equipment_page, name="equipment-page"),
    path("movements/", views.movements_page, name="movements-page"),
    path("requests/", views.requests_page, name="requests-page"),
    path("trainings/", views.trainings_page, name="trainings-page"),
    # Built in the last Step 7 sub-step:
    path("archived/", views.coming_soon_page, name="archived-page"),
]
