"""
Trained Personnel & Training Matrix models (spec Section 3.3, build Step 3).

Reconciles the audited system's ``TrainedPersonnel`` / ``TrainingCompletion``
into a spreadsheet-shaped matrix: one ``Personnel`` row per trained person,
one ``TrainingRecord`` cell per (person, training) with the year attained.

Not in this step: the ``/api/personnel/`` CRUD endpoints (Step 3b), admin
registration (Step 8), and the Section 3.2 training-event models (Step 5).
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN, OrgAffiliation
from .reference import (
    MUNICIPALITY_CHOICES,
    MUNICIPALITY_NAME_MAX_LENGTH,
    TRAINING_CATALOG_CHOICES,
    TRAINING_KEY_MAX_LENGTH,
    district_for,
)


class Personnel(models.Model):
    """A trained person tracked in the training matrix (spec Section 3.3).

    Spreadsheet-sourced data about an individual — not an auth account. The
    only ``User`` link is ``archived_by`` (audit trail).
    """

    name = models.CharField(max_length=255)
    designation = models.CharField(max_length=255, blank=True)

    # C/MDRRMO Employee vs. Volunteer — the rollup axis (spec 2.5).
    org_affiliation = models.CharField(
        max_length=16,
        choices=OrgAffiliation.choices,
        default=OrgAffiliation.EMPLOYEE,
    )

    # The sheet's visible "Employment Status" column. Free text for v1: spec
    # Section 6 Open Question #1 is unresolved (only "Permanent" confirmed), so
    # this follows the Section 2.11 pattern — free CharField, frontend offers a
    # dropdown of common values as a convenience, not a DB constraint. See
    # choices.EmploymentStatus for that placeholder value set.
    employment_status = models.CharField(max_length=64, blank=True)

    # Plain choice off the Section 1.1 fixed constant — no FK (spec 1.1 / 2.5;
    # this is a standalone project with no accounts app to FK into). Required:
    # a Personnel with no municipality can't appear in any district/
    # municipality matrix view.
    municipality = models.CharField(
        max_length=MUNICIPALITY_NAME_MAX_LENGTH,
        choices=MUNICIPALITY_CHOICES,
    )

    other_drr_training = models.TextField(blank=True)

    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["municipality", "name"]

    def __str__(self):
        return self.name

    @property
    def district(self):
        """Computed via the municipality->district lookup, never stored (spec 3.3)."""
        return district_for(self.municipality)


class TrainingRecord(models.Model):
    """One matrix cell: a (person, training) pair and the year attained.

    ``unique_together (personnel, training_key)`` is kept intentionally (spec
    Section 3.3) — this is a spreadsheet-shaped matrix, one cell per training
    per person, edited in place when retaken. It is NOT the old
    ``TrainingCompletion`` bug (there ``training_type`` meant many distinct
    scheduled events over time). The constraint is what lets the Step 3b
    cell-upsert endpoint be an ``update_or_create``.
    """

    personnel = models.ForeignKey(
        Personnel,
        on_delete=models.CASCADE,
        related_name="training_records",
    )
    training_key = models.CharField(
        max_length=TRAINING_KEY_MAX_LENGTH,
        choices=TRAINING_CATALOG_CHOICES,
    )
    year_attained = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(TRAINING_YEAR_MIN),
            MaxValueValidator(TRAINING_YEAR_MAX),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["training_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["personnel", "training_key"],
                name="uniq_personnel_training_key",
            ),
        ]

    def __str__(self):
        return f"{self.personnel} · {self.training_key} ({self.year_attained})"
