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
- [x] **3. Personnel & Training Matrix models + backend CRUD** (spec
      Section 3.3, 4) — front-loaded ahead of the rest of inventory per
      Section 0's confirmed priority. Both parts done:
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
  - [x] **3b. Backend CRUD** — `PersonnelViewSet` (DRF `ModelViewSet` +
        `SimpleRouter`) in `views.py` / `urls.py`, `serializers.py`,
        `UserProfile` model (`role` STAFF/ADMIN + `can_permanently_delete`)
        with an auto-create `post_save` signal (`signals.py`, wired in
        `CoreConfig.ready()`), migration `core/0002_userprofile`.
        Live routes, all ADMIN-only:
        - `GET/POST /api/personnel/` — list supports `?municipality=`
          (exact), `?district=` (via `reference.municipalities_in`),
          `?archived=` (absent/`false`/`0`/unknown = active, `true`/`1`
          = archived, `all` = both); unknown municipality/district → `[]`.
          No pagination. `training_records` always embedded.
        - `GET/PATCH /api/personnel/<pk>/` — PATCH on an archived row → 409.
        - `DELETE /api/personnel/<pk>/` — soft-archive (idempotent 200).
        - `POST /api/personnel/<pk>/restore/` — idempotent 200.
        - `DELETE /api/personnel/<pk>/permanent-delete/` — needs
          `can_permanently_delete`; 409 unless already archived; 204.
        - `PATCH /api/personnel/<pk>/training-record/<training_key>/` —
          `{year_attained:<int>}` upsert → 200, `{year_attained:null}`
          clear → 204; bad key → 404; out-of-range year → 400; upsert
          wrapped in `transaction.atomic()` with an IntegrityError retry.
        Permission classes in `permissions.py`: `IsAdmin`,
        `CanPermanentlyDelete` (both treat Django superusers as
        satisfying the check). `archived_by` serialized as a username
        string. `config/urls.py` unchanged (Step 2's `apps.core.urls`
        include already covers it).
- [x] **4. Personnel/matrix frontend** (spec Section 5, page 1) — plain
      Django templates + vanilla JS, no build step.
      - Page route: `GET /personnel/` (`apps/core/web_urls.py`, included
        at `/` by `config/urls.py`; `/` redirects to it). View
        `personnel_matrix_page` is `@login_required` + `@ensure_csrf_cookie`,
        renders only a shell — all data is fetched client-side from the
        Step 3b API. Non-admins get an "admin account required" notice
        instead of the grid.
      - Templates in `apps/core/templates/` (`core/base.html`,
        `core/matrix.html`, `registration/login.html`); static in
        `apps/core/static/core/` (`matrix.css`, `matrix.js`).
      - Matrix UI: district (required) + municipality (optional) +
        Active/Archived pickers; two-row header (MANAGERIAL/SKILLS bands
        over the 27 training columns) with a sticky Name column; all 5
        identity fields + every training-year cell inline-editable
        (blur → PATCH); "+ New Personnel" modal; per-row Archive /
        Restore. Permanent-delete is deliberately NOT here (spec puts it
        on page 7).
      - Login: `django.contrib.auth.urls` mounted at `/accounts/`
        (matches the pre-set `LOGIN_URL`) + a minimal
        `registration/login.html`. Logout is a POST form in the top bar.
      - `settings.py`: under `DEBUG`, `STORAGES["staticfiles"]` falls
        back to plain `StaticFilesStorage` so `{% static %}` works
        without `collectstatic`.
      - `apps/core/management/commands/seed_personnel.py` — dev aid
        (`python manage.py seed_personnel [--flush]`): creates an
        `admin`/`admin` ADMIN user + 20 Personnel across 6 municipalities
        / 3 districts, 73 training cells, 2 archived rows. Idempotent.
        `db.sqlite3` stays gitignored — the command is the source of truth.
      - Browser-tested (headless Chromium): found and fixed a header bug
        — `rowspan="2"` identity `<th>`s + `position: sticky` collapsed
        the MANAGERIAL/SKILLS band row in Chrome; header rebuilt as two
        full rows, no rowspan.
- [x] **5. Remaining core models + migrations** (spec Section 3.1, 3.2),
      applying Section 2's decisions as they're built. Done in two parts —
      9 models total, all in `apps/core/models.py`, migrations
      `core/0003` (5a) + `core/0004` (5b): `Category`, `Staff`,
      `InventoryItem`, `ItemHolderLog`, `StockMovement`,
      `InventoryRequest`, `TrainingSchedule`, `TrainingRegistration`,
      `ManualAttendee`.
  - [x] **5a. Inventory core (§3.1)** — `Category`, `Staff`,
        `InventoryItem`, `ItemHolderLog`, `StockMovement`,
        `InventoryRequest` appended to `apps/core/models.py`, migration
        `core/0003`. Nested `TextChoices` per model (`Staff.Status`,
        `InventoryItem.Condition`, `ItemHolderLog.Action`,
        `StockMovement.MovementType`, `InventoryRequest.Status`). Applied:
        2.10 (no `Category.icon`), 2.11 (free-text `unit`), 2.3 (full
        `is_archived`/`archived_at`/`archived_by` triple on Staff + Item,
        not just the bare bool), 2.12 (`InventoryRequest.decided_by`/
        `decided_at`). `Staff.photo` + `InventoryItem.image` are
        `ImageField` → **Pillow** added to `requirements.txt`. The atomic
        stock logic (2.1/2.12) and `ItemHolderLog` auto-write are
        deferred to Step 6 (CRUD); no serializers/views/admin yet.
  - [x] **5b. Training events (§3.2)** — migration `core/0004`.
        `TrainingSchedule` (nested `Status` UPCOMING/ONGOING/COMPLETED/
        CANCELLED; real `is_archived`/`archived_at`/`archived_by` triple
        orthogonal to `status` per 2.3; `matrix_training_key`
        `CharField(blank=True, choices=TRAINING_CATALOG_CHOICES)` — no
        `null=True`, no `TrainingType` model per 2.4; `created_by`→User
        SET_NULL). `TrainingRegistration` (nested `Status` REGISTERED/
        CANCELLED + `cancelled_at` soft-cancel per 2.6; `training`+`user`
        both CASCADE; **no `unique_together`** — the not-registered-twice
        check is Step 6). `ManualAttendee` (`training`→CASCADE;
        `municipality` choice off `MUNICIPALITY_CHOICES`, no FK, per
        §1.1; `org_affiliation` is the shared `choices.OrgAffiliation`,
        not a re-declared enum, per 2.5). The attendance→`TrainingRecord`
        auto-upsert is Step 6.
- [x] **6. Backend CRUD for the rest of inventory** (spec Section 4).
      Done in three sub-steps. Full route surface now live (all on the
      `SimpleRouter` in `apps/core/urls.py` unless noted), every write
      ADMIN unless marked otherwise:
      `/api/categories/…` · `/api/staff/…` (+`archived/`, `restore/`,
      `permanent-delete/`) · `/api/items/…` (+`archived/`, `restore/`,
      `permanent-delete/`, `<pk>/holder-history/`; STAFF may GET active
      list/detail) · `/api/movements/` + `/api/movements/add/` ·
      `/api/requests/` (STAFF own-only) + `/api/requests/<pk>/approve/` ·
      `/api/trainings/…` (+`archived/`, `restore/`, `permanent-delete/`,
      `<pk>/register/`, `<pk>/cancel-registration/`,
      `<pk>/registrations/`, `my-registrations/`,
      `<pk>/attendance/<user_id>/`; STAFF may GET active + self-register/
      cancel/see own) · `/api/trainings/<tpk>/manual-attendees/…`
      (explicit nested `path()` entries, ADMIN-only, hard delete).
  - [x] **6a. Catalog + custody CRUD** — `CategoryViewSet`,
        `StaffViewSet`, `InventoryItemViewSet` on the `SimpleRouter` in
        `apps/core/urls.py` (`/api/categories/`, `/api/staff/…`,
        `/api/items/…` — all §4 routes incl. `archived/`, `restore/`,
        `permanent-delete/`, and `items/<pk>/holder-history/`). New
        `ArchiveLifecycleMixin` in `views.py` factors the soft-archive
        lifecycle (list=active, `GET archived/`, `DELETE`=idempotent
        soft-archive 200, `restore/`, `permanent-delete/` 409-unless-
        archived) — **reused by `TrainingScheduleViewSet` in 6c**. New
        `IsAdminOrReadOnly` permission (STAFF may GET active items;
        every write + `archived/` + `holder-history/` is ADMIN).
        Behavioral pieces landed: `remove_photo` in `StaffViewSet.update`
        (2.7); `ItemHolderLog` auto-write on item create-with-holder and
        on PATCH holder change (old→REMOVED, new→ASSIGNED, `holder_note`
        carried), `holder-history` returns them newest-first;
        `InventoryItem.quantity` stripped in the serializer's `update()`
        (writable on create only); `CategoryViewSet.destroy` → 409 while
        the category still has items. No migration.
  - [x] **6b. Stock integrity** — `apps/core/services.py`:
        `apply_stock_movement(item, qty, movement_type, *, performed_by,
        note)` is the **only** path that changes `InventoryItem.quantity`
        after creation. One atomic attempt (`_apply_stock_movement_once`,
        `@transaction.atomic`) does: `select_for_update()` on the item
        (real row-lock on Postgres, no-op on SQLite); OUT insufficiency
        check *before* any write; quantity moved by a **single
        conditional `UPDATE … SET quantity = quantity ± n WHERE
        quantity >= n`** so an OUT can never overdraw on any backend
        (0 rows touched ⇒ lost a race ⇒ `InsufficientStock`); then the
        `StockMovement` row. `apply_stock_movement` wraps that in a
        bounded **retry-on-"database is locked"** loop
        (`_LOCK_RETRIES=6`, 50 ms×n backoff) — needed because the
        in-memory shared-cache SQLite test DB raises `SQLITE_LOCKED` on a
        second concurrent writer instead of waiting; a practical no-op on
        Postgres (there `select_for_update` blocks rather than erroring),
        and `InsufficientStock` is never retried. Concurrency proven with
        real threads + a `Barrier` (`Step6bConcurrencyTests`,
        `TransactionTestCase`): two OUTs that together overdraw ⇒ exactly
        one succeeds; two that both fit ⇒ both succeed.
        Endpoints: `GET /api/movements/` (`?item=`) + `POST
        /api/movements/add/` (ADMIN; `InsufficientStock`→400, no partial
        state; archived item→400). `GET/POST /api/requests/` (STAFF sees/
        creates own only, `requested_by`+`PENDING` set server-side;
        ADMIN sees all) + `PATCH /api/requests/<pk>/approve/` (ADMIN;
        `{"decision":"APPROVED"|"REJECTED","note"?}`; PENDING-only→409
        otherwise; REJECTED sets status/decided_by/decided_at; APPROVED
        calls the same `apply_stock_movement` (OUT) + decides in one
        transaction per 2.12, `InsufficientStock`→400 leaves it PENDING;
        the movement note records `Request #<pk> approved by <user>`).
        No migration.
  - [x] **6c. Training events + matrix bridge** — migration `core/0005`
        adds nullable `Personnel.user` OneToOne→User (SET_NULL,
        `related_name="personnel_profile"`); **no API-writable linking
        endpoint** (spec §4 doesn't call for one — link via admin/shell,
        or add `user` to `PersonnelSerializer` later).
        `TrainingScheduleViewSet` reuses `ArchiveLifecycleMixin`; its own
        `get_queryset` also honours `?archived=true`/`all` on the list
        for ADMIN. `register/` enforces, in order → 409: not archived +
        `status` ∈ (UPCOMING, ONGOING); `registration_deadline` not
        past; `max_slots` not reached (REGISTERED count); no existing
        REGISTERED row. `cancel-registration/` soft-cancels the caller's
        REGISTERED row (404 if none) → 200; re-registering makes a fresh
        REGISTERED row, the CANCELLED one is kept. `registrations/` is
        the ADMIN roster; `my-registrations/` is the caller's own.
        `attendance/<user_id>/` (`{"attended": bool}`, ADMIN): toggles
        the reg's `attended`; when `attended` and
        `training.matrix_training_key` set, upserts
        `TrainingRecord(personnel=Personnel.objects.get(user=user_id),
        training_key, year_attained=date_start.year)` via
        `update_or_create` — response carries `matrix_updated` and, when
        false, a `matrix_reason` ("no linked Personnel record" / "year N
        outside the matrix range" / "no matrix_training_key").
        `attended: false` never deletes an existing `TrainingRecord`.
        `ManualAttendeeViewSet` (`viewsets.ViewSet`, ADMIN): nested
        list/create/destroy(**hard**, 204)/`set_attendance` — attendance
        here is a plain toggle, never a `TrainingRecord` upsert.
        `ManualAttendeeSerializer` adds a computed `district`.
- [~] 7. Remaining frontend pages (spec Section 5, pages 2–8) — plain
      Django templates + vanilla JS, no build step. Sub-split:
      **7a** shared infra + Categories + Staff · **7b** Equipment +
      Stock movements · **7c** Requests · **7d** Training schedules ·
      **7e** Archived (tabbed). Each its own plan→build→verify (headless
      Chromium click-through)→commit cycle.
  - [x] **7a. Shared infra + Categories + Staff.**
        - `static/core/common.js` → `window.App`: `api()` (fetch + CSRF;
          also sends `FormData` as multipart), `el()`, `setStatus(node,…)`,
          `flash()`, `summarise()`, `openModal(form, onSubmit)`,
          `downloadCsv()`. `static/core/common.css`: topbar/nav,
          `.notice`, `.toolbar`, `.status`, buttons + `button.danger`,
          `.data-table` (bordered, sticky header, zebra, `.cell-input`,
          `img.thumb`), `.modal*`, `.flash-*`/`.saving`, `.login-box`.
        - `apps/core/context_processors.py:role` (wired in
          `settings.TEMPLATES`) → `is_admin` / `can_permanently_delete`
          on every template. `base.html` loads `common.{css,js}`, adds
          `{% block extra_head %}`, and a **role-gated nav**: ADMIN sees
          all 8 links, STAFF sees only Equipment / Requests / Trainings.
          `/` (`home_page`) redirects by role. The 5 not-yet-built routes
          (`equipment/`, `movements/`, `requests/`, `trainings/`,
          `archived/`) point at `coming_soon_page` so nav resolves now.
        - `matrix.js`/`matrix.css` refactored onto the shared helpers
          (matrix.js aliases `el/api/flash` from `App`, delegates
          `setStatus`; matrix.css keeps only `#grid` rules). Full
          personnel-matrix click-through re-verified — behaviour
          unchanged.
        - **Categories page** (`/categories/`, `categories.js`): inline
          add-row + blur-to-save name/description + `item_count` +
          delete (409-with-message if it still has items). **Staff page**
          (`/staff/`, `staff.js`): table w/ photo thumbnail; modal
          create/edit (multipart photo upload); "Remove current photo"
          checkbox on edit → `remove_photo`; per-row Archive. Both
          ADMIN-only (STAFF → notice). No migration.
  - [ ] **7b. Equipment dashboard + Stock movements** (pages 2, 4).
        Not started.
  - [ ] **7c. Requests + approval flow** (page 5). Not started.
  - [ ] **7d. Training schedules** (page 6) — list + create/edit +
        archive + expandable per-schedule panel (roster + attendance
        toggle w/ matrix-bridge feedback + manual attendees). Not started.
  - [ ] **7e. Archived** (page 7) — tabbed Items/Staff/Trainings/
        Personnel, restore + conditional permanent-delete. Not started.
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

On branch `main`: `11c8a3c` scaffold → Step 2 reference-data → Step 3a/3b
Personnel models + CRUD + auth → Step 4 personnel/matrix frontend → Step 5
remaining core models (`core/0003` inventory + `core/0004` training
events) → Step 6 full inventory CRUD (6a catalog/custody, 6b stock
integrity `services.py`, 6c training events + `attendance→TrainingRecord`
bridge, `core/0005` `Personnel.user`) → Step 7a shared frontend infra
(`common.js`/`common.css`/`context_processors.py`, role-gated nav) +
Categories & Staff pages. Steps 1–6 + 7a done; Step 7b (Equipment + Stock
movements pages) is next. Remote `origin` is
`https://github.com/Kienny043/Pdrrmo-Inventory.git`; `main` tracks
`origin/main`.

Backend note — stock integrity (`apps/core/services.py`):
`apply_stock_movement` is the ONLY path that changes
`InventoryItem.quantity` after creation (so every change writes a
`StockMovement` audit row). It does `select_for_update()` (real on
Postgres, no-op on SQLite) + an OUT-insufficiency check before any write
+ a single conditional `UPDATE … WHERE quantity >= n` (0 rows ⇒
`InsufficientStock`) so overdraw is impossible on any backend, wrapped in
a bounded retry-on-"database is locked" loop (needed for the in-memory
SQLite test DB; a no-op on Postgres). Request approval (2.12) calls the
exact same function.

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
