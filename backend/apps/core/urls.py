"""Reference-data URL routes, mounted under /api/ by config/urls.py."""

from django.urls import path

from . import views

urlpatterns = [
    path("municipalities/", views.municipalities_list, name="municipalities-list"),
    path("training-catalog/", views.training_catalog_list, name="training-catalog-list"),
]
