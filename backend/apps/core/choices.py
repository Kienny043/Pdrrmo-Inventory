"""
Shared enumerations and small validation constants for the core app.

Kept separate from ``reference.py`` (which is strictly the spec Section 1
municipality/training-catalog reference data) and from ``models.py`` so that
later build steps — e.g. Step 5's ``ManualAttendee`` — can reuse
``OrgAffiliation`` without importing the personnel models (spec Section 2.5:
"one shared class", not one per model).
"""

from django.db import models


class OrgAffiliation(models.TextChoices):
    """C/MDRRMO Employee vs. Volunteer (spec Section 2.5 / 3.3).

    The axis that feeds the deferred SUMMARY rollup's Employee/Volunteer
    split. This is the concept the audited system called ``employment_status``
    before this rebuild renamed it to free that label for the sheet's real
    HR-status column.
    """

    EMPLOYEE = "EMPLOYEE", "Employee"
    VOLUNTEER = "VOLUNTEER", "Volunteer"


class EmploymentStatus(models.TextChoices):
    """The source sheet's visible "Employment Status" column.

    NOT wired to any model field yet: spec Section 6 Open Question #1 is still
    unresolved — the client has only confirmed "Permanent" so far, so
    ``Personnel.employment_status`` is a free ``CharField`` for v1 (spec
    Section 2.11 pattern). This class is defined now only as a reference for
    the placeholder value set a frontend dropdown can offer, and as the
    obvious target if the list is later locked in and promoted to real DB
    choices. "Volunteer" is deliberately absent — that belongs to
    ``OrgAffiliation``, a separate axis.
    """

    PERMANENT = "PERMANENT", "Permanent"
    CASUAL = "CASUAL", "Casual"
    JOB_ORDER = "JOB_ORDER", "Job Order"
    CONTRACTUAL = "CONTRACTUAL", "Contractual"


# TrainingRecord.year_attained validation bounds (spec Section 3.3: "validated
# range e.g. 2000-2035"). The upper bound is arbitrary — the spec itself only
# gives it as an example. Revisit / bump this (or make it dynamic, e.g.
# current year + 1) before it starts rejecting legitimate future entries.
TRAINING_YEAR_MIN = 2000
TRAINING_YEAR_MAX = 2035
