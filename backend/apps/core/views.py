"""
API views for the core app (spec Section 1 / 4).

- Reference-data endpoints: read-only, function-based, ``IsAuthenticated``.
- ``PersonnelViewSet``: the Personnel / Training Matrix CRUD surface,
  ADMIN-only (``permanent-delete`` additionally gated by
  ``can_permanently_delete``).
"""

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from . import reference
from .choices import Role
from .models import Personnel, TrainingRecord, profile_for
from .permissions import CanPermanentlyDelete, IsAdmin
from .serializers import (
    PersonnelSerializer,
    TrainingRecordCellSerializer,
    TrainingRecordCellWriteSerializer,
)

_ARCHIVE_FIELDS = ["is_archived", "archived_at", "archived_by", "updated_at"]
_ARCHIVED_READ_ONLY = {
    "detail": "This personnel record is archived; restore it before editing."
}


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


@login_required
@ensure_csrf_cookie
def personnel_matrix_page(request):
    """Server-rendered shell for the personnel/training-matrix page (spec Section 5, page 1).

    Renders only the shell + guarantees the CSRF cookie; all data is loaded
    client-side from the DRF API. Non-admin users get a notice instead of the
    grid (every /api/personnel/ route is ADMIN-only).
    """
    profile = profile_for(request.user)
    is_admin = request.user.is_superuser or profile.role == Role.ADMIN
    return render(request, "core/matrix.html", {"is_admin": is_admin})


class PersonnelViewSet(viewsets.ModelViewSet):
    """CRUD + archive lifecycle + matrix-cell upsert for Personnel (spec Section 4).

    Routes (all ADMIN-only; permanent-delete needs can_permanently_delete):
      GET/POST   /api/personnel/                         list (filtered) / create
      GET/PATCH  /api/personnel/<pk>/                    retrieve / partial update
      DELETE     /api/personnel/<pk>/                    soft-archive (idempotent)
      POST       /api/personnel/<pk>/restore/           un-archive (idempotent)
      DELETE     /api/personnel/<pk>/permanent-delete/  hard delete (must be archived)
      PATCH      /api/personnel/<pk>/training-record/<training_key>/  upsert / clear one cell
    """

    serializer_class = PersonnelSerializer
    lookup_value_regex = r"\d+"
    pagination_class = None

    def get_permissions(self):
        if self.action == "permanent_delete":
            return [CanPermanentlyDelete()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = Personnel.objects.all().prefetch_related("training_records")
        if self.action != "list":
            # detail routes and custom actions must see archived rows too.
            return qs

        params = self.request.query_params

        archived = (params.get("archived") or "").lower()
        if archived in ("true", "1"):
            qs = qs.filter(is_archived=True)
        elif archived == "all":
            pass
        else:
            # absent, "false", "0", or any unrecognised value -> active only
            qs = qs.filter(is_archived=False)

        municipality = params.get("municipality")
        if municipality is not None:
            qs = qs.filter(municipality=municipality)

        district = params.get("district")
        if district is not None:
            qs = qs.filter(municipality__in=reference.municipalities_in(district))

        return qs

    # --- editing guards -------------------------------------------------

    def update(self, request, *args, **kwargs):
        # covers PATCH (partial_update delegates here)
        if self.get_object().is_archived:
            return Response(_ARCHIVED_READ_ONLY, status=status.HTTP_409_CONFLICT)
        return super().update(request, *args, **kwargs)

    # --- archive lifecycle -------------------------------------------------

    def destroy(self, request, *args, **kwargs):
        """DELETE /api/personnel/<pk>/ — soft-archive. Idempotent no-op if already archived."""
        personnel = self.get_object()
        if not personnel.is_archived:
            personnel.is_archived = True
            personnel.archived_at = timezone.now()
            personnel.archived_by = request.user
            personnel.save(update_fields=_ARCHIVE_FIELDS)
        return Response(self.get_serializer(personnel).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """POST /api/personnel/<pk>/restore/ — un-archive. Idempotent no-op if already active."""
        personnel = self.get_object()
        if personnel.is_archived:
            personnel.is_archived = False
            personnel.archived_at = None
            personnel.archived_by = None
            personnel.save(update_fields=_ARCHIVE_FIELDS)
        return Response(self.get_serializer(personnel).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="permanent-delete")
    def permanent_delete(self, request, pk=None):
        """DELETE /api/personnel/<pk>/permanent-delete/ — hard delete. 409 unless archived first."""
        personnel = self.get_object()
        if not personnel.is_archived:
            return Response(
                {"detail": "Archive this personnel record before permanently deleting it."},
                status=status.HTTP_409_CONFLICT,
            )
        personnel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- matrix cell upsert / clear -------------------------------------

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"training-record/(?P<training_key>[^/.]+)",
    )
    def training_record(self, request, pk=None, training_key=None):
        """PATCH one matrix cell: {year_attained: <int>} upserts (200), {year_attained: null} clears (204)."""
        personnel = self.get_object()
        if training_key not in reference.VALID_TRAINING_KEYS:
            return Response({"detail": "Unknown training key."}, status=status.HTTP_404_NOT_FOUND)
        if personnel.is_archived:
            return Response(_ARCHIVED_READ_ONLY, status=status.HTTP_409_CONFLICT)

        write = TrainingRecordCellWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        year = write.validated_data["year_attained"]

        if year is None:
            TrainingRecord.objects.filter(
                personnel=personnel, training_key=training_key
            ).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        record = self._upsert_cell(personnel, training_key, year)
        return Response(TrainingRecordCellSerializer(record).data, status=status.HTTP_200_OK)

    @staticmethod
    def _upsert_cell(personnel, training_key, year):
        """update_or_create the cell; if a concurrent insert wins the race, fall back to update."""
        try:
            with transaction.atomic():
                record, _created = TrainingRecord.objects.update_or_create(
                    personnel=personnel,
                    training_key=training_key,
                    defaults={"year_attained": year},
                )
            return record
        except IntegrityError:
            record = TrainingRecord.objects.get(
                personnel=personnel, training_key=training_key
            )
            record.year_attained = year
            record.save(update_fields=["year_attained", "updated_at"])
            return record
