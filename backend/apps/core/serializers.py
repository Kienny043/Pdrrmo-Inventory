"""Serializers for the Personnel / Training Matrix CRUD surface (spec Section 4)."""

from rest_framework import serializers

from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN
from .models import Personnel, TrainingRecord


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
