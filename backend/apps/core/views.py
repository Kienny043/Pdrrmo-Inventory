"""
API views for the core app (spec Section 1 / 4).

- Reference-data endpoints: read-only, function-based, ``IsAuthenticated``.
- ``PersonnelViewSet``: the Personnel / Training Matrix CRUD surface,
  ADMIN-only (``permanent-delete`` additionally gated by
  ``can_permanently_delete``).
"""

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import reference
from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN, Role
from .models import (
    Category,
    InventoryItem,
    InventoryRequest,
    ItemHolderLog,
    ManualAttendee,
    Personnel,
    Staff,
    StockMovement,
    TrainingRecord,
    TrainingRegistration,
    TrainingSchedule,
    profile_for,
)
from .permissions import (
    CanPermanentlyDelete,
    IsAdmin,
    IsAdminOrReadOnly,
    _can_permanently_delete,
    _is_admin,
)
from .serializers import (
    AttendanceSerializer,
    CategorySerializer,
    InventoryItemSerializer,
    InventoryRequestSerializer,
    ItemHolderLogSerializer,
    ManualAttendeeSerializer,
    PersonnelSerializer,
    RequestDecisionSerializer,
    StaffSerializer,
    StockMovementSerializer,
    StockMovementWriteSerializer,
    TrainingRecordCellSerializer,
    TrainingRecordCellWriteSerializer,
    TrainingRegistrationSerializer,
    TrainingScheduleSerializer,
)
from .services import InsufficientStock, apply_stock_movement

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


@api_view(["GET"])
def me(request):
    """GET /api/me/ — the current user's identity + role flags for the SPA.

    The React equivalent of the ``context_processors.role`` template hook.
    """
    user = request.user
    is_admin = _is_admin(user)
    return Response(
        {
            "username": user.username,
            "role": Role.ADMIN if is_admin else Role.STAFF,
            "is_admin": is_admin,
            "can_permanently_delete": _can_permanently_delete(user),
        }
    )


@login_required
def home_page(request):
    """Send each role to a page it can actually use."""
    return redirect("personnel-matrix" if _is_admin(request.user) else "equipment-page")




@login_required
@ensure_csrf_cookie
def personnel_matrix_page(request):
    """Server-rendered shell for the personnel/training-matrix page (spec Section 5, page 1).

    Renders only the shell + guarantees the CSRF cookie; all data is loaded
    client-side from the DRF API. Non-admin users get a notice instead of the
    grid (every /api/personnel/ route is ADMIN-only). ``is_admin`` comes from
    the ``core.context_processors.role`` processor.
    """
    return render(request, "core/matrix.html")


@login_required
@ensure_csrf_cookie
def categories_page(request):
    """Shell for the Categories management page (spec Section 5, page 8). ADMIN-only."""
    return render(request, "core/categories.html")


@login_required
@ensure_csrf_cookie
def staff_page(request):
    """Shell for the Staff management page (spec Section 5, page 3). ADMIN-only."""
    return render(request, "core/staff.html")


@login_required
@ensure_csrf_cookie
def equipment_page(request):
    """Shell for the Equipment dashboard (spec Section 5, page 2).

    STAFF may view the table (read-only) + export CSV; ADMIN also gets
    add/edit/archive/holder-history. The template gates the buttons on the
    context processor's ``is_admin``.
    """
    return render(request, "core/equipment.html")


@login_required
@ensure_csrf_cookie
def movements_page(request):
    """Shell for the Stock movements page (spec Section 5, page 4). ADMIN-only."""
    return render(request, "core/movements.html")


@login_required
@ensure_csrf_cookie
def requests_page(request):
    """Shell for the Requests page (spec Section 5, page 5).

    STAFF see and create only their own requests; ADMIN see all and can
    approve/reject. The table gates the action column on ``is_admin``.
    """
    return render(request, "core/requests.html")


@login_required
@ensure_csrf_cookie
def trainings_page(request):
    """Shell for the Training schedules page (spec Section 5, page 6).

    STAFF see active schedules + can register/cancel; ADMIN also get
    create/edit/archive, the roster + attendance panel, and manual
    attendees. Everything gates on the context processor's is_admin /
    can_permanently_delete.
    """
    return render(request, "core/trainings.html")


@login_required
@ensure_csrf_cookie
def archived_page(request):
    """Shell for the Archived page (spec Section 5, page 7). ADMIN-only.

    Tabbed view over Items / Staff / Trainings / Personnel archived records;
    Restore for any admin, Permanent-delete only when
    ``can_permanently_delete`` (the button is hidden, not disabled).
    """
    return render(request, "core/archived.html")


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


# ==========================================================================
# Step 6b — stock integrity (spec Section 4, audit decisions 2.1 / 2.12)
# ==========================================================================


class StockMovementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/movements/ (?item=<id>) and POST /api/movements/add/ — ADMIN only.

    ``add`` calls services.apply_stock_movement directly; InsufficientStock
    surfaces as 400 with no partial writes (spec 2.1).
    """

    queryset = StockMovement.objects.select_related("item", "performed_by")
    serializer_class = StockMovementSerializer
    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        item_id = self.request.query_params.get("item")
        if item_id:
            qs = qs.filter(item_id=item_id)
        return qs

    @action(detail=False, methods=["post"], url_path="add")
    def add(self, request):
        write = StockMovementWriteSerializer(data=request.data)
        write.is_valid(raise_exception=True)
        data = write.validated_data
        try:
            movement = apply_stock_movement(
                data["item"],
                data["quantity"],
                data["movement_type"],
                performed_by=request.user,
                note=data["note"],
            )
        except InsufficientStock as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED
        )


class InventoryRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """GET/POST /api/requests/ and PATCH /api/requests/<pk>/approve/ (spec Section 4).

    STAFF sees and creates only their own requests; ADMIN sees all and decides.
    Approval deducts stock through the same atomic path as 2.1 (2.12).
    """

    serializer_class = InventoryRequestSerializer
    lookup_value_regex = r"\d+"
    pagination_class = None

    def get_permissions(self):
        if self.action == "approve":
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = InventoryRequest.objects.select_related(
            "item", "requested_by", "decided_by"
        )
        if not _is_admin(self.request.user):
            qs = qs.filter(requested_by=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(requested_by=self.request.user)

    @action(detail=True, methods=["patch"], url_path="approve")
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != InventoryRequest.Status.PENDING:
            return Response(
                {
                    "detail": (
                        f"Request is already {req.status}; "
                        "only a pending request can be decided."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        form = RequestDecisionSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        decision = form.validated_data["decision"]
        note = form.validated_data["note"]

        if decision == InventoryRequest.Status.REJECTED:
            req.status = InventoryRequest.Status.REJECTED
            req.decided_by = request.user
            req.decided_at = timezone.now()
            fields = ["status", "decided_by", "decided_at"]
            if note:
                req.note = (req.note + f"\n[Rejected: {note}]").strip()
                fields.append("note")
            req.save(update_fields=fields)
            return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)

        # APPROVED — deduct stock and decide in one transaction (2.12 reuses 2.1).
        movement_note = f"Request #{req.pk} approved by {request.user.username}"
        if note:
            movement_note += f": {note}"
        try:
            with transaction.atomic():
                apply_stock_movement(
                    req.item,
                    req.quantity,
                    StockMovement.MovementType.OUT,
                    performed_by=request.user,
                    note=movement_note,
                )
                req.status = InventoryRequest.Status.APPROVED
                req.decided_by = request.user
                req.decided_at = timezone.now()
                req.save(update_fields=["status", "decided_by", "decided_at"])
        except InsufficientStock as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(req).data, status=status.HTTP_200_OK)


# ==========================================================================
# Step 6c — training events + the attendance -> TrainingRecord bridge
# ==========================================================================


class TrainingScheduleViewSet(ArchiveLifecycleMixin, viewsets.ModelViewSet):
    """CRUD + archive lifecycle + registration + attendance (spec Section 4).

    STAFF may GET active trainings and self-register / cancel / view their own
    registrations; ADMIN manages schedules, the roster, and attendance.
    """

    serializer_class = TrainingScheduleSerializer
    lookup_value_regex = r"\d+"
    pagination_class = None
    archived_read_only_detail = "This training is archived; restore it before editing."

    _OPEN_STATUSES = (
        TrainingSchedule.Status.UPCOMING,
        TrainingSchedule.Status.ONGOING,
    )

    def get_permissions(self):
        if self.action == "permanent_delete":
            return [CanPermanentlyDelete()]
        if self.action in ("list", "retrieve"):
            return [IsAdminOrReadOnly()]
        if self.action in ("register", "cancel_registration", "my_registrations"):
            return [IsAuthenticated()]
        return [IsAdmin()]

    def get_queryset(self):
        qs = TrainingSchedule.objects.select_related("archived_by", "created_by")
        if self.action == "archived":
            return qs.filter(is_archived=True)
        if self.action != "list":
            return qs
        archived = (self.request.query_params.get("archived") or "").lower()
        if _is_admin(self.request.user) and archived in ("true", "1"):
            return qs.filter(is_archived=True)
        if _is_admin(self.request.user) and archived == "all":
            return qs
        return qs.filter(is_archived=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # --- registration (STAFF self-service) ---------------------------------

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        training = self.get_object()
        if training.is_archived or training.status not in self._OPEN_STATUSES:
            return Response(
                {"detail": "Registration is not open for this training."},
                status=status.HTTP_409_CONFLICT,
            )
        if (
            training.registration_deadline
            and training.registration_deadline < timezone.localdate()
        ):
            return Response(
                {"detail": "The registration deadline has passed."},
                status=status.HTTP_409_CONFLICT,
            )
        active = training.registrations.filter(
            status=TrainingRegistration.Status.REGISTERED
        )
        if training.max_slots is not None and active.count() >= training.max_slots:
            return Response(
                {"detail": "This training is full."},
                status=status.HTTP_409_CONFLICT,
            )
        if active.filter(user=request.user).exists():
            return Response(
                {"detail": "You are already registered for this training."},
                status=status.HTTP_409_CONFLICT,
            )
        reg = TrainingRegistration.objects.create(training=training, user=request.user)
        return Response(
            TrainingRegistrationSerializer(reg).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["delete"], url_path="cancel-registration")
    def cancel_registration(self, request, pk=None):
        training = self.get_object()
        reg = (
            training.registrations.filter(
                user=request.user, status=TrainingRegistration.Status.REGISTERED
            )
            .order_by("-registered_at")
            .first()
        )
        if reg is None:
            return Response(
                {"detail": "You have no active registration for this training."},
                status=status.HTTP_404_NOT_FOUND,
            )
        reg.status = TrainingRegistration.Status.CANCELLED
        reg.cancelled_at = timezone.now()
        reg.save(update_fields=["status", "cancelled_at"])
        return Response(TrainingRegistrationSerializer(reg).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="my-registrations")
    def my_registrations(self, request):
        qs = TrainingRegistration.objects.select_related("training", "user").filter(
            user=request.user
        )
        return Response(TrainingRegistrationSerializer(qs, many=True).data)

    # --- roster + attendance (ADMIN) -------------------------------------

    @action(detail=True, methods=["get"])
    def registrations(self, request, pk=None):
        training = self.get_object()
        qs = training.registrations.select_related("user", "training").all()
        return Response(TrainingRegistrationSerializer(qs, many=True).data)

    @action(detail=True, methods=["patch"], url_path=r"attendance/(?P<user_id>\d+)")
    def attendance(self, request, pk=None, user_id=None):
        """Toggle a registered user's attendance; upsert their TrainingRecord
        when the training carries a matrix_training_key (spec 2.4)."""
        training = self.get_object()
        reg = (
            training.registrations.filter(user_id=user_id)
            .order_by("-registered_at")
            .first()
        )
        if reg is None:
            return Response(
                {"detail": "That user has no registration for this training."},
                status=status.HTTP_404_NOT_FOUND,
            )
        form = AttendanceSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        attended = form.validated_data["attended"]
        reg.attended = attended
        reg.save(update_fields=["attended"])

        matrix_updated = False
        matrix_reason = None
        if attended and training.matrix_training_key:
            personnel = Personnel.objects.filter(user_id=user_id).first()
            year = training.date_start.year
            if personnel is None:
                matrix_reason = "the attending user has no linked Personnel record"
            elif not TRAINING_YEAR_MIN <= year <= TRAINING_YEAR_MAX:
                matrix_reason = f"training year {year} is outside the matrix range"
            else:
                TrainingRecord.objects.update_or_create(
                    personnel=personnel,
                    training_key=training.matrix_training_key,
                    defaults={"year_attained": year},
                )
                matrix_updated = True
        elif attended:
            matrix_reason = "the training has no matrix_training_key"

        data = TrainingRegistrationSerializer(reg).data
        data["matrix_updated"] = matrix_updated
        if attended and not matrix_updated:
            data["matrix_reason"] = matrix_reason
        return Response(data)


class ManualAttendeeViewSet(viewsets.ViewSet):
    """Nested manual-attendee routes under a training (spec Section 4, 2.8).

    ADMIN only. No soft-delete on this model, so DELETE is a hard delete.
    Attendance here is a plain toggle — no TrainingRecord upsert (a manual
    attendee has no linked account).
    """

    permission_classes = [IsAdmin]

    def _training(self, training_pk):
        return get_object_or_404(TrainingSchedule, pk=training_pk)

    def _attendee(self, training_pk, pk):
        return get_object_or_404(ManualAttendee, pk=pk, training_id=training_pk)

    def list(self, request, training_pk=None):
        self._training(training_pk)
        qs = ManualAttendee.objects.filter(training_id=training_pk)
        return Response(ManualAttendeeSerializer(qs, many=True).data)

    def create(self, request, training_pk=None):
        training = self._training(training_pk)
        serializer = ManualAttendeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(training=training)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, training_pk=None, pk=None):
        self._attendee(training_pk, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def set_attendance(self, request, training_pk=None, pk=None):
        attendee = self._attendee(training_pk, pk)
        form = AttendanceSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        attendee.attended = form.validated_data["attended"]
        attendee.save(update_fields=["attended"])
        return Response(ManualAttendeeSerializer(attendee).data)
