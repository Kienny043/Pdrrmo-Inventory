"""Django admin registration for every core model (spec 2.9).

The admin is an internal fallback UI. It uses Django's own auth
(``is_staff`` + ``is_superuser`` / model permissions) — unrelated to the
DRF ``IsAdmin`` / ``CanPermanentlyDelete`` API permission classes.

Fields that are only ever set by the API's atomic or lifecycle paths are
read-only here so the admin can't silently break an invariant or falsify
an audit trail:
  - archive triple (is_archived / archived_at / archived_by)
  - audit FKs (performed_by / decided_by / archived_by / created_by)
  - lifecycle-driven fields (InventoryRequest.status/decided_*,
    TrainingRegistration.status/attended/cancelled_at)
  - StockMovement and ItemHolderLog are wholly view-only (a manual edit
    would bypass services.apply_stock_movement, spec 2.1).
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Category,
    InventoryItem,
    InventoryRequest,
    ItemHolderLog,
    ManualAttendee,
    Personnel,
    PersonnelAttendee,
    Staff,
    StockMovement,
    TrainingRecord,
    TrainingRegistration,
    TrainingSchedule,
    UserProfile,
)

_ARCHIVE_TRIPLE = ("is_archived", "archived_at", "archived_by")


class ReadOnlyTabularInline(admin.TabularInline):
    """A tabular inline for browsing only — no add / change / delete."""

    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# --------------------------------------------------------------------------
# Inventory core
# --------------------------------------------------------------------------


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "item_count", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")

    class _ItemInline(ReadOnlyTabularInline):
        model = InventoryItem
        fields = ("name", "brand", "quantity", "condition", "is_archived")
        readonly_fields = fields

    inlines = [_ItemInline]

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "department", "status", "is_archived")
    list_filter = ("status", "is_archived", "department")
    search_fields = ("first_name", "last_name", "position", "contact")
    readonly_fields = _ARCHIVE_TRIPLE + ("created_at", "updated_at")

    @admin.display(description="Name", ordering="last_name")
    def full_name(self, obj):
        return obj.full_name


class StockMovementInline(ReadOnlyTabularInline):
    model = StockMovement
    fields = ("movement_type", "quantity", "note", "performed_by", "created_at")
    readonly_fields = fields
    ordering = ("-created_at",)


class ItemHolderLogInline(ReadOnlyTabularInline):
    model = ItemHolderLog
    fields = ("action", "staff", "performed_by", "timestamp", "note")
    readonly_fields = fields
    ordering = ("-timestamp",)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "brand", "quantity", "unit", "condition",
        "memorandum_receipt", "is_archived",
    )
    list_filter = ("category", "condition", "is_archived")
    search_fields = ("name", "brand", "remarks")
    list_select_related = ("category", "memorandum_receipt")
    autocomplete_fields = ("category", "memorandum_receipt")
    inlines = [StockMovementInline, ItemHolderLogInline]

    _base_readonly = _ARCHIVE_TRIPLE + ("created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        ro = list(self._base_readonly)
        if obj is not None:
            # quantity is create-only; thereafter it moves through
            # /api/movements/add/ or request approval (spec 2.1).
            ro.append("quantity")
        return ro


@admin.register(ItemHolderLog)
class ItemHolderLogAdmin(admin.ModelAdmin):
    list_display = ("item", "action", "staff", "performed_by", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("item__name", "staff__first_name", "staff__last_name", "note")
    list_select_related = ("item", "staff", "performed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("item", "movement_type", "quantity", "performed_by", "created_at")
    list_filter = ("movement_type", "created_at")
    search_fields = ("item__name", "note")
    list_select_related = ("item", "performed_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InventoryRequest)
class InventoryRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id", "requested_by", "item", "quantity", "status", "decided_by", "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("requested_by__username", "item__name", "note")
    list_select_related = ("requested_by", "item", "decided_by")
    autocomplete_fields = ("item",)
    # decisions go through PATCH /api/requests/<pk>/approve/ (spec 2.12)
    readonly_fields = ("status", "decided_by", "decided_at", "created_at")


# --------------------------------------------------------------------------
# Training events
# --------------------------------------------------------------------------


class TrainingRegistrationInline(admin.TabularInline):
    model = TrainingRegistration
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "status", "attended", "registered_at", "cancelled_at")
    readonly_fields = ("status", "attended", "registered_at", "cancelled_at")


class ManualAttendeeInline(admin.TabularInline):
    model = ManualAttendee
    extra = 0
    fields = ("name", "designation", "municipality", "org_affiliation", "attended")


@admin.register(TrainingSchedule)
class TrainingScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "title", "date_start", "status", "matrix_training_key",
        "max_slots", "is_archived", "created_by",
    )
    list_filter = ("status", "is_archived", "date_start")
    search_fields = ("title", "venue", "description")
    list_select_related = ("created_by",)
    inlines = [TrainingRegistrationInline, ManualAttendeeInline]
    readonly_fields = _ARCHIVE_TRIPLE + ("created_by", "created_at", "updated_at")


@admin.register(TrainingRegistration)
class TrainingRegistrationAdmin(admin.ModelAdmin):
    list_display = ("training", "user", "status", "attended", "registered_at")
    list_filter = ("status", "attended", "registered_at")
    search_fields = ("training__title", "user__username")
    list_select_related = ("training", "user")
    autocomplete_fields = ("training", "user")
    # status/attended change via register/cancel/attendance endpoints
    readonly_fields = ("status", "attended", "registered_at", "cancelled_at")


@admin.register(ManualAttendee)
class ManualAttendeeAdmin(admin.ModelAdmin):
    list_display = ("name", "training", "municipality", "org_affiliation", "attended")
    list_filter = ("org_affiliation", "municipality", "attended")
    search_fields = ("name", "designation", "training__title")
    list_select_related = ("training",)
    autocomplete_fields = ("training",)
    readonly_fields = ("created_at",)


@admin.register(PersonnelAttendee)
class PersonnelAttendeeAdmin(admin.ModelAdmin):
    list_display = ("personnel", "training", "attended", "added_by", "added_at")
    list_filter = ("attended", "training")
    search_fields = ("personnel__name", "training__title")
    list_select_related = ("personnel", "training", "added_by")
    autocomplete_fields = ("training", "personnel")
    # attendance flows through the API's matrix bridge; added_by/added_at are audit
    readonly_fields = ("added_by", "added_at")


# --------------------------------------------------------------------------
# Personnel / training matrix
# --------------------------------------------------------------------------


class TrainingRecordInline(admin.TabularInline):
    model = TrainingRecord
    extra = 0
    fields = ("training_key", "year_attained", "updated_at")
    readonly_fields = ("updated_at",)


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = (
        "name", "designation", "municipality", "district",
        "org_affiliation", "employment_status", "is_archived",
    )
    list_filter = ("org_affiliation", "municipality", "is_archived")
    search_fields = ("name", "designation", "employment_status", "other_drr_training")
    # `user` stays editable — the admin is the account-linking UI (the API
    # has no linking endpoint).
    autocomplete_fields = ("user",)
    inlines = [TrainingRecordInline]
    readonly_fields = ("district",) + _ARCHIVE_TRIPLE + ("created_at", "updated_at")

    @admin.display(description="District")
    def district(self, obj):
        try:
            return obj.district
        except KeyError:
            return "—"


@admin.register(TrainingRecord)
class TrainingRecordAdmin(admin.ModelAdmin):
    list_display = ("personnel", "training_key", "year_attained", "updated_at")
    list_filter = ("training_key", "year_attained")
    search_fields = ("personnel__name",)
    list_select_related = ("personnel",)
    autocomplete_fields = ("personnel",)
    readonly_fields = ("updated_at",)


# --------------------------------------------------------------------------
# UserProfile — role assignment (also inlined on the User page)
# --------------------------------------------------------------------------


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "can_permanently_delete")
    list_filter = ("role", "can_permanently_delete")
    search_fields = ("user__username",)
    list_select_related = ("user",)
    autocomplete_fields = ("user",)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name_plural = "core profile"
    fields = ("role", "can_permanently_delete")


class UserAdmin(DjangoUserAdmin):
    inlines = [UserProfileInline]
    list_display = DjangoUserAdmin.list_display + ("core_role",)

    @admin.display(description="Core role")
    def core_role(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.role if profile else "—"


admin.site.unregister(get_user_model())
admin.site.register(get_user_model(), UserAdmin)
