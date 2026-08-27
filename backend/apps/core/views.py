"""
Read-only reference-data endpoints (spec Section 1 / 4).

Both return static data built from ``reference.py`` — no models, no
serializers, no database access. They keep the project-wide default
permission (``IsAuthenticated``); the frontend calls them after login.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import reference


@api_view(["GET"])
def municipalities_list(request):
    """GET /api/municipalities/ — [{name, district}], district First->Fourth then name."""
    data = [
        {"name": name, "district": district}
        for name, district in reference.municipalities_by_district_then_name()
    ]
    return Response(data)


@api_view(["GET"])
def training_catalog_list(request):
    """GET /api/training-catalog/ — [{key, label, group}], MANAGERIAL block then SKILLS."""
    data = [
        {"key": key, "label": label, "group": group}
        for key, label, group in reference.training_catalog_rows()
    ]
    return Response(data)
