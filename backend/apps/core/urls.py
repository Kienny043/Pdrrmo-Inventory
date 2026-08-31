"""Core app URL routes, mounted under /api/ by config/urls.py."""

from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = SimpleRouter()
router.register("personnel", views.PersonnelViewSet, basename="personnel")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("staff", views.StaffViewSet, basename="staff")
router.register("items", views.InventoryItemViewSet, basename="item")
router.register("movements", views.StockMovementViewSet, basename="movement")
router.register("requests", views.InventoryRequestViewSet, basename="request")
router.register("trainings", views.TrainingScheduleViewSet, basename="training")

# Manual attendees are nested under a training (spec Section 4). Explicit
# path() entries rather than a nested-router dependency.
_ma = views.ManualAttendeeViewSet
manual_attendee_list = _ma.as_view({"get": "list", "post": "create"})
manual_attendee_detail = _ma.as_view({"delete": "destroy"})
manual_attendee_attendance = _ma.as_view({"patch": "set_attendance"})

# Personnel-roster attendees — same nested shape, FK'd to an existing Personnel.
_pa = views.PersonnelAttendeeViewSet
personnel_attendee_list = _pa.as_view({"get": "list", "post": "create"})
personnel_attendee_detail = _pa.as_view({"delete": "destroy"})
personnel_attendee_attendance = _pa.as_view({"patch": "set_attendance"})

urlpatterns = [
    # --- auth for the React SPA ---
    path("token/", TokenObtainPairView.as_view(), name="token-obtain-pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.me, name="me"),
    # --- reference data ---
    path("municipalities/", views.municipalities_list, name="municipalities-list"),
    path("training-catalog/", views.training_catalog_list, name="training-catalog-list"),
    path(
        "trainings/<int:training_pk>/manual-attendees/",
        manual_attendee_list,
        name="manual-attendee-list",
    ),
    path(
        "trainings/<int:training_pk>/manual-attendees/<int:pk>/",
        manual_attendee_detail,
        name="manual-attendee-detail",
    ),
    path(
        "trainings/<int:training_pk>/manual-attendees/<int:pk>/attendance/",
        manual_attendee_attendance,
        name="manual-attendee-attendance",
    ),
    path(
        "trainings/<int:training_pk>/personnel-attendees/",
        personnel_attendee_list,
        name="personnel-attendee-list",
    ),
    path(
        "trainings/<int:training_pk>/personnel-attendees/<int:pk>/",
        personnel_attendee_detail,
        name="personnel-attendee-detail",
    ),
    path(
        "trainings/<int:training_pk>/personnel-attendees/<int:pk>/attendance/",
        personnel_attendee_attendance,
        name="personnel-attendee-attendance",
    ),
    *router.urls,
]
