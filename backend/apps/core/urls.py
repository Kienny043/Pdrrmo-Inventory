"""Core app URL routes, mounted under /api/ by config/urls.py."""

from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("personnel", views.PersonnelViewSet, basename="personnel")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("staff", views.StaffViewSet, basename="staff")
router.register("items", views.InventoryItemViewSet, basename="item")

urlpatterns = [
    path("municipalities/", views.municipalities_list, name="municipalities-list"),
    path("training-catalog/", views.training_catalog_list, name="training-catalog-list"),
    *router.urls,
]
