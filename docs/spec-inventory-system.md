# Inventory & Trained Personnel System — Standalone Build Spec

**Status:** Planning — not yet built
**Purpose:** Rebuild `PDRRMO_v3`'s `apps/inventory` module (equipment,
staff, requests, training schedules, trained personnel) as a clean
standalone system — same "build standalone first, integrate later"
strategy already used for `quick-sitrep` and the trained-personnel
training-matrix piece. Two inputs feed this spec:

1. A full read-only audit of `PDRRMO_v3`'s actual current
   `apps/inventory` code (models, serializers, endpoints, and the seven
   non-analytics frontend pages), done specifically to inform this
   rebuild.
2. The confirmed training-matrix requirements (41 municipalities / 4
   districts, the 27-item training catalog, year-attained tracking,
   archive-for-audit) from the client-requested standalone build that
   was already spec'd separately. That work is folded in here as this
   document's Trained Personnel & Training Matrix section, not restated
   as a parallel document — this **is** that build now, expanded to
   cover the rest of inventory too.

Analytics (`InventoryAnalytics.jsx` and the `analytics/` endpoint) is
**out of scope** for this rebuild, same as it was out of scope for the
audit that fed it.

**Strategy:** Own repo, own session, no build step for v1 (plain
templates + vanilla JS, matching `quick-sitrep`'s and the original
trained-personnel spec's stated approach — fastest path to something
real, integration into `PDRRMO_v3`'s actual React frontend is a later
concern). Reuse `PDRRMO_v3`'s existing models as a *reference*, not a
literal port — several things are being deliberately fixed, not copied,
per Section 2 below.

---

## 0. Scope

**Confirmed priority (carried from the original training-matrix spec):**
The Trained Personnel & Training Matrix piece (Section 4.3) was
requested first and has its own near-term deadline pressure. It should
be built and usable before the rest of inventory, even though both now
live in the same project. Everything else in this document (equipment,
staff, requests, training-event scheduling) has no external deadline —
it's being built in the same standalone project because it was audited
together and shares infrastructure (municipalities, auth, the training
catalog), not because it's equally urgent.

**In scope, rebuilt cleanly:**
- Category, Staff
- InventoryItem, StockMovement, ItemHolderLog
- InventoryRequest
- TrainingSchedule, TrainingRegistration, ManualAttendee
- Trained Personnel & Training Matrix (Personnel, TrainingRecord)

**Deferred (explicitly, not silently dropped):**
- Analytics (whole section, both the old inventory analytics and the
  training-matrix SUMMARY rollup screen)
- Seminar module (mentioned in the original training-matrix reference
  material, no detail ever provided)
- Integration into `PDRRMO_v3` itself

---

## 1. Reference Data

### 1.1 Municipalities & Districts

41 municipalities, 4 districts, exact list from the confirmed
spreadsheet. Kept as **fixed Python constants** (a name list + a
`municipality -> district` lookup dict), not a database table —
district is computed via the lookup, never stored redundantly. This
matches the original training-matrix spec's own recommendation, and is
extended here to replace `ManualAttendee.municipality`'s old FK to
`accounts.Municipality` too — this is a standalone project with no
`accounts` app to FK into, and the reference data doesn't change often
enough to justify a DB table over a constant.

- **First District (13):** Burdeos, General Nakar, Infanta, Jomalig,
  Lucban, Mauban, Pagbilao, Panukulan, Patnanungan, Polillo, Real,
  Sampaloc, Tayabas City
- **Second District (6):** Candelaria, Dolores, Lucena City, San
  Antonio, Sariaya, Tiaong
- **Third District (12):** Agdangan, Buenavista, Catanauan, General
  Luna, Macalelon, Mulanay, Padre Burgos, Pitogo, San Andres, San
  Francisco, San Narciso, Unisan
- **Fourth District (10):** Alabat, Atimonan, Calauag, Guinayangan,
  Gumaca, Lopez, Perez, Plaridel, Quezon, Tagkawayan

Exposed to the frontend via a small read-only `GET /api/municipalities/`
endpoint (name + district per row) so the constant list has exactly one
source of truth — not duplicated between Python and JS.

### 1.2 Training Catalog (27 items)

Kept as a **fixed `TextChoices` class**, not a database table — same
reasoning the original training-matrix spec gave: this exact list isn't
something that changes often, and a hardcoded catalog is far faster to
build correctly under time pressure. See Section 2.4 for why this
replaces the old system's `TrainingType` model rather than promoting it
to a real FK.

**MANAGERIAL (15):** Basic Incident Command System Level 1 · ICS —
Integrated Planning Level 2 · ICS — Position Course Level 3 · ICS — All
Hazard Incident Management Team Level 4 · ICS — Training for
Instructors · Incident Command System – Executive Course · Emergency
Operations Center (EOC) · Emergency Operations Center – Executive
Course · Rapid Damage Assessment & Needs Analysis (RDANA) ·
Community-Based Disaster Risk Reduction and Management ·
Community-Based Disaster Risk Reduction and Management – Training of
Trainers · Early Childhood Care & Development in Emergencies Training
(ECCDiE) · Contingency Plan Training · Public Service Continuity Plan
(PSCP) · Local Disaster Risk Reduction and Management Plan Training
(LDRRMP)

**SKILLS (12):** Basic Life Support (BLS) · Standard First Aid (SFA) ·
Basic Life Support Learning Facilitation Course (BLS-TOF) · Crash
Vehicle Extrication and Rescue Training (CVERT) · Water Search and
Rescue Training (WASAR) · Swift Water Rescue Training (SWAR) · Basic
Rope Rescue Training (BRRT) · Mountain Search & Rescue Training
(MOSART) · Mountain Search & Rescue Training of Trainers (MOSAR TOT) ·
Hazardous Materials Awareness Level · Hazardous Materials Operations
Level · Collapsed Structure Search & Rescue Training (CSSR)

Exposed via `GET /api/training-catalog/`, same one-source-of-truth
reasoning as municipalities.

---

## 2. Decisions Carried From the Inventory Audit

Every real bug or inconsistency flagged in the audit gets an explicit
call here — fixed, deliberately preserved, or deferred — before the
data model below reflects the outcome. Nothing carries forward silently.

**2.1 Orphaned `StockMovement` row on a rejected OUT transaction — FIX.**
The old `add_movement` view saved the `StockMovement` row *before*
checking whether the item had enough stock for an `OUT` movement, so a
rejected request still left a permanent, misleading log entry. The new
build wraps the whole operation — create movement, adjust
`item.quantity`, insufficient-stock check — in one
`transaction.atomic()` block. If the check fails, nothing is written,
not even the movement row.

**2.2 `TrainedPersonnelPage`'s broken field references — don't repeat.**
The old frontend read `p.municipality?.name` (the API actually returns
a raw FK id plus a separate flat `municipality_name`) and
`p.training_title` / `p.training?.title` / `p.completion_date` (none of
which exist — completions are a `completions` array, not flat fields).
Three of six columns silently rendered blank. The new build has no
equivalent mistake to avoid repeating structurally: Section 4.3's
`Personnel`/`TrainingRecord` API is designed field-name-first (the
frontend table is built directly against the real serializer output,
matrix-shaped from the start), and this point is simply a reminder to
verify the new frontend's field names against the real API response
before shipping, not a design change.

**2.3 Archive/restore asymmetry on `TrainingSchedule` — FIX, add a real
`is_archived` field.** The old model had no `is_archived` at all;
"archiving" overloaded `status=CANCELLED`, conflating "this training
was actually cancelled" (a real-world fact) with "hide this row from
the default list" (a housekeeping/audit action) — and there was no
permanent-delete path for a cancelled training either. The new
`TrainingSchedule` gets its own `is_archived` boolean plus
`archived_at`/`archived_by`, matching the pattern already used for
Staff, Items, and Personnel. `status` (`UPCOMING`/`ONGOING`/`COMPLETED`/
`CANCELLED`) keeps meaning exactly what it says; archiving is a
separate action layered on top, with the same `/archived/`, `/restore/`,
`/<pk>/permanent-delete/` shape as everything else.

**2.4 `TrainingType` unwired/abandoned — DROP the model, wire up the
concept as a fixed catalog instead.** The old `TrainingType` model was
never seeded (schema-only migration), never registered in admin, and
had zero frontend references — `TrainingCompletion.training_type` was a
free `CharField`, not a FK to it. Rather than finish wiring it up as a
real FK (a DB table for 27 rows that essentially never change buys
nothing), the new build drops `TrainingType` entirely and uses the
Section 1.2 fixed `TextChoices` catalog as `TrainingRecord.training_key`
— an explicit decision, not a half-finished model carried forward
again. If the client ever wants to self-edit the catalog, promoting a
`TextChoices` to a real model later is a small, well-understood
migration.

**2.5 Duplicated EMPLOYEE/VOLUNTEER choice pattern — FIX, one shared
class.** The old system declared this concept twice: `TrainedPersonnel`
used a proper `EmploymentStatus(TextChoices)`, `ManualAttendee` used an
inline raw tuple list on the field directly. The new build defines one
`OrgAffiliation(TextChoices)` (`EMPLOYEE`/`VOLUNTEER`) and reuses it on
both `Personnel` and `ManualAttendee` — see Section 3's naming note for
why it's renamed from "employment status" (that label now means
something else — see 4.3).

**2.6 No audit trail for self-cancelled training registrations — FIX,
soft-cancel instead of hard delete.** `cancel_training_registration`
did a real `reg.delete()` — no record survives that a registration ever
existed. Given this whole build's stated emphasis on audit trails (the
training-matrix archive requirement is explicit about this: "for
auditing, not just tidying up"), `TrainingRegistration` gets a `status`
field (`REGISTERED`/`CANCELLED`, default `REGISTERED`) plus
`cancelled_at` instead of being deleted. See Section 3.2 for the
`unique_together` consequence this creates and how it's handled.

**2.7 Staff "Remove photo" checkbox does nothing — FIX.** The old
frontend sent `remove_photo=true` but neither `StaffSerializer` nor the
view ever read it. Small, cheap fix: the new `staff_detail`
PATCH handler explicitly clears the `photo` field when
`remove_photo` is present and truthy in the request body.

**2.8 `delete_manual_attendee` endpoint has no frontend caller — FIX,
wire up the missing button.** The old backend's authorization logic
(admin, or an LGU deleting only their own municipality's attendee) was
already correct — the UI for it was just never finished. The new
`ManualAttendees` component gets a delete action per row using the same
permission rule.

**2.9 `admin.py` registers only 5 of 12 models — FIX, register all of
them.** This is an internal tool; the Django admin panel is a
legitimate fallback UI for edge cases and support work. Every model in
this spec gets a registered `ModelAdmin` from the start, not
retrofitted later.

**2.10 `Category.icon` — DROP.** Never rendered anywhere in the old
frontend, and no requirement calls for it. Category management also had
no create/edit UI at all in the old build (categories could only be
created via admin/shell) — the new build adds a minimal category
list/create/edit screen (Section 5), and `Category` stays just
`name` + `description`. An icon can be re-added later if a real design
need for it shows up.

**2.11 `competency`/`unit` are free text but the frontend showed a
fixed dropdown — PRESERVE, document as intentional.** This wasn't
really a bug so much as an undocumented mismatch — real-world values for
both (competency labels, item units) genuinely vary by context, and
locking either to a hard enum risks blocking legitimate entries. The
new build keeps both as free `CharField`s with a frontend
dropdown-of-common-values as a convenience, not a constraint — stated
explicitly here so it isn't "discovered" as a bug again later. (Note:
`competency` itself doesn't survive into the new `Personnel` model at
all — see Section 3's note on why.)

**2.12 `InventoryRequest.approve` never touches stock — FIX.** Flagged
in the audit's endpoint notes: approving a request didn't create a
`StockMovement` or adjust `item.quantity` at all, making the request
queue purely advisory. The new `approve_request` (on `APPROVED` only,
not `REJECTED`) creates an `OUT` `StockMovement` and decrements stock
through the same atomic path as 2.1 — including the same
insufficient-stock rejection behavior, so approving a request for more
than what's on hand fails cleanly instead of silently going negative.

---

## 3. Data Model

### 3.1 Inventory Core

**Category**
`id`, `name` (unique), `description` (blank). *(`icon` dropped — 2.10.)*

**Staff**
`id`, `first_name`, `last_name`, `position` (blank), `department`
(blank), `contact` (blank), `status` (`TextChoices`:
`PERMANENT`/`CASUAL`/`INTERN`/`INACTIVE`, default `PERMANENT`), `photo`
(nullable), `is_archived` (default `False`).

**InventoryItem**
`id`, `category` (FK → Category, CASCADE), `name`, `brand` (blank),
`description` (blank), `image` (nullable), `quantity` (default 1),
`unit` (free `CharField`, blank — see 2.11), `date_acquired`
(nullable), `memorandum_receipt` (FK → Staff, SET_NULL, nullable —
current holder), `condition` (`TextChoices`:
`NEW`/`GOOD`/`FAIR`/`NEEDS_REPAIR`/`DAMAGED`, default `GOOD`), `remarks`
(blank), `is_archived`, `created_at`.

**ItemHolderLog**
`id`, `item` (FK → InventoryItem, CASCADE), `staff` (FK → Staff,
SET_NULL, nullable), `action` (`TextChoices`: `ASSIGNED`/`REMOVED` —
was a bare `CharField` before, cleaned up as part of the rebuild),
`performed_by` (FK → User, SET_NULL, nullable), `timestamp` (auto),
`note` (blank). Written automatically on item create (if a holder is
set) and on every holder change — same behavior as the audited system,
just field-typed properly.

**StockMovement**
`id`, `item` (FK → InventoryItem, CASCADE), `quantity` (required),
`movement_type` (`TextChoices`: `IN`/`OUT`), `note` (blank),
`performed_by` (FK → User, SET_NULL, nullable), `created_at` (auto).
Creation is always atomic with the corresponding `item.quantity`
adjustment (2.1).

**InventoryRequest**
`id`, `requested_by` (FK → User, CASCADE), `item` (FK → InventoryItem,
CASCADE), `quantity` (required), `status` (`TextChoices`:
`PENDING`/`APPROVED`/`REJECTED`, default `PENDING`), `note` (blank),
`decided_by` (FK → User, SET_NULL, nullable — new, small audit-trail
addition consistent with this build's overall emphasis), `decided_at`
(nullable), `created_at`. Approval triggers a stock movement (2.12).

### 3.2 Training Events

**TrainingSchedule**
`id`, `title`, `description` (blank), `date_start`, `date_end`
(nullable), `time_start`/`time_end` (nullable), `venue` (blank),
`target_participants` (blank), `max_slots` (nullable),
`registration_deadline` (nullable), `status` (`TextChoices`:
`UPCOMING`/`ONGOING`/`COMPLETED`/`CANCELLED`, default `UPCOMING`),
`matrix_training_key` (nullable choice from the Section 1.2 catalog —
new; when set, marking attendance auto-upserts the attendee's
`TrainingRecord` for that key at `date_start.year`, same convenience
the old system had via `schedule.title`, now made compatible with the
fixed catalog instead of relying on free-text title matching; when
blank, the schedule is just an event/attendance record and never
touches the matrix), `is_archived`, `archived_at`, `archived_by` (2.3),
`created_by` (FK → User, SET_NULL, nullable), `created_at`,
`updated_at`.

**TrainingRegistration**
`id`, `training` (FK, CASCADE), `user` (FK, CASCADE), `status`
(`TextChoices`: `REGISTERED`/`CANCELLED`, default `REGISTERED` — 2.6),
`registered_at` (auto), `cancelled_at` (nullable), `attended` (default
`False`). **No blanket `unique_together`** on `(training, user)` — a
person can have a `CANCELLED` row and later a fresh `REGISTERED` row for
the same training. Instead, `register_training` checks for an existing
row with `status=REGISTERED` for that pair before creating a new one,
which is the actual invariant that matters ("not currently registered
twice"), not "never registered twice, ever."

**ManualAttendee**
`id`, `training` (FK, CASCADE), `name`, `designation` (blank),
`municipality` (choice, Section 1.1 — no more FK to an `accounts` app),
`org_affiliation` (shared `OrgAffiliation` TextChoices — 2.5), `attended`
(default `False`), `created_at`.

### 3.3 Trained Personnel & Training Matrix

This is the confirmed-requirements piece — folded in from the original
training-matrix spec, reconciled with the audited system's
`TrainedPersonnel`/`TrainingCompletion` rather than kept as a second,
parallel design.

**Personnel** *(was `TrainedPersonnel`)*
- `name`, `designation`
- `org_affiliation` — the shared `OrgAffiliation` TextChoices from 2.5
  (`EMPLOYEE`/`VOLUNTEER`). This is the axis that feeds the deferred
  SUMMARY rollup's "C/MDRRMO Employee vs. Volunteer" split — confirming
  the original spec's Section 6 open question #2: **it is the same
  underlying concept the audited system already called
  `employment_status`**, just renamed here because...
- `employment_status` — **a separate field**, the sheet's actual visible
  "Employment Status" column (Permanent/Casual/Job
  Order/Contractual/etc.). This is *not* the same thing as
  `org_affiliation` — see Open Questions, the exact choice list is still
  unconfirmed beyond "Permanent."
- `municipality` (choice, Section 1.1)
- `district` — computed via the municipality→district lookup, never
  stored (per the original spec's own recommendation)
- `other_drr_training` (TextField, blank — free text, matches the
  sheet's unstructured "Other" column)
- `is_archived`, `archived_at`, `archived_by` (FK → User) — the explicit
  audit-trail requirement from the original spec
- `created_at`, `updated_at`
- **`competency` (the old free-text Basic/Advanced/Instructor field) is
  dropped, not carried forward.** It's superseded by the per-training
  `year_attained` matrix below, which is strictly more informative than
  one overall label — an explicit merge decision, not an oversight.

**TrainingRecord** *(was `TrainingCompletion`)*
- `personnel` (FK → Personnel, CASCADE)
- `training_key` (choice from the Section 1.2 fixed catalog — replaces
  the old free-text `training_type`)
- `year_attained` (PositiveSmallInteger, validated range e.g.
  2000–2035)
- `updated_at`
- `unique_together = (personnel, training_key)` — **kept intentionally**,
  and this is *not* the same bug the audit flagged in the old
  `TrainingCompletion` model. There, `training_type` was meant to
  represent many distinct scheduled training events over time, so the
  same constraint wrongly blocked a legitimate second completion of a
  same-named training in a later year. Here, the requirement is
  explicitly a spreadsheet-shaped matrix — one cell per training per
  person, editing it in place when retaken — so the constraint is
  correct as designed. Editing an existing cell just updates
  `year_attained` in place; there's no history of prior years for a
  re-taken training, matching the source spreadsheet exactly.

---

## 4. API Endpoints

Grouped by resource; permission model in Section 5. Municipalities and
the training catalog are read-only (Section 1).

**Categories** — `GET/POST /api/categories/`, `GET/PATCH/DELETE
/api/categories/<pk>/` (new — 2.10 gives Category a real management UI
this time).

**Staff** — `GET/POST /api/staff/`, `GET/PATCH/DELETE
/api/staff/<pk>/` (PATCH handles `remove_photo` — 2.7), `GET
/api/staff/archived/`, `POST /api/staff/<pk>/restore/`, `DELETE
/api/staff/<pk>/permanent-delete/` (elevated permission only).

**Items** — `GET/POST /api/items/`, `GET/PATCH/DELETE
/api/items/<pk>/` (PATCH diffs `memorandum_receipt` and writes
`ItemHolderLog` entries, same as the audited system), `GET
/api/items/archived/`, `POST /api/items/<pk>/restore/`, `DELETE
/api/items/<pk>/permanent-delete/`, `GET
/api/items/<pk>/holder-history/`.

**Stock Movements** — `POST /api/movements/add/` (atomic — 2.1), `GET
/api/movements/`.

**Requests** — `GET/POST /api/requests/`, `PATCH
/api/requests/<pk>/approve/` (triggers a stock movement on approval —
2.12).

**Training Schedules** — `GET/POST /api/trainings/`,
`GET/PATCH/DELETE /api/trainings/<pk>/`, `GET
/api/trainings/archived/`, `POST /api/trainings/<pk>/restore/`, `DELETE
/api/trainings/<pk>/permanent-delete/` (all new — 2.3), `POST
/api/trainings/<pk>/register/`, `DELETE
/api/trainings/<pk>/cancel-registration/` (soft-cancel now — 2.6), `GET
/api/trainings/<pk>/registrations/`, `PATCH
/api/trainings/<pk>/attendance/<user_id>/` (auto-upserts a
`TrainingRecord` when `matrix_training_key` is set), `GET
/api/trainings/my-registrations/`.

**Manual Attendees** — `GET/POST
/api/trainings/<training_pk>/manual-attendees/`, `DELETE
/api/trainings/<training_pk>/manual-attendees/<pk>/` (now reachable
from the frontend — 2.8), `PATCH
/api/trainings/<training_pk>/manual-attendees/<pk>/attendance/`.

**Trained Personnel & Training Matrix** — `GET/POST
/api/personnel/` (supports `?municipality=`, `?district=`,
`?archived=`), `GET/PATCH/DELETE /api/personnel/<pk>/` (DELETE is
soft-archive), `POST /api/personnel/<pk>/restore/`, `DELETE
/api/personnel/<pk>/permanent-delete/`, `PATCH
/api/personnel/<pk>/training-record/<training_key>/` (upserts one
matrix cell — `year_attained` or `null` to clear it).

**Reference data** — `GET /api/municipalities/`, `GET
/api/training-catalog/`.

---

## 5. Frontend & Auth

**Auth.** The original training-matrix spec proposed no role system at
all (single-office tool). That doesn't hold once the rest of inventory
is folded in — equipment requests, approvals, and training
registration/cancellation genuinely need at least an admin/non-admin
distinction to mean anything. Two roles:
- **STAFF** — can request equipment, register/cancel their own training
  registrations, view their own requests/registrations.
- **ADMIN** — everything else: manage categories/staff/items/movements,
  approve/reject requests, manage training schedules and the personnel
  matrix, archive/restore.
- A narrow `can_permanently_delete` flag on top of ADMIN (mirrors the
  old system's `is_inventory_admin` split) — permanent deletion of an
  already-archived record stays a deliberately rare, explicitly-elevated
  action, consistent with this build's overall audit-trail emphasis,
  not something every admin account can do by default.

Simple session auth is still fine for v1 — the point of the original
simplification (no JWT, no PDRRMO_v3 integration yet) still holds, this
just needs two roles instead of zero.

**Frontend approach.** Plain Django templates + vanilla JS, no build
step — matches `quick-sitrep`'s and the original training-matrix spec's
stated approach, fastest path given no confirmed timeline pressure on
the inventory half and real pressure on the personnel half.

**Pages (personnel/training-matrix first, per Section 0's priority):**
1. **Personnel matrix** — district/municipality picker, then a table
   shaped exactly like the source spreadsheet: Name, Designation,
   Employment Status, Org Affiliation, the 27 training columns (year
   input per cell, blank = not attained), Other DRR Training. "+ New
   Personnel" adds a row. "Archive" soft-deletes with confirmation
   (visible, deliberate action — not silent). Archived personnel
   reachable via a simple filter toggle, not a separate page.
2. **Equipment dashboard** — item list, category filter, search,
   add/edit modal, CSV export, holder-history modal. Same shape as the
   audited `InventoryDashboard.jsx`, minus the broken bits.
3. **Staff management** — list/add/edit/archive, working photo removal
   (2.7).
4. **Stock movements** — log view + record-movement form (ADMIN only).
5. **Requests** — list (own for STAFF, all for ADMIN) + new-request
   form + approve/reject actions.
6. **Training schedules** — create/edit/archive/restore, registrations
   view with attendance toggle, manual attendees with a working delete
   button (2.8).
7. **Archived** — tabbed view (Items / Staff / Trainings / Personnel),
   same shape as the audited `ArchivedPage.jsx`, now with a real
   archived-trainings endpoint to call instead of client-side filtering
   all trainings (2.3).
8. **Categories** — new, minimal list/create/edit (2.10).

---

## 6. Open Questions

Carried forward from the original training-matrix spec — still
unresolved, need a client answer before or while building:

1. **Full `employment_status` choice list.** The source spreadsheet
   only shows "Permanent." Philippine LGU/government HR typically also
   has Contractual, Job Order, Casual — need the client's actual list,
   or ship a placeholder set and adjust later.
2. ~~**Is "C/MDRRMO Employee vs. Volunteer" the same as Employment
   Status?**~~ Resolved by this merge — it's `org_affiliation`
   (Section 3.3), a separate axis from `employment_status`, matching
   what the audited system already called `employment_status`
   (EMPLOYEE/VOLUNTEER) before this rebuild renamed it to avoid
   colliding with the sheet's real HR-status column of the same name.

---

## 7. Suggested Build Order

1. Scaffold the standalone project (own repo, own session — same
   pattern as `quick-sitrep`'s and the original training-matrix spec's
   Step 1)
2. Reference data: municipalities/districts + training catalog as
   fixed constants (Section 1), plus their two read-only endpoints
3. **Personnel & Training Matrix models + backend CRUD** (Section 3.3,
   4) — front-loaded ahead of the rest of inventory per Section 0's
   confirmed priority
4. Personnel/matrix frontend (Section 5, page 1) — test with realistic
   data across a few districts/municipalities before moving on
5. Remaining core models + migrations (Section 3.1, 3.2), applying all
   of Section 2's decisions as they're built (atomic stock movements,
   real `is_archived` on `TrainingSchedule`, soft-cancel registrations,
   shared `OrgAffiliation`, etc.) rather than retrofitting afterward
6. Backend CRUD for the rest of inventory (Section 4)
7. Remaining frontend pages (Section 5, pages 2–8)
8. Full `admin.py` registration for every model (2.9) — cheap, do it
   once at the end rather than piecemeal
9. Test end-to-end: personnel matrix across districts, equipment
   request → approval → stock deduction, training schedule → attendance
   → matrix auto-populate, archive/restore/permanent-delete for every
   archivable model
10. Deploy (same Render + external Postgres approach as `quick-sitrep`,
    unless a faster option makes more sense at that point)
11. *(Later, separate effort)* Integration into `PDRRMO_v3`'s real
    React frontend and JWT/role system
