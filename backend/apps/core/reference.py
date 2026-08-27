"""
Reference data as fixed Python constants (spec Section 1).

Municipalities/districts and the training catalog do not change often
enough to justify database tables, and a hardcoded catalog is faster to
build correctly under time pressure. Each list is exposed through exactly
one read-only endpoint (see ``views.py``) so Python and the frontend JS
share one source of truth rather than keeping two copies.

Nothing here touches the database. ``TextChoices`` is used only for its
value/label pairing; the classes below are consumed as ``.choices`` by
model fields added in later build steps.
"""

from django.db import models

# --------------------------------------------------------------------------
# 1.1  Municipalities & Districts  (41 municipalities, 4 districts)
# --------------------------------------------------------------------------
# District is computed from the municipality via MUNICIPALITY_DISTRICT and is
# never stored redundantly (spec Section 1.1 / 3.3).

FIRST_DISTRICT = "First District"
SECOND_DISTRICT = "Second District"
THIRD_DISTRICT = "Third District"
FOURTH_DISTRICT = "Fourth District"

# Ordered First -> Fourth. This is the canonical district ordering used by
# the municipalities endpoint.
DISTRICTS = (FIRST_DISTRICT, SECOND_DISTRICT, THIRD_DISTRICT, FOURTH_DISTRICT)

# The single source: municipalities grouped by district, exact list from the
# confirmed spreadsheet (spec Section 1.1). Everything else in this section is
# derived from this dict so there is only ever one copy to keep correct.
_DISTRICT_MUNICIPALITIES = {
    FIRST_DISTRICT: (
        "Burdeos",
        "General Nakar",
        "Infanta",
        "Jomalig",
        "Lucban",
        "Mauban",
        "Pagbilao",
        "Panukulan",
        "Patnanungan",
        "Polillo",
        "Real",
        "Sampaloc",
        "Tayabas City",
    ),
    SECOND_DISTRICT: (
        "Candelaria",
        "Dolores",
        "Lucena City",
        "San Antonio",
        "Sariaya",
        "Tiaong",
    ),
    THIRD_DISTRICT: (
        "Agdangan",
        "Buenavista",
        "Catanauan",
        "General Luna",
        "Macalelon",
        "Mulanay",
        "Padre Burgos",
        "Pitogo",
        "San Andres",
        "San Francisco",
        "San Narciso",
        "Unisan",
    ),
    FOURTH_DISTRICT: (
        "Alabat",
        "Atimonan",
        "Calauag",
        "Guinayangan",
        "Gumaca",
        "Lopez",
        "Perez",
        "Plaridel",
        "Quezon",
        "Tagkawayan",
    ),
}

# name -> district lookup
MUNICIPALITY_DISTRICT = {
    name: district
    for district, names in _DISTRICT_MUNICIPALITIES.items()
    for name in names
}

# Flat, alphabetically ordered name list.
MUNICIPALITIES = tuple(sorted(MUNICIPALITY_DISTRICT))

# (value, label) pairs for use as ``choices=`` on model fields in later steps
# (Personnel.municipality, ManualAttendee.municipality).
MUNICIPALITY_CHOICES = tuple((name, name) for name in MUNICIPALITIES)

MUNICIPALITY_NAME_MAX_LENGTH = 32  # longest is "General Nakar" (13); headroom for model fields


def district_for(municipality):
    """Return the district name for a municipality, or raise KeyError."""
    return MUNICIPALITY_DISTRICT[municipality]


def municipalities_by_district_then_name():
    """Ordered [(name, district), ...] — district First->Fourth, then name."""
    rows = []
    for district in DISTRICTS:
        for name in sorted(_DISTRICT_MUNICIPALITIES[district]):
            rows.append((name, district))
    return rows


# --------------------------------------------------------------------------
# 1.2  Training Catalog  (27 items: 15 MANAGERIAL + 12 SKILLS)
# --------------------------------------------------------------------------
# Replaces the old, never-wired-up ``TrainingType`` model (spec Section 2.4).
# Consumed as ``TrainingRecord.training_key`` and
# ``TrainingSchedule.matrix_training_key`` in later steps. Labels are verbatim
# from spec Section 1.2; item order within each class is meaningful and
# preserved (e.g. ICS Level 1 -> Level 4).

MANAGERIAL = "MANAGERIAL"
SKILLS = "SKILLS"


class ManagerialTraining(models.TextChoices):
    ICS_L1 = "ICS_L1", "Basic Incident Command System Level 1"
    ICS_L2 = "ICS_L2", "ICS — Integrated Planning Level 2"
    ICS_L3 = "ICS_L3", "ICS — Position Course Level 3"
    ICS_L4 = "ICS_L4", "ICS — All Hazard Incident Management Team Level 4"
    ICS_TFI = "ICS_TFI", "ICS — Training for Instructors"
    ICS_EXEC = "ICS_EXEC", "Incident Command System – Executive Course"
    EOC = "EOC", "Emergency Operations Center (EOC)"
    EOC_EXEC = "EOC_EXEC", "Emergency Operations Center – Executive Course"
    RDANA = "RDANA", "Rapid Damage Assessment & Needs Analysis (RDANA)"
    CBDRRM = "CBDRRM", "Community-Based Disaster Risk Reduction and Management"
    CBDRRM_TOT = (
        "CBDRRM_TOT",
        "Community-Based Disaster Risk Reduction and Management – Training of Trainers",
    )
    ECCDIE = (
        "ECCDIE",
        "Early Childhood Care & Development in Emergencies Training (ECCDiE)",
    )
    CP = "CP", "Contingency Plan Training"
    PSCP = "PSCP", "Public Service Continuity Plan (PSCP)"
    LDRRMP = (
        "LDRRMP",
        "Local Disaster Risk Reduction and Management Plan Training (LDRRMP)",
    )


class SkillsTraining(models.TextChoices):
    BLS = "BLS", "Basic Life Support (BLS)"
    SFA = "SFA", "Standard First Aid (SFA)"
    BLS_TOF = (
        "BLS_TOF",
        "Basic Life Support Learning Facilitation Course (BLS-TOF)",
    )
    CVERT = "CVERT", "Crash Vehicle Extrication and Rescue Training (CVERT)"
    WASAR = "WASAR", "Water Search and Rescue Training (WASAR)"
    SWAR = "SWAR", "Swift Water Rescue Training (SWAR)"
    BRRT = "BRRT", "Basic Rope Rescue Training (BRRT)"
    MOSART = "MOSART", "Mountain Search & Rescue Training (MOSART)"
    MOSAR_TOT = (
        "MOSAR_TOT",
        "Mountain Search & Rescue Training of Trainers (MOSAR TOT)",
    )
    HAZMAT_AWARENESS = "HAZMAT_AWARENESS", "Hazardous Materials Awareness Level"
    HAZMAT_OPERATIONS = "HAZMAT_OPERATIONS", "Hazardous Materials Operations Level"
    CSSR = "CSSR", "Collapsed Structure Search & Rescue Training (CSSR)"


# Ordered (group_name, TextChoices) pairs — MANAGERIAL block first, then SKILLS.
TRAINING_GROUPS = (
    (MANAGERIAL, ManagerialTraining),
    (SKILLS, SkillsTraining),
)

# All 27 (value, label) pairs, spec order preserved. Use as ``choices=`` for
# TrainingRecord.training_key in a later step.
TRAINING_CATALOG_CHOICES = ManagerialTraining.choices + SkillsTraining.choices

# Fast membership / validation set of the 27 keys.
VALID_TRAINING_KEYS = frozenset(key for key, _label in TRAINING_CATALOG_CHOICES)

# Longest key is "HAZMAT_OPERATIONS" (17); headroom for model fields.
TRAINING_KEY_MAX_LENGTH = 32

_TRAINING_GROUP_BY_KEY = {
    key: group
    for group, choices_cls in TRAINING_GROUPS
    for key in choices_cls.values
}
_TRAINING_LABEL_BY_KEY = dict(TRAINING_CATALOG_CHOICES)


def training_group(key):
    """Return "MANAGERIAL" or "SKILLS" for a catalog key, or raise KeyError."""
    return _TRAINING_GROUP_BY_KEY[key]


def training_label(key):
    """Return the human-readable label for a catalog key, or raise KeyError."""
    return _TRAINING_LABEL_BY_KEY[key]


def training_catalog_rows():
    """Ordered [(key, label, group), ...] — MANAGERIAL block then SKILLS, spec order."""
    rows = []
    for group, choices_cls in TRAINING_GROUPS:
        for key, label in choices_cls.choices:
            rows.append((key, label, group))
    return rows
