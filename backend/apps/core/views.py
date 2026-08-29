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
from .models import (
    Category,
    InventoryItem,
    ItemHolderLog,
    Personnel,
    Staff,
    TrainingRecord,
    profile_for,
)
from .permissions import CanPermanentlyDelete, IsAdmin, IsAdminOrReadOnly
from .serializers import (
    CategorySerializer,
    InventoryItemSerializer,
    ItemHolderLogSerializer,
    PersonnelSerializer,
    StaffSerializer,
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


# ==========================================================================
# Step 6a — catalog + custody CRUD (spec Section 4)
# ==========================================================================


def _truthy(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class ArchiveLifecycleMixin:
    """Shared soft-archive lifecycle for models with the is_archived triple.

    - list                             -> active rows only
    - GET  <resource>/archived/        -> archived rows only
    - DELETE <resource>/<pk>/          -> soft-archive (idempotent 200)
    - POST <resource>/<pk>/restore/    -> un-archive (idempotent 200)
    - DELETE <resource>/<pk>/permanent-delete/ -> hard delete, 409 unless archived
    - PATCH on an archived row -> 409

    Subclass sets ``queryset`` + ``archived_read_only_detail`` and returns
    ``CanPermanentlyDelete`` for the ``permanent_delete`` action.
    """

    archived_read_only_detail = "This record is archived; restore it before editing."
    _archive_fields = ["is_archived", "archived_at", "archived_by", "updated_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "list":
            return qs.filter(is_archived=False)
        if self.action == "archived":
            return qs.filter(is_archived=True)
        return qs

    def update(self, request, *args, **kwargs):
        if self.get_object().is_archived:
            return Response(
                {"detail": self.archived_read_only_detail},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.is_archived:
            obj.is_archived = True
            obj.archived_at = timezone.now()
            obj.archived_by = request.user
            obj.save(update_fields=self._archive_fields)
        return Response(self.get_serializer(obj).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def archived(self, request):
        data = self.get_serializer(self.get_queryset(), many=True).data
        return Response(data)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        obj = self.get_object()
        if obj.is_archived:
            obj.is_archived = False
            obj.archived_at = None
            obj.archived_by = None
            obj.save(update_fields=self._archive_fields)
        return Response(self.get_serializer(obj).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="permanent-delete")
    def permanent_delete(self, request, pk=None):
        obj = self.get_object()
        if not obj.is_archived:
            return Response(
                {"detail": "Archive this record before permanently deleting it."},
                status=status.HTTP_409_CONFLICT,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(viewsets.ModelViewSet):
    """GET/POST /api/categories/, GET/PATCH/DELETE /api/categories/<pk>/ — ADMIN only.

    No archive lifecycle (spec 3.1 gives Category no is_archived); DELETE is a
    hard delete, refused with 409 while the category still has items.
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdmin]
    lookup_value_regex = r"\d+"
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        n = category.items.count()
        if n:
            return Response(
                {"detail": f"Category still has {n} item(s); reassign or delete them first."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class StaffViewSet(ArchiveLifecycleMixin, viewsets.ModelViewSet):
    """CRUD + archive lifecycle for Staff — ADMIN only (permanent-delete elevated)."""

    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    lookup_value_regex = r"\d+"
    pagination_class = None
    archived_read_only_detail = "This staff record is archived; restore it before editing."

    def get_permissions(self):
        if self.action == "permanent_delete":
            return [CanPermanentlyDelete()]
        return [IsAdmin()]

    def update(self, request, *args, **kwargs):
        # 2.7: honour remove_photo before the serializer runs. Only meaningful
        # on an editable record; the archived guard lives in the mixin update()
        # that super() calls next.
        instance = self.get_object()
        if not instance.is_archived and _truthy(request.data.get("remove_photo")):
            if instance.photo:
                instance.photo.delete(save=False)
            instance.photo = None
            instance.save(update_fields=["photo", "updated_at"])
        return super().update(request, *args, **kwargs)


class InventoryItemViewSet(ArchiveLifecycleMixin, viewsets.ModelViewSet):
    """CRUD + archive lifecycle + holder-log auto-write + holder-history (spec Section 4).

    STAFF may GET the active list/detail (to build an equipment request); every
    write, plus /archived/ and /holder-history/, is ADMIN.
    """

    queryset = InventoryItem.objects.select_related("category", "memorandum_receipt")
    serializer_class = InventoryItemSerializer
    lookup_value_regex = r"\d+"
    pagination_class = None
    archived_read_only_detail = "This item is archived; restore it before editing."

    def get_permissions(self):
        if self.action == "permanent_delete":
            return [CanPermanentlyDelete()]
        if self.action in ("list", "retrieve"):
            return [IsAdminOrReadOnly()]
        return [IsAdmin()]

    def _holder_note(self):
        return str(self.request.data.get("holder_note", "")).strip()

    def perform_create(self, serializer):
        with transaction.atomic():
            item = serializer.save()
            if item.memorandum_receipt_id:
                ItemHolderLog.objects.create(
                    item=item,
                    staff=item.memorandum_receipt,
                    action=ItemHolderLog.Action.ASSIGNED,
                    performed_by=self.request.user,
                    note=self._holder_note(),
                )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_archived:
            return Response(
                {"detail": self.archived_read_only_detail},
                status=status.HTTP_409_CONFLICT,
            )
        old_holder_id = instance.memorandum_receipt_id
        with transaction.atomic():
            response = super().update(request, *args, **kwargs)
            instance.refresh_from_db()
            new_holder_id = instance.memorandum_receipt_id
            if new_holder_id != old_holder_id:
                note = self._holder_note()
                if old_holder_id:
                    ItemHolderLog.objects.create(
                        item=instance,
                        staff_id=old_holder_id,
                        action=ItemHolderLog.Action.REMOVED,
                        performed_by=request.user,
                        note=note,
                    )
                if new_holder_id:
                    ItemHolderLog.objects.create(
                        item=instance,
                        staff_id=new_holder_id,
                        action=ItemHolderLog.Action.ASSIGNED,
                        performed_by=request.user,
                        note=note,
                    )
        return response

    @action(detail=True, methods=["get"], url_path="holder-history")
    def holder_history(self, request, pk=None):
        item = self.get_object()
        logs = item.holder_logs.select_related("staff", "performed_by").all()
        return Response(ItemHolderLogSerializer(logs, many=True).data)
