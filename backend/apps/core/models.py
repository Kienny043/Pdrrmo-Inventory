"""
Core data models.

- Personnel / TrainingRecord — the training matrix (spec Section 3.3, Step 3).
- UserProfile — role + elevated-delete flag (spec Section 5, Step 3b).
- Category / Staff / InventoryItem / ItemHolderLog / StockMovement /
  InventoryRequest — inventory core (spec Section 3.1, Step 5a).
- Section 3.2 training-event models (TrainingSchedule etc.) land in Step 5b.

Model definitions only. Behavior that the audit decisions call for — atomic
stock adjustment (2.1), ItemHolderLog auto-write, approve-deducts-stock
(2.12), remove_photo (2.7) — lives in the Step 6 CRUD layer, not here. Admin
registration is Step 8 (2.9).
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .choices import TRAINING_YEAR_MAX, TRAINING_YEAR_MIN, OrgAffiliation, Role
from .reference import (
    MUNICIPALITY_CHOICES,
    MUNICIPALITY_NAME_MAX_LENGTH,
    TRAINING_CATALOG_CHOICES,
    TRAINING_KEY_MAX_LENGTH,
    district_for,
)


class UserProfile(models.Model):
    """Per-user role + elevated-delete flag (spec Section 5).

    Auto-created for every ``User`` by a ``post_save`` signal (see
    ``signals.py``). ``profile_for()`` below is the safe accessor for code
    paths that may hit a user created before the signal existed.

    v1 has no self-service registration or role-management UI — profiles are
    edited via ``createsuperuser`` + shell/admin. Step 11 replaces this with
    JWT claims from PDRRMO_v3.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)
    can_permanently_delete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user} ({self.role})"

    @property
    def is_admin(self):
        return self.role == Role.ADMIN


def profile_for(user):
    """Return the user's profile, creating a default (STAFF) one if missing."""
    profile, _created = UserProfile.objects.get_or_create(user=user)
    return profile


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


# ==========================================================================
# Inventory core (spec Section 3.1, build Step 5a)
# ==========================================================================
# CRUD endpoints are Step 6; admin registration is Step 8. Audit decisions
# with model impact here: 2.10 (no Category.icon), 2.11 (free-text unit),
# 2.3 (full is_archived/archived_at/archived_by triple on Staff + Item),
# 2.12 (InventoryRequest.decided_by/decided_at). The atomic stock logic
# (2.1) and holder-log auto-write are endpoint concerns, added in Step 6.


class Category(models.Model):
    """An equipment category (spec 3.1). No ``icon`` — dropped (2.10)."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Staff(models.Model):
    """An inventory staff member — equipment holder / MR custodian (spec 3.1).

    Distinct from ``Personnel`` (training-matrix people) and from the auth
    ``User`` (login accounts).
    """

    class Status(models.TextChoices):
        PERMANENT = "PERMANENT", "Permanent"
        CASUAL = "CASUAL", "Casual"
        INTERN = "INTERN", "Intern"
        INACTIVE = "INACTIVE", "Inactive"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    position = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=150, blank=True)
    contact = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PERMANENT
    )
    photo = models.ImageField(upload_to="staff_photos/", null=True, blank=True)

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
        ordering = ["last_name", "first_name"]
        verbose_name_plural = "staff"

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class InventoryItem(models.Model):
    """A tracked equipment item (spec 3.1)."""

    class Condition(models.TextChoices):
        NEW = "NEW", "New"
        GOOD = "GOOD", "Good"
        FAIR = "FAIR", "Fair"
        NEEDS_REPAIR = "NEEDS_REPAIR", "Needs repair"
        DAMAGED = "DAMAGED", "Damaged"

    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="item_images/", null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    # Free text on purpose (2.11) — the frontend offers a dropdown of common
    # values as a convenience, not a constraint.
    unit = models.CharField(max_length=50, blank=True)
    date_acquired = models.DateField(null=True, blank=True)
    # Current holder / memorandum-receipt custodian.
    memorandum_receipt = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="held_items",
    )
    condition = models.CharField(
        max_length=16, choices=Condition.choices, default=Condition.GOOD
    )
    remarks = models.TextField(blank=True)

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
        ordering = ["name"]

    def __str__(self):
        return self.name


class ItemHolderLog(models.Model):
    """Audit trail of equipment holder assignments (spec 3.1).

    Written automatically on item create (if a holder is set) and on every
    holder change — that write happens in the Step 6 item endpoint, not here.
    """

    class Action(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        REMOVED = "REMOVED", "Removed"

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="holder_logs"
    )
    staff = models.ForeignKey(
        Staff, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.item} · {self.action} · {self.staff or '—'}"


class StockMovement(models.Model):
    """A single stock IN/OUT event (spec 3.1).

    ``quantity`` is an unsigned magnitude; direction is ``movement_type``.
    Creation must be atomic with the matching ``item.quantity`` adjustment and
    the insufficient-stock check (2.1) — that wrapping lives in the Step 6
    ``/api/movements/add/`` endpoint.
    """

    class MovementType(models.TextChoices):
        IN = "IN", "Stock in"
        OUT = "OUT", "Stock out"

    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="movements"
    )
    quantity = models.PositiveIntegerField()
    movement_type = models.CharField(max_length=8, choices=MovementType.choices)
    note = models.TextField(blank=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movement_type} {self.quantity} · {self.item}"


class InventoryRequest(models.Model):
    """A staff request to draw equipment from stock (spec 3.1).

    Approval (``APPROVED`` only) creates an ``OUT`` ``StockMovement`` and
    decrements stock through the same atomic path as 2.1 — that logic is the
    Step 6 ``approve_request`` endpoint (2.12). ``decided_by`` / ``decided_at``
    are the new audit-trail fields.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inventory_requests",
    )
    item = models.ForeignKey(
        InventoryItem, on_delete=models.CASCADE, related_name="requests"
    )
    quantity = models.PositiveIntegerField()
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PENDING
    )
    note = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requested_by} → {self.quantity}× {self.item} [{self.status}]"
