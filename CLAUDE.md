# Inventory & Training Matrix System — Project Context for Claude Code

Standalone rebuild of `PDRRMO_v3`'s `apps/inventory` module (equipment,
staff, requests, training schedules, trained personnel) as a clean,
independent Django project — same "build standalone first, integrate
later" strategy already used for `quick-sitrep`. Lives in its own git
repo, sibling to `PDRRMO_v3/` and `quick-sitrep/`
(`../PDRRMO_v3/`, `../quick-sitrep/`), not inside either of them.

**Full spec:** [docs/spec-inventory-system.md](docs/spec-inventory-system.md)
— read that first, it has everything: scope split, reference data, the
12 explicit audit-decision resolutions carried over from auditing
`PDRRMO_v3`'s current inventory module, the full data model, API
endpoints, frontend/auth notes, and the build order this project
follows. Originally written in `PDRRMO_v3/docs/`, copied here so this
project is self-contained — a future session working only in this repo
doesn't need to reach into a sibling repo for its own spec.

## Strategy

- **Priority:** the Trained Personnel & Training Matrix piece (spec
  Section 3.3 / 4) is front-loaded ahead of the rest of inventory
  (equipment, staff, requests, training-event scheduling) — it has real
  near-term deadline pressure from the client; the rest of the module
  does not. See spec Section 0.
- **No build step for v1** — plain Django templates + vanilla JS, no
  React/Vite. Matches `quick-sitrep`'s and the original training-matrix
  spec's approach: fastest path to something real. Integration into
  `PDRRMO_v3`'s actual React frontend is explicitly a later concern
  (spec Section 7, step 11).
- Analytics (`InventoryAnalytics.jsx` and analytics endpoints) is
  **out of scope** for this rebuild, same as it was out of scope for
  the audit that fed the spec.
- `PDRRMO_v3`'s existing models are a *reference*, not a literal port —
  several things are being deliberately fixed, not copied (spec
  Section 2's 12 audit-decision resolutions).

## Tech Stack (as actually installed)

| Layer          | Technology                                                   |
| -------------- | ------------------------------------------------------------- |
| Backend        | Python 3.13, Django 6.0.4, Django REST Framework 3.17.1      |
| Auth           | DRF session auth (+ CSRF) for the real UI path; DRF basic auth added only so endpoints can be curl-tested without a login/CSRF dance |
| Database       | SQLite (local dev, default) / PostgreSQL via `DATABASE_URL` (prod — `dj-database-url` 2.3.0, `psycopg2-binary` 2.9.10) |
| Static files   | `whitenoise` 6.8.2 (`CompressedManifestStaticFilesStorage`)   |
| Config         | `python-dotenv` 1.2.2, `.env`-based (`backend/.env`, gitignored; `backend/.env.example` checked in) |
| Deployment     | `gunicorn` 23.0.0 (Render + external Postgres planned — same approach as `quick-sitrep`, spec Section 7 step 10) |
| Frontend       | Plain Django templates + vanilla JS (no build step)           |
| Timezone       | `Asia/Manila`                                                 |

No custom Django apps exist yet — `backend/apps/` is an empty package,
ready for the first app (reference data / personnel) per the build
order below.

## Reference-Data-as-Constants Pattern

Municipalities/districts (41 towns, 4 districts) and the training
catalog (27 items) are kept as **fixed Python constants** — a name list
+ `municipality → district` lookup dict, and a `TextChoices` class —
**not** database tables. This is the same pattern already used in
`quick-sitrep`, and it's a deliberate choice, not a shortcut: this
reference data doesn't change often enough to justify a DB table, and
a hardcoded catalog is faster to build correctly under time pressure.
See spec Section 1 for the full reasoning, including why this also
replaces `ManualAttendee.municipality`'s old FK (no `accounts` app to
FK into here — this is a standalone project). Each constant list is
exposed via exactly one read-only endpoint (`GET /api/municipalities/`,
`GET /api/training-catalog/`) so there's one source of truth shared by
Python and the frontend JS, not two copies.

## Auth Plan

Two roles (spec Section 5) — the original training-matrix spec proposed
no role system at all, but that doesn't hold once equipment
requests/approvals and training registration are folded in:

- **STAFF** — request equipment, register/cancel their own training
  registrations, view their own requests/registrations.
- **ADMIN** — everything else: manage categories/staff/items/movements,
  approve/reject requests, manage training schedules and the personnel
  matrix, archive/restore.
- A narrow **`can_permanently_delete`** flag on top of ADMIN (mirrors
  `PDRRMO_v3`'s old `is_inventory_admin` split) — permanent deletion of
  an already-archived record stays a deliberately rare, explicitly
  elevated action, not something every admin account can do by default.

Session auth is sufficient for v1 (no JWT yet) — see Tech Stack above.

## Build Order (spec Section 7)

Work through these in order, confirming before moving to the next step.

- [x] **1. Scaffold the standalone project** — own repo, own venv, own
      `.env`-based settings. Done: commit `11c8a3c` on `main`.
- [x] **2. Reference data** — municipalities/districts + 27-item
      training catalog as fixed constants in `backend/apps/core/
      reference.py` (spec Section 1), exposed via two read-only,
      auth-required endpoints: `GET /api/municipalities/` (41 rows,
      `{name, district}`, ordered First→Fourth district then name) and
      `GET /api/training-catalog/` (27 rows, `{key, label, group}`,
      MANAGERIAL block of 15 then SKILLS block of 12, spec order).
      Wired via `apps.core` in `INSTALLED_APPS` and `path("api/",
      include("apps.core.urls"))`. No models/migrations yet.
- [~] 3. Personnel & Training Matrix models + backend CRUD (spec
      Section 3.3, 4) — front-loaded ahead of the rest of inventory per
      Section 0's confirmed priority. Split into two parts:
  - [x] **3a. Models + migration** — `Personnel` and `TrainingRecord`
        in `backend/apps/core/models.py` (+ `choices.py` for the shared
        `OrgAffiliation` enum, unused `EmploymentStatus` reference enum,
        and `TRAINING_YEAR_MIN/MAX`), migration `core/0001_initial`.
        `Personnel.district` is a computed property, not stored;
        `municipality` is a plain `choices` field off
        `MUNICIPALITY_CHOICES` (no FK); `employment_status` is a free
        `CharField` for v1 (spec Section 6 Q#1 still open);
        `TrainingRecord` has `unique_together (personnel, training_key)`.
        No `admin.py` (that's Step 8).
  - [ ] **3b. Backend CRUD** — the `/api/personnel/…` endpoints from
        spec Section 4 (list/create with `?municipality=`/`?district=`/
        `?archived=`, detail, soft-archive DELETE, restore,
        permanent-delete, `PATCH …/training-record/<training_key>/`
        cell upsert). Not started.
- [ ] 4. Personnel/matrix frontend (spec Section 5, page 1) — test with
      realistic data across a few districts/municipalities before
      moving on
- [ ] 5. Remaining core models + migrations (spec Section 3.1, 3.2),
      applying all of Section 2's decisions as they're built (atomic
      stock movements, real `is_archived` on `TrainingSchedule`,
      soft-cancel registrations, shared `OrgAffiliation`, etc.) rather
      than retrofitting afterward
- [ ] 6. Backend CRUD for the rest of inventory (spec Section 4)
- [ ] 7. Remaining frontend pages (spec Section 5, pages 2–8)
- [ ] 8. Full `admin.py` registration for every model (spec 2.9) —
      cheap, do it once at the end rather than piecemeal
- [ ] 9. Test end-to-end: personnel matrix across districts, equipment
      request → approval → stock deduction, training schedule →
      attendance → matrix auto-populate, archive/restore/
      permanent-delete for every archivable model
- [ ] 10. Deploy (Render + external Postgres, unless a faster option
       makes more sense at that point)
- [ ] 11. *(Later, separate effort)* Integration into `PDRRMO_v3`'s
       real React frontend and JWT/role system

## Current Git State

On branch `main`: `11c8a3c` scaffold, then the Step 2 reference-data
commit. Remote `origin` is
`https://github.com/Kienny043/Pdrrmo-Inventory.git`; `main` tracks
`origin/main`.

## Notes for Claude Code

- This project's models are inspired by `PDRRMO_v3`'s `apps/inventory`
  but are **not** a literal port — check spec Section 2 before assuming
  old behavior carries over; 12 specific bugs/inconsistencies were
  found in the old system and each has an explicit fix/preserve/drop
  call already made.
- Don't reach into `../PDRRMO_v3/` or `../quick-sitrep/` for anything
  this repo needs going forward — this repo should be self-contained
  (this is why the spec doc was copied in rather than left as a
  cross-repo reference).
- Ask before skipping ahead in the build order above.
