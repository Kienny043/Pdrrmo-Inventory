"""Serializers for the core CRUD surface (spec Section 4)."""

from rest_framework import serializers

from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from .models import (
    Category,
    InventoryItem,
    InventoryRequest,
    ItemHolderLog,
    Personnel,
    Staff,
    StockMovement,
    TrainingRecord,
)


class TrainingRecordCellSerializer(serializers.ModelSerializer):
    """One matrix cell, read-only — always embedded in Personnel responses."""

    class Meta:
        model = TrainingRecord
        fields = ["training_key", "year_attained", "updated_at"]
        read_only_fields = fields


class PersonnelSerializer(serializers.ModelSerializer):
    # Computed from municipality via the reference lookup — never writable.
    district = serializers.ReadOnlyField()
    # Read-only; archive transitions happen only through DELETE / restore.
    archived_by = serializers.SlugRelatedField(slug_field="username", read_only=True)
    training_records = TrainingRecordCellSerializer(many=True, read_only=True)

    class Meta:
        model = Personnel
        fields = [
            "id",
            "name",
            "designation",
            "org_affiliation",
            "employment_status",
            "municipality",
            "district",
            "other_drr_training",
            "is_archived",
            "archived_at",
            "archived_by",
            "created_at",
            "updated_at",
            "training_records",
        ]
        # district / archived_by / training_records are already declared
        # read-only above; these are the remaining model-derived ones.
        read_only_fields = ["is_archived", "archived_at", "created_at", "updated_at"]


class TrainingRecordCellWriteSerializer(serializers.Serializer):
    """Body for PATCH .../training-record/<training_key>/.

    ``year_attained`` is an int in range to upsert the cell, or ``null`` to
    clear it. The key must be present in the payload.
    """

    year_attained = serializers.IntegerField(
        allow_null=True,
        min_value=TRAINING_YEAR_MIN,
        max_value=TRAINING_YEAR_MAX,
    )


# --------------------------------------------------------------------------
# Step 6a — catalog + custody (Category, Staff, InventoryItem, ItemHolderLog)
# --------------------------------------------------------------------------


class CategorySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "description", "item_count", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def get_item_count(self, obj):
        return obj.items.count()


class StaffSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    archived_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "position",
            "department",
            "contact",
            "status",
            "photo",
            "is_archived",
            "archived_at",
            "archived_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["is_archived", "archived_at", "created_at", "updated_at"]


class ItemHolderLogSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    performed_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = ItemHolderLog
        fields = [
            "id",
            "item",
            "staff",
            "staff_name",
            "action",
            "performed_by",
            "timestamp",
            "note",
        ]
        read_only_fields = fields

    def get_staff_name(self, obj):
        return obj.staff.full_name if obj.staff else None


class InventoryItemSerializer(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField()
    memorandum_receipt_name = serializers.SerializerMethodField()
    archived_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "brand",
            "description",
            "image",
            "quantity",
            "unit",
            "date_acquired",
            "memorandum_receipt",
            "memorandum_receipt_name",
            "condition",
            "remarks",
            "is_archived",
            "archived_at",
            "archived_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["is_archived", "archived_at", "created_at", "updated_at"]

    def get_category_name(self, obj):
        return obj.category.name

    def get_memorandum_receipt_name(self, obj):
        return obj.memorandum_receipt.full_name if obj.memorandum_receipt else None

    def update(self, instance, validated_data):
        # quantity is set once at create; thereafter it only moves through
        # /api/movements/add/ or request approval (spec 2.1 audit trail).
        validated_data.pop("quantity", None)
        return super().update(instance, validated_data)


# --------------------------------------------------------------------------
# Step 6b — stock integrity (StockMovement, InventoryRequest)
# --------------------------------------------------------------------------


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    performed_by = serializers.SlugRelatedField(slug_field="username", read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "item",
            "item_name",
            "quantity",
            "movement_type",
            "note",
            "performed_by",
            "created_at",
        ]
        read_only_fields = fields


class StockMovementWriteSerializer(serializers.Serializer):
    """Body for POST /api/movements/add/."""

    item = serializers.PrimaryKeyRelatedField(queryset=InventoryItem.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    movement_type = serializers.ChoiceField(choices=StockMovement.MovementType.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_item(self, item):
        if item.is_archived:
            raise serializers.ValidationError("Cannot record a movement for an archived item.")
        return item


class InventoryRequestSerializer(serializers.ModelSerializer):
    requested_by = serializers.SlugRelatedField(slug_field="username", read_only=True)
    decided_by = serializers.SlugRelatedField(slug_field="username", read_only=True)
    item_name = serializers.CharField(source="item.name", read_only=True)

    class Meta:
        model = InventoryRequest
        fields = [
            "id",
            "requested_by",
            "item",
            "item_name",
            "quantity",
            "status",
            "note",
            "decided_by",
            "decided_at",
            "created_at",
        ]
        read_only_fields = ["status", "decided_by", "decided_at", "created_at"]

    def validate_item(self, item):
        if item.is_archived:
            raise serializers.ValidationError("Cannot request an archived item.")
        return item

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value


class RequestDecisionSerializer(serializers.Serializer):
    """Body for PATCH /api/requests/<pk>/approve/."""

    decision = serializers.ChoiceField(
        choices=[
            InventoryRequest.Status.APPROVED,
            InventoryRequest.Status.REJECTED,
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")
