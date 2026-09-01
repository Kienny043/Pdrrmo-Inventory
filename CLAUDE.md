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
- **~~No build step for v1~~ — SUPERSEDED.** v1 shipped as plain Django
  templates + vanilla JS (Steps 4 + 7) for speed, then the frontend was
  rebuilt as a React 19 + Vite + Tailwind SPA across R1–R7 (matching
  `PDRRMO_v3`'s design system) and the template layer was **deleted at
  the R7 cutover**. There is a build step now (`frontend/`, `npm run
  build` → `frontend/dist/`). Folding this SPA into `PDRRMO_v3`'s actual
  app is still a later concern (spec Section 7, step 11).
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
| Auth           | JWT (`djangorestframework-simplejwt` 5.5.1) for the React SPA — `POST /api/token/` + `/api/token/refresh/`; `SessionAuthentication` kept for the Django admin, `BasicAuthentication` for curl. 60-min access / 7-day refresh. |
| Database       | SQLite (local dev, default) / PostgreSQL via `DATABASE_URL` (prod — `dj-database-url` 2.3.0, `psycopg2-binary` 2.9.10) |
| Static files   | `whitenoise` 6.8.2 (`CompressedManifestStaticFilesStorage`) for admin assets; also serves the built SPA (`WHITENOISE_ROOT = frontend/dist`) |
| Config         | `python-dotenv` 1.2.2, `.env`-based (`backend/.env`, gitignored; `backend/.env.example` checked in). `django-cors-headers` 4.9.0 wired but env-gated + empty (single-origin deploy). |
| Deployment     | `gunicorn` 23.0.0. **Single-origin:** Django + whitenoise serves `frontend/dist/` (`/` + `/assets/*` as real files, a SPA catch-all → `index.html` for client-side routes); no CORS. Render + external Postgres planned (spec Section 7 step 10). |
| Frontend       | **React 19 + Vite 8 + Tailwind v4 SPA** (`frontend/`, own `package.json`; `react-router-dom` v7, `axios`, `lucide-react`). Design matches `PDRRMO_v3` per `docs/design-system-export.md`. Dev: Vite server proxies `/api` `/admin` `/media` to Django on `:8000`. *(The original plain-Django-templates + vanilla-JS frontend — Step 7 — was rebuilt in React across R1–R7 and deleted at R7; see below.)* |
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
- [x] **7. Remaining frontend pages** (spec Section 5, pages 2–8) —
      plain Django templates + vanilla JS, no build step. Done in five
      sub-steps: **7a** shared infra + Categories + Staff · **7b**
      Equipment + Stock movements · **7c** Requests · **7d** Training
      schedules · **7e** Archived (tabbed). All 8 pages live; nav
      role-gated via `context_processors.role`; shared `common.js` /
      `common.css` helpers. Each sub-step verified with a headless
      Chromium click-through.
      > **⚠ Superseded and removed.** This entire plain-template + vanilla-JS
      > frontend (its `templates/`, `static/core/*.{js,css}`, `web_urls.py`,
      > `context_processors.py`, and the page views in `views.py`) was
      > rebuilt as a React SPA across R1–R7 and **deleted at the R7 cutover**.
      > The 7a–7e detail below is kept as a historical record of what the
      > pages did (behaviour the React versions match), not as a description
      > of code that still exists. See "Frontend Rebuild (React) — Steps
      > R1–R7" below.
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
  - [x] **7b. Equipment dashboard + Stock movements** (pages 2, 4).
        No migration.
        - **Equipment** (`/equipment/`, `equipment.js`): `.data-table`
          with name/brand/category/qty/unit/condition/holder/remarks/
          acquired; client-side category filter + name/brand substring
          search; **CSV export** via `App.downloadCsv` (columns: name,
          brand, category, quantity, unit, condition, holder,
          date_acquired, remarks). ADMIN also gets +New Item and per-row
          Edit / History / Archive. Add/edit **modal** sends scalars/FKs
          as JSON, then a follow-up `FormData` PATCH for the image if a
          file was picked (avoids multipart-null on the nullable holder
          FK); `quantity` is disabled on edit (serializer strips it).
          Holder-history **modal** → `GET /api/items/<pk>/holder-history/`
          newest-first. STAFF: read-only table + CSV only (`#app`
          `data-can-edit` gates the JS).
        - **Stock movements** (`/movements/`, `movements.js`):
          ADMIN-only (STAFF → notice). Inline record-movement form →
          `POST /api/movements/add/`; on a 400 the `InsufficientStock`
          message renders in a dedicated `#form-error` line, not a
          transient flash. Movement log + `?item=` filter dropdown.
        - `common.css` gained `.record-form` + a bare `.form-error`.
        - Two click-through bugs found + fixed: `form.elements.item`
          resolves to the collection's `item()` method, not the control
          named "item" (switched to `querySelector`); an empty `<tbody>`
          isn't "visible" to Playwright (assert on `.data-table`).
  - [x] **7c. Requests + approval flow** (page 5). `/requests/`,
        `requests.js`. No migration. Visible to **both roles**: STAFF and
        ADMIN both get the new-request form (item `<select>` + qty +
        note → `POST /api/requests/`); `GET /api/requests/` is
        server-scoped so STAFF only ever see their own rows. Table: item
        · qty · status · note · requester · decided-by. STAFF: no actions
        column. ADMIN: per **PENDING** row an Approve / Reject pair →
        `PATCH /api/requests/<pk>/approve/ {decision}`; a 400
        (`InsufficientStock`) renders the message in a `.form-error` on
        that row's actions cell and leaves the row PENDING (Approve
        stays enabled to retry); decided rows render **no controls at
        all** (client-side, not relying on the backend 409).
        - Also fixed a stale test: `test_not_yet_built_pages_render_
          placeholder` still asserted `/equipment/` shows the
          coming-soon page — outdated since 7b made it real (the 7b
          suite run missed it). Now checks `/trainings/` + `/archived/`.
  - [x] **7d. Training schedules** (page 6). `/trainings/`,
        `trainings.js` + `trainings.css`. No migration.
        - List (both roles): title/dates/venue/status/matrix-label/slots/
          deadline/reg-count. Per-row **Register/Cancel** — if a
          client-side blocker applies the button is disabled with the
          specific reason (`training is archived` / `registration closed
          (<status>)` / `registration deadline passed` / `training is
          full` / `you are already registered`); a server 409 also
          surfaces its `detail`.
        - ADMIN: `+ New Training` + `View: Active/Archived`. Create/edit
          **modal** with a `matrix_training_key` `<select>` split into
          `<optgroup>` MANAGERIAL/SKILLS from `GET /api/training-catalog/`.
          Per-row **Details** (expand) / Edit / Archive; archived view:
          Restore + Delete (permanent-delete, gated on
          `can_permanently_delete`, 409-unless-archived).
        - **Expandable panel** (ADMIN): Registrations sub-table with an
          attendance checkbox per registrant → `PATCH
          …/attendance/<user_id>/`; the response's `matrix_updated`
          drives an inline note — "✓ matrix updated" / "matrix not
          updated — <reason>" / "attendance cleared" on uncheck. Manual
          attendees sub-table (list + add form w/ municipality `<select>`
          + org-affiliation + delete + attendance checkbox), prefaced by
          a static note that manual attendees do **not** feed the matrix.
        - `TrainingRegistrationSerializer` gained a read-only `user_id`
          (`PrimaryKeyRelatedField(source="user")`) — the roster returns
          `user` as a username, but the attendance route keys on the
          numeric id.
  - [x] **7e. Archived** (page 7). `/archived/`, `archived.js`.
        ADMIN-only (STAFF → notice, no nav link). No migration.
        Tabbed **Items / Staff / Trainings / Personnel**, driven by one
        data-config array (`{url, base, cols}` per tab) — no per-tab
        logic; every archivable resource shares the `<base>/<id>/restore/`
        + `<base>/<id>/permanent-delete/` shape. Sources:
        `GET /api/{items,staff,trainings}/archived/` and
        `GET /api/personnel/?archived=true`. Per row: **Restore** (all
        admins); **Delete permanently** rendered **only when
        `can_permanently_delete`** (button absent, not disabled;
        `#app data-can-delete` gates the JS). `.tabs` strip added to
        `common.css`. Cleanup: removed the now-dead `coming_soon_page`
        view + `coming_soon.html` + the stale placeholder test, replaced
        by `test_every_nav_route_resolves_to_a_real_page` (all 8 nav
        routes are real pages). **Step 7 complete.**
- [x] **8. Full `admin.py` registration for every model** (spec 2.9) —
      `apps/core/admin.py` (new; no migration) registers all 12 models.
      Fields set only by the API's atomic/lifecycle paths are read-only
      in the admin so it can't break an invariant or falsify an audit
      trail: the archive triple (`is_archived`/`archived_at`/
      `archived_by`) on Staff/Item/TrainingSchedule/Personnel; audit FKs
      (`performed_by`/`decided_by`/`archived_by`/`created_by`); all
      timestamps; `InventoryRequest.status`/`decided_by`/`decided_at`;
      `TrainingRegistration.status`/`attended`/`registered_at`/
      `cancelled_at`; `InventoryItem.quantity` read-only **on change
      only** (editable on add) via `get_readonly_fields`;
      `Personnel.district` (a property). `StockMovement` and
      `ItemHolderLog` are **wholly view-only** (add/change/delete all
      denied) — a manual edit would bypass
      `services.apply_stock_movement`. `TrainingRecord` stays editable
      except `updated_at` (year corrections are a legit support case).
      **`Personnel.user` is editable via `autocomplete_fields`** — the
      admin is the account-linking UI, closing the 6c/7d gap (the API
      still has no linking endpoint). Inlines: Category→InventoryItem
      (view-only), InventoryItem→StockMovement+ItemHolderLog (view-only),
      TrainingSchedule→TrainingRegistration (status/attendance read-only)
      +ManualAttendee (editable), Personnel→TrainingRecord (editable).
      `UserProfile` fully editable (role / `can_permanently_delete`), and
      a custom `UserAdmin` (unregister + re-register `User`) carries a
      `UserProfileInline` so role is settable from the user page + a
      `core_role` changelist column. `seed_personnel.py` now makes the
      seeded `admin` user `is_staff`+`is_superuser` (set unconditionally
      each run) so `/admin/` is usable by the dev login. `Step8AdminTests`
      (7 tests): all 12 in `admin.site._registry`; all 12 changelists →
      200; view-only admins forbid add (403); change pages with inlines
      load; add pages load for editable models; the quantity
      readonly-on-change-only rule; the User page renders the profile
      inline.
- [x] **9. End-to-end testing** — four real-world workflows exercised as
      one continuous headless-Chromium session each, through the actual
      UI, against one evolving dev DB (dedicated fixture accounts:
      `mgarcia` plain non-superuser ADMIN, `rlopez`/`jnavarro`/`baquino`
      STAFF; `jnavarro`→Personnel *Josie Navarro* / Catanauan,
      `baquino`→*Dennis Cruz* / Lucena City). **No application code
      changed** — this step proves existing code holds together. **86/86
      assertions passed.**
  - **Chain 1 — personnel matrix across districts (21/21):** browsed
      First (Tayabas City + Lucban shown together, 7 rows) → Lucban only
      (3 rows, Municipality column hidden) → Second/Sariaya → Third/
      Mulanay, editing a training-year cell or identity field in each;
      archived view showed only the 2 seed-archived rows; edits persisted
      across in-session navigation *and* a full page reload; row sets
      stayed disjoint per district (data isolation held).
  - **Chain 2 — request → approval → stock deduction (18/18):** STAFF
      `rlopez` submitted a qty-5 request (PENDING, no actions cell);
      plain-ADMIN `mgarcia` approved it → APPROVED/decided-by; Equipment
      page then showed 20→15 and Stock movements showed
      `OUT / 5 / "Request #N approved by mgarcia"`. Negative tail: a
      qty-999 approve stayed PENDING, showed the inline
      insufficient-stock error on the row, and left quantity at 15 (no
      partial deduction). *(One assertion initially failed on the test's
      own regex — the real message reads "Only N … on hand; M requested."
      — fixed the assertion only; no app change.)*
  - **Chain 3 — training → attendance → matrix auto-populate (17/17):**
      `mgarcia` created a training with `matrix_training_key=RDANA` via
      the modal; `jnavarro` and `baquino` self-registered; attendance was
      ticked for **jnavarro only**. On the Personnel matrix page itself:
      *Josie Navarro's* RDANA cell flipped blank→2026 (POSITIVE), and —
      **the load-bearing assertion of this whole pass** — *Dennis Cruz's*
      RDANA cell stayed **blank** (registered but never marked attended;
      asserted directly as `value === ""`, not inferred from the positive
      case). Un-ticking jnavarro's attendance ("attendance cleared") left
      the 2026 TrainingRecord intact (invariant: un-mark never deletes).
  - **Chain 4 — archive/restore/permanent-delete via the Archived page
      (30/30):** for Staff, InventoryItem, TrainingSchedule and Personnel
      (throwaway records), each: archived from its own page → listed in
      the right Archived-page tab → **Restore** there → back in the
      active list (`is_archived:false`) → re-archived → **Delete
      permanently** there → gone, detail endpoint 404. The Personnel tab
      kept aggregating the 2 seed-archived rows alongside.
  - Teardown: `seed_personnel --flush` + explicit drop of the fixture
      users / Category / Item / workflow rows → back to the pristine
      20 Personnel / 73 TrainingRecords / 2 archived baseline.
- [ ] 10. Deploy (Render + external Postgres, unless a faster option
       makes more sense at that point). The single-origin serving
       mechanism is already wired (`WHITENOISE_ROOT = frontend/dist`,
       SPA catch-all) — a deploy needs the build/collectstatic/migrate
       steps + Render config, nothing more in the app.
- [ ] 11. *(Later, separate effort)* Integration into `PDRRMO_v3`'s
       real React frontend and JWT/role system. **Unchanged in scope by
       the R1–R7 rebuild** — this project's React SPA being production
       here does not fold it into `PDRRMO_v3`; that is still its own
       later effort.

## Frontend Rebuild (React) — Steps R1–R7  ·  **COMPLETE**

A parallel track, run after Step 9: this project's frontend was rebuilt
from plain Django templates + vanilla JS into a React 19 + Vite +
Tailwind v4 SPA that visually matches `PDRRMO_v3`'s design system, while
keeping the project standalone (own repo, own deploy). **All of R1–R7
are done**, and at the R7 cutover the template frontend was deleted —
the React SPA is now the only frontend, served single-origin by Django +
whitenoise. **This is not Step 11** — folding into `PDRRMO_v3` itself is
still a later, separate effort.

**Authoritative design reference:** [docs/design-system-export.md](docs/design-system-export.md)
— a one-time, self-contained snapshot of `PDRRMO_v3/frontend`'s visual
system (color tokens, fonts, component recipes, layout). Copied in
(byte-identical to the PDRRMO_v3 copy) so this repo never needs to reach
into `../PDRRMO_v3/`. It is a frozen snapshot, not a living reference.

### Decisions locked in (so a future session doesn't re-derive them)

- **Auth: JWT now** (`djangorestframework-simplejwt`), *not* deferred to
  Step 11. `DEFAULT_AUTHENTICATION_CLASSES` = `[JWTAuthentication,
  SessionAuthentication, BasicAuthentication]` — JWT leads for the SPA;
  Session stays for the Django admin **and** the plain-template UI that
  remains live until the R7 cutover; Basic stays for curl. Rationale:
  the design export's own `apiFetch` is built around JWT refresh-on-401,
  and Step 11 will be JWT anyway, so the auth layer is already in its
  final shape. `SIMPLE_JWT`: 60-min access, 7-day refresh.
- **Deploy shape: single-origin.** Production = Django + whitenoise
  serves the built React bundle (matches the existing whitenoise setup
  and `quick-sitrep`'s pattern), so no CORS/cross-site-cookie
  complexity. `django-cors-headers` is wired but **env-gated and empty
  by default** — a fallback for a hypothetical split-origin deploy, not
  load-bearing. Dev = Vite server proxies `/api`, `/admin`, `/accounts`,
  `/static`, `/media` to Django on `:8000` (single origin in dev too).
- **Template UI stays alive through the whole rebuild**, deleted in one
  pass at R7 — there is always a working UI during the transition.
- **Component layer:** a thin set of primitives (`Button`, `Modal`,
  `Table`, `Field`, `Badge`, `Tabs`, `PageHeader`, `Sidebar`,
  `EmptyState`, `ErrorBanner`, `Spinner`, `ProtectedRoute`) that emit
  the design export's *exact* class strings. This is a deliberate,
  approved divergence from PDRRMO_v3's hand-composed-inline-per-page
  convention (the source has no component library by choice).
- **Icons:** `lucide-react` (the export notes it's visually near-identical
  to PDRRMO_v3's hand-drawn SVGs).
- **Validation:** native HTML `required` + an `ErrorBanner` for
  submit-time/business errors, **plus** the inline per-field messages
  the current vanilla-JS frontend already has — do not regress to bare
  `alert()` like the source app.
- **`GET /api/me/`** shape: `{ username, role, is_admin,
  can_permanently_delete }` — the SPA's equivalent of
  `context_processors.role`.
- **Stack (matches the design export):** React 19 + Vite + Tailwind v4
  (CSS-config, no `tailwind.config.js` — the `@theme` tokens live in
  `frontend/src/index.css`), `react-router-dom` v7, `axios`. No icon kit
  beyond lucide, no UI/component kit, no toast/animation/state library
  (React Context only). `frontend/` is a sibling of `backend/`.

### Sub-steps (same plan → build → browser-verify → commit cadence)

- [x] **R1. Scaffold + backend auth prep.** `frontend/` (Vite + React 19
      + Tailwind v4, `index.css` = design-export §1 verbatim, dev proxy,
      `.env.example`, gitignores). Backend: `django-cors-headers`
      (env-gated), SimpleJWT `POST /api/token/` + `/api/token/refresh/`,
      `GET /api/me/`; `SessionAuthentication`/`BasicAuthentication` kept.
      Behavior change: credential-less API requests now return **401**
      (JWT supplies `WWW-Authenticate`), not the 403 that
      session-auth-first produced — 401 is the correct code and what the
      SPA's refresh-on-401 path needs; 3 existing "unauthenticated →
      403" assertions updated to 401 (`ReferenceEndpointTests`,
      `PersonnelPermissionTests`, `Step6aPermissionTests` — the
      authenticated-but-forbidden 403s are unchanged). New tests:
      `R1TokenAuthTests` + `R1MeEndpointTests` (11). Template UI verified
      unaffected.
- [x] **R2. Shared infra + Login.** `frontend/src/` — `lib/tokens.js`
      (localStorage access/refresh), `lib/api.js` (axios: bearer on every
      request; response interceptor refreshes once on 401 via bare axios,
      retries the original, else `clearTokens()` + fires the registered
      auth-failure handler; DRF error body → `Error(message)` + `.status`/
      `.data`; `apiGet/Post/Patch/Delete` helpers), `lib/auth.jsx`
      (`AuthProvider`/`useAuth` → `{user,isLoading,login,logout}`, `user`
      from `GET /api/me/` on login and on app-load-if-token;
      `defaultRouteFor` mirrors backend `home_page`). Primitive component
      layer emitting the design export's **exact** class strings:
      `Button` (primary/secondary/chip, no red variant), `TextAction`
      (navy/red/green/muted + optional `confirm`), `Card`, `StatTile`,
      `Table`/`THead`/`Th`/`Tr`/`Td`, `Modal` (md/xl/2xl), `Field` +
      `INPUT_CLASS` + `SearchInput` (Field keeps an optional per-field
      `error` — decision #5), `Badge` (§2 status→class map + our
      training enums), `Tabs`, `Spinner`/`LoadingSection`/
      `FullScreenSpinner`, `EmptyState`, `ErrorBanner`, `PageHeader` +
      `PageBody`, `Sidebar` (navy, role-filtered nav via `nav.js` in the
      exact `core/base.html` order, initials avatar, sign-out),
      `AppLayout` (§3 Variant A), `ProtectedRoute` (`allowedRoles`,
      `requireCanDelete`), `PlaceholderPage`. `LoginPage` (real form →
      `/api/token/`, `ErrorBanner` on failure, redirect via
      `defaultRouteFor`). `App.jsx` router: `/login` public; all else
      under `ProtectedRoute` → `AppLayout`, with the 5 ADMIN pages nested
      under a second `ProtectedRoute allowedRoles={['ADMIN']}`; `/` + `*`
      role-redirect. 8 pages are placeholders (real content R3–R6).
      **Confirmed design decision:** a STAFF user hitting an ADMIN-only
      route by direct URL is **silently redirected** to their default
      page (`/equipment`), not shown an in-page notice — a deliberate
      divergence from the Django template, matching the design export's
      §3 `ProtectedRoute` pattern (the role-filtered sidebar never links
      there anyway). Verified headless: admin→8-link sidebar→`/personnel`;
      staff1→3-link sidebar→`/equipment`, `/personnel` & `/archived`
      bounce to `/equipment`; full reload keeps the session; bad creds →
      `ErrorBanner`, no crash; refresh-on-401 proven (corrupt access +
      valid refresh → transparent re-auth; both corrupt → forced logout).
      **No backend changes.**
- [x] **R3. Categories + Staff.** `CategoriesPage.jsx` — `Table` with an
      inline add-row (name + description → `POST /api/categories/`,
      Enter-to-submit, Add disabled while name blank) and per-row
      blur-to-save inline `<input>` edits (`PATCH`, revert + `ErrorBanner`
      on failure), `item_count` cell, red `TextAction` "Delete" with
      `confirm`; a 409 (category still has items) surfaces the server
      message verbatim in an `ErrorBanner`. `StaffPage.jsx` — `Table`
      (photo thumbnail / name / position / department / contact / `Badge`
      status / state / actions) + a `Modal` create/edit form
      (`StaffForm`, remounted per open via `key`) posting multipart
      `FormData` (text fields + optional `photo` + `remove_photo`);
      per-row `TextAction` Edit / Archive(`confirm`). **The "Remove
      current photo" checkbox is `{editing && staff.photo && …}` —
      conditional render, so with no photo the node is absent from the
      DOM entirely, not CSS-`hidden`.** This is the structural fix for
      UI-audit Finding 1 (the template's `[hidden]` attribute was
      defeated by `.modal label { display:flex }`); R3's browser test
      asserts it via DOM node count (`input[name="remove_photo"]` count
      0 on create and when editing a photo-less staff, 1 when editing one
      with a photo), not visual inspection. Backend: one change —
      `config/urls.py` serves `/media/` **under `DEBUG` only** so photo
      thumbnails display in dev (prod media serving deferred to R7 /
      Step 10); DEBUG-gated so the test suite is unaffected (still 199).
      Verified headless: 26/26 — create/inline-edit-persists-across-
      reload/delete-empty/delete-with-items-409-message for Categories;
      create-with-real-PNG-upload (thumbnail actually loads,
      `naturalWidth > 0`) / remove-photo-clears-it / edit-persists /
      archive-is-soft for Staff; no console errors; screenshots match
      the design system.
- [x] **R4. Equipment + Stock movements.** `EquipmentPage.jsx` — `Table`
      (name/brand/category/qty/unit/`Badge` condition/holder/remarks/
      acquired + actions), `SearchInput` name/brand substring filter + a
      category `<select>`. **Role-aware category filter (the audit fix,
      reimplemented in React):** ADMIN options come from `/api/categories/`
      (value = id); STAFF options are derived from distinct
      `item.category_name` (value = name) and `/api/categories/` is not
      fetched at all for STAFF — so the STAFF equipment page can't break
      on the ADMIN-only categories endpoint. `Export CSV` (both roles;
      `lib/csv.js`) exports the visible rows, columns name,brand,
      category,quantity,unit,condition,holder,date_acquired,remarks.
      ADMIN-only: `+ New Item` / Edit `Modal` (`ItemForm`, `key`-remounted)
      — category/holder(`/api/staff/`)/condition selects + image file;
      saves scalars/FKs as JSON then a follow-up `FormData` PATCH for the
      image (avoids the multipart-null-FK problem, mirrors the template);
      **quantity `<input>` `disabled` on edit** and omitted from the edit
      payload. Per-row `TextAction` Edit / History / Archive(`confirm`);
      Holder-history `Modal` → `GET /api/items/<id>/holder-history/`,
      newest-first. `MovementsPage.jsx` — ADMIN-only (route-gated):
      `Card`-wrapped record form (item select w/ "on hand: N", type,
      quantity, note → `POST /api/movements/add/`); a 400 renders the
      server message in an **`ErrorBanner` inside the form** (persistent,
      not a toast); `?item=` filter select + movement-log `Table`.
      New shared helper `lib/csv.js` (`downloadCsv`); `Badge` map gained
      `IN` (green) / `OUT` (blue) for stock-movement type. **No backend
      changes.** Verified headless: 41/41 — Equipment ADMIN
      create-with-image / edit-quantity-disabled / category+search
      filters / holder-history newest-first / CSV columns+rows / archive;
      Equipment STAFF table loads (audit bug absent) + category filter
      from `category_name` + no admin buttons + CSV works; Movements
      ADMIN IN/OUT with on-hand reflected on the Equipment page after
      reload + inline insufficient-stock error + `?item=` filter;
      Movements STAFF redirects to `/equipment`; no console errors;
      screenshots match the design system.
- **R5. Requests + Trainings — SPLIT into R5a + R5b.** Requests and
  Trainings share essentially no surface (different models, different
  endpoints, opposite UI shapes — Requests is one table + a small form +
  two row actions; Trainings is a catalog-grouped modal + an expandable
  roster panel + matrix-bridge feedback + a manual-attendee sub-table +
  the full archive/restore/permanent-delete lifecycle + 5 distinct
  register blockers). Verifying them together buys nothing, and
  Trainings alone is the app's biggest page — it got its own dedicated
  cycle as Step 7d in the template rebuild, same reasoning here.
  - [x] **R5a. Requests.** `RequestsPage.jsx` — `PageHeader`/`PageBody`,
        `Card`-wrapped new-request form (item `<select>` w/ "on hand: N",
        quantity, note → `POST /api/requests/`, both roles). `Table`
        item/qty/`Badge` status/note/requester/decided-by; the list is
        server-scoped so STAFF only ever see their own rows and ADMIN
        sees all (both proven headless, incl. two distinct STAFF users
        not seeing each other's requests). ADMIN gets an actions column;
        a **PENDING** row shows `TextAction` Approve (green) + Reject
        (red, `confirm`) with a small per-row error line (the `Field`
        error style — `text-xs text-pd-red mt-1` — reused inline, not a
        toast, not a cell-filling `ErrorBanner`); on a 400 the
        insufficient-stock message renders there and the row stays
        PENDING with Approve still clickable. **Decided rows render
        `null` in the actions cell — zero controls, not disabled ones**,
        client-side. No new primitives, helpers, or backend changes.
        Verified headless 21/21: both-role visibility + STAFF isolation,
        Approve → APPROVED + decided_by/at + Equipment page shows the
        deduction, Reject → REJECTED + no stock change, insufficient-stock
        Approve → inline row error + stays PENDING + no partial deduction,
        decided rows have no controls; no console errors; screenshot
        matches the design system.
  - [x] **R5b. Trainings.** `TrainingsPage.jsx` (R2 primitives only; no
        backend changes). `Table` title/dates/venue/`Badge` status/matrix
        label/slots/deadline/regs + actions. **Register/Cancel per row
        (both roles):** `registerBlock(t)` computes all 5 blockers
        client-side — archived / `registration closed (<status>)` /
        deadline passed / full / already-registered; a blocked row shows
        a struck "Register" + the reason, an already-registered row shows
        red "Cancel registration" + a `you: REGISTERED` hint, else an
        enabled navy "Register"; a server 409 `detail` surfaces in a
        per-row `text-pd-red` line (the 5th blocker's *string* is
        superseded by the Cancel button, faithful to the template — the
        guard itself is server-enforced, verified via the 409). ADMIN
        active-view row: Details(toggle) / Edit / Archive; archived-view:
        Restore / Delete (only when `can_permanently_delete`). Create/
        edit `Modal` (`TrainingForm`, `key`-remounted) — status `<select>`
        + a matrix-key `<select>` with `<optgroup>` MANAGERIAL / SKILLS
        from `/api/training-catalog/` + a `— none —` option. **Expandable
        ADMIN panel (`RosterPanel`, `<td colspan=9>`):** registrations
        sub-`Table` with an **optimistic** attendance checkbox (flips
        synchronously, reverts on error) → `PATCH …/attendance/<user_id>/`,
        per-row note from the response (`✓ matrix updated` /
        `matrix not updated — <reason>` / `attendance cleared`); manual-
        attendees sub-`Table` (list/add w/ municipality+affiliation
        `<select>`s / delete / optimistic attendance toggle) prefaced by
        a static "**do not feed the training matrix**" note. Optimistic
        checkboxes are a deliberate UX improvement over the template's
        re-fetch-only toggle. Verified headless 42/42: all 5 STAFF
        blockers + register/cancel/re-register-no-dup + 409 double-
        register; ADMIN create-with-matrix-key (optgroups) / edit;
        roster matrix-bridge for a linked user (`✓`) and an unlinked one
        (reason), **cross-checked against the real `/api/personnel/`**
        (Josie Navarro's RDANA cell → 2026), un-mark-doesn't-delete
        invariant, re-tick → still exactly one record; manual attendee
        add (computed district) / attendance / delete; full archive →
        archived-view (blocker #1 shows there) → restore → re-archive →
        permanent-delete → 404. No console errors; screenshot matches
        the design system.
- [x] **R6. Personnel matrix.** `PersonnelPage.jsx` (rewritten) +
      `PersonnelMatrix.css` (new, scoped to `#matrix-grid`). ADMIN-only —
      `/personnel` is already behind `ProtectedRoute allowedRoles=['ADMIN']`
      (R2), so STAFF is redirected to `/equipment` (same effect as the
      template's notice — STAFF gets no data). Filter row: District
      `<select>` (required) + Municipality `<select>` (disabled until a
      district; empty = whole district, Municipality column shown) + View
      `<select>` (Active/Archived) + `+ New Personnel` (disabled until a
      district) — matches the template exactly. **Two-row MANAGERIAL/
      SKILLS banded header built as two FULL `<tr>`s, never rowspan** —
      the template's fix for the Chrome rowspan+sticky collapse.
      **Triple-sticky layout** (`PersonnelMatrix.css`, ported from
      `matrix.css` using the `--color-pd-*` tokens): frozen Name column
      (`left:0`), frozen actions column (`right:0`), sticky two-row
      header (`top:0` / `top:1.7em`), and a **nested-sticky band label**
      (`.band-label{position:sticky;left:170px}`) pinned just past the
      Name column. All 5 identity fields inline-editable in place (name/
      designation/employment_status `<input>`, org_affiliation `<select>`,
      other_drr_training `<textarea>`) blur-to-save `PATCH /api/personnel/
      <id>/`; each of the 27 training cells is a blur-to-save year
      `<input>` hitting `…/training-record/<key>/` (`{year_attained:N}` or
      `{...:null}` to clear); filled cells get the faint green
      `:not(:placeholder-shown)` tint. **New Personnel is a `Modal`**
      (stated: consistent with every other R3–R5 create flow, and an
      inline new row would be unreachable in a 33-column horizontally-
      scrolled grid). Per-row `TextAction` Archive (active) / Restore
      (archived). Verified headless 40/40 — **including measured
      `getBoundingClientRect()` deltas at scrollLeft 0/450/max**: Name
      header+body cells stay at left≈257 (Δ≤2px), the MANAGERIAL band
      label pins at left=427 (~170px past the frozen column), the actions
      header+body cells freeze to the container's right edge (Δ≤3px), and
      the band-row keeps its 24px height with both band labels visible
      (not collapsed — the exact bug class the template build caught).
      Also: inline year-cell + identity edits persist across a full page
      reload; data isolation holds across First/Second/Third districts
      with no leakage; create appears in the right municipality;
      archive→restore round-trips with correct view-toggle behaviour;
      no console errors. **No backend changes.**
- **R7. Archived + cutover.**
  - [x] **R7 Archived page.** `ArchivedPage.jsx` on R2 primitives
        (`Tabs`, `Table`, `TextAction`) — one `TABS` config array
        (`{key,label,url,base,cols}` per tab), no per-tab logic, same
        shape as the template's `archived.js`. 4 tabs Items / Staff /
        Trainings / Personnel from `/api/{items,staff,trainings}/archived/`
        + `/api/personnel/?archived=true`. Per row: `Restore` (green, all
        admins) → `POST <base>/<id>/restore/`; `Delete permanently` (red)
        → `DELETE <base>/<id>/permanent-delete/`, **rendered only when
        `user.can_permanently_delete`** (absent from the DOM, not
        disabled). ADMIN-only via the existing `ProtectedRoute`. Verified
        headless 24/24: all 4 tabs load their archived rows + config
        headers; Restore round-trips for Personnel and Items (row leaves
        the tab, `is_archived:false` in the active list); a real
        permanent-delete → 204 → detail endpoint 404; `Delete
        permanently` absent (count 0) on all 4 tabs for a non-elevated
        admin while `Restore` stays; no console errors. **No backend
        changes.**
  - [x] **R7 cutover — the React SPA is now the production frontend; the
        Django template frontend is gone.** `config/settings.py`:
        `FRONTEND_DIST` const, `TEMPLATES["DIRS"] = [FRONTEND_DIST]`,
        `WHITENOISE_ROOT = frontend/dist` + `WHITENOISE_INDEX_FILE=True`,
        removed `context_processors.role` and the vestigial
        `LOGIN_URL` / `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL`.
        `config/urls.py`: dropped the `web_urls` and `accounts/` includes;
        added a last-pattern SPA catch-all
        `re_path(r"^(?!api/|admin/|media/|static/).*$" → index.html)` so
        direct loads / refreshes of client-side routes work. **Deleted
        (24 files):** `apps/core/templates/` (10, incl.
        `registration/login.html`), `apps/core/static/core/` (12
        `*.{js,css}`), `apps/core/web_urls.py`, `apps/core/
        context_processors.py`. `views.py`: the 9 page views removed
        (`home_page`, `personnel_matrix_page`, …) + now-unused imports.
        `tests.py`: the 5 `Step7*PageShellTests` classes removed (21
        tests). Verified **before** the deletions landed: a 60/60 full
        parity click-through of all 8 React pages + login (both roles, +
        the non-elevated-admin permanent-delete gating); a single-origin
        smoke test (`DEBUG=False`, `collectstatic`, `runserver :8090`) —
        whitenoise serves `/` + `/assets/*`, the catch-all serves
        `index.html` for every deep link + refresh, `/api/*` 401/200,
        `/admin/` 302→login; browser check confirmed the SPA boots,
        routes, and survives a deep-link refresh. Full Django suite:
        **178** (199 − 21). `manage.py check` clean.

## Post-R7: Personnel-roster attendance for trainings

Not part of the original R1–R7 plan — a follow-up feature from real-usage
testing (alongside a small Improvement 1: the Personnel matrix now
defaults its district select to the first district on load, so the page
shows data immediately instead of an empty grid — `frontend/src/pages/
PersonnelPage.jsx`, commit `49243f7`).

**What it adds:** an ADMIN can search for and select an **existing
`Personnel` record** (by name, across all districts — chosen, never
free-typed) and add them to a training's roster. Marking attendance on
such an entry upserts a `TrainingRecord` exactly like the User-linked
attendance bridge does. This is a **third, distinct** attendee type,
each kept unrepurposed:

- `TrainingRegistration` — self-service, requires a `User` account;
  feeds the matrix only if that user is linked to a `Personnel`.
- `ManualAttendee` — free-typed name/municipality/affiliation, no
  `Personnel` link; **never** feeds the matrix.
- `PersonnelAttendee` *(new)* — admin-added FK to an existing
  `Personnel`; an explicit, unambiguous link, so it **does** feed the
  matrix.

**Backend:**
- New model `PersonnelAttendee` (`training` FK CASCADE, `personnel` FK
  CASCADE, `attended`, `added_at`, `added_by` FK SET_NULL,
  `unique_together(training, personnel)`) — migration **`core/0006`**.
  No existing model altered.
- `?search=` on `PersonnelViewSet.get_queryset` — `name__icontains`,
  ADMIN-only, active-only default.
- `PersonnelAttendeeViewSet` (`viewsets.ViewSet`, `IsAdmin`) nested
  under the training, mirroring the `ManualAttendee` route shape —
  explicit `path()` entries in `apps/core/urls.py`:
  - `GET/POST  /api/trainings/<tpk>/personnel-attendees/` — list / add
    (`{personnel: <id>}`; duplicate → **409**
    `"<name> is already on this training's roster."`).
  - `DELETE    /api/trainings/<tpk>/personnel-attendees/<pk>/` — hard
    delete, 204.
  - `PATCH     /api/trainings/<tpk>/personnel-attendees/<pk>/attendance/`
    — `{attended: bool}`; toggles + runs the matrix bridge, response
    carries `matrix_updated` + `matrix_reason`.
- `PersonnelAttendeeSerializer` — embeds `personnel_name`,
  `personnel_municipality`, computed `personnel_district`, `added_by`
  (username).
- **Shared `_matrix_bridge(training, personnel)` helper** extracted from
  the existing User-linked `attendance` action and called from both it
  and the new `set_attendance`. **Pure refactor** — the 8 existing
  `Step6cAttendanceBridgeTests` are untouched and green, confirming zero
  behavior change to the User-linked bridge.
- `admin.py` — `PersonnelAttendeeAdmin` (autocomplete training +
  personnel; `added_by`/`added_at` read-only).

**Frontend:** a third **"Personnel roster"** section in
`TrainingsPage.jsx`'s expandable `RosterPanel`, between "Registrations"
and "Manual attendees". A debounced search-as-you-type `PersonnelPicker`
(hits `?search=`, filters out personnel already on the roster); table of
name / municipality / district / added-by / attendance checkbox (with
`✓ matrix updated` / `matrix not updated — <reason>` / `attendance
cleared` feedback, optimistic) / Remove. A note states attendance here
**does** feed the training matrix — explicitly contrasted with the
"do **not** feed" note on the Manual attendees section just below.

**Tests:** 14 new (`PersonnelRosterModelTests`, `PersonnelSearchParamTests`,
`PersonnelRosterCrudTests`, `PersonnelRosterAttendanceBridgeTests`) —
model round-trip + `unique_together`, `?search=` filtering/permissions,
roster CRUD (perm / dupe-409 / delete-204 / wrong-training-404), the
attendance bridge (upsert with `date_start.year`, out-of-range year,
no-matrix-key, un-mark-preserves, re-mark-no-duplicate), and explicit
confirmation the refactored `_matrix_bridge` leaves the existing bridge
tests green. **Suite: 192** (178 + 14). Verified end-to-end with a
headless-Chromium run against the `DEBUG=False` single-origin server
(15/15): create a matrix-linked training, add a Personnel from a
different municipality than any training context, duplicate-add blocked,
tick attendance → **cross-checked on `/personnel` itself** that the
RDANA cell flipped to 2026, Remove clears the roster entry but not the
`TrainingRecord`.

**Scope:** standalone-system only. Public/portal training registration
and self-service flows remain Step 11 (fold into `PDRRMO_v3`).

## Post-R7: logic / data-consistency audit response

A deeper audit (beyond the earlier UI/button pass) of business-rule gaps,
hidden inconsistencies, and un-surfaced data. Findings grouped by
severity; being worked in three waves, each its own plan-build-verify-
commit cycle.

### Wave 1 — real bugs, fixed outright  ·  **DONE**  (migration `core/0007`, suite **203**)

- **F3** — `EquipmentPage.jsx`'s modal "Remarks" field was bound to
  `description`; the table column + CSV read `remarks`, so typed remarks
  vanished and `remarks` was never settable. Split into two textareas:
  a new **Description** (→ `description`) and **Remarks** (→ `remarks`,
  now correct). No table column added for `description` (kept the
  10-column table readable); both fields round-trip in the modal +
  `/api/items/`. No backend change (serializer already exposed both).
- **D1** — `_matrix_bridge` (`views.py`) now returns
  `(False, "the training is archived")` / `(False, "the personnel
  record is archived")` when either side is archived — added **once
  inside the helper**, so both the User-linked `attendance` action and
  the roster `set_attendance` inherit it. Mirrors the 409 the direct
  cell-edit endpoint already returns. Precedence: no-matrix-key →
  archived-training → no-personnel → archived-personnel → year-range.
  The `attended:false` un-mark path never calls the bridge (unchanged;
  still never deletes).
- **D3** — double-registration race. `TrainingRegistration` gains a
  **partial `UniqueConstraint`** on `(training, user)` `WHERE
  status='REGISTERED'` (migration `core/0007`) — CANCELLED + a fresh
  REGISTERED row still legal (spec 2.6). `register` wraps its
  check+insert in `transaction.atomic()` + `select_for_update()` on the
  training row and catches `IntegrityError` → same `409`.
  `TrainingsPage.jsx` disables Register/Cancel while their request is in
  flight (`rowBusy` state, "Registering…" / "Cancelling…").
- **D4** — `Personnel.district` property now `try/except KeyError →
  None`, matching `ManualAttendeeSerializer` /
  `PersonnelAttendeeSerializer` / `PersonnelAdmin`. One stale
  `municipality` value can no longer 500 the whole `GET /api/personnel/`.
- **PersonnelAttendee create race** — `serializer.save()` wrapped in
  `transaction.atomic()` + `IntegrityError` catch → same `409` the
  sequential duplicate returns, instead of a raw 500.
- **Tests (+11 → 203):** `Wave1MatrixBridgeArchivedTests` (7),
  `Wave1DistrictGuardTests` (2), `Wave1RegistrationRaceTests` (2),
  `Wave1RosterAddRaceTests` (1). The two race classes use real
  **barrier-synchronised concurrent requests** (`TransactionTestCase` +
  threads, like `Step6bConcurrencyTests`), re-run 3× standalone for
  stability — not reasoned about in the abstract. Existing
  `Step6cAttendanceBridgeTests` + `test_matrix_bridge_helper_is_
  behaviour_neutral` untouched and green. F3 verified with a 10/10
  real-browser run (`DEBUG=False` single-origin).

### Wave 2 — functional additions  ·  **DONE**  (no migration, suite **217**)

- **F1** — `Personnel.user` account link is now visible + manageable from
  the SPA. New `GET /api/users/` (ADMIN-only, `{id, username,
  personnel_id, personnel_name}`, optional `?search=`).
  `PersonnelSerializer` gains a **writable** `user` (declared as an
  explicit `PrimaryKeyRelatedField` so DRF attaches no generic
  UniqueValidator) + read-only `user_username`; `validate_user` raises a
  record-named 400 (`"<username> is already linked to <name>."`) when the
  account is linked elsewhere. Link/unlink rides the existing `PATCH
  /api/personnel/<id>/` (ADMIN-only; the archived-guard 409 applies).
  Frontend: a new read+write **"Account"** `<select>` column in the
  matrix grid (— none — / current link / every unlinked account),
  change-to-save, refetches `/api/users/` after a link change so other
  rows' option lists update. `leadRest` 3 → 4.
- **F5** — `DELETE /api/requests/<id>/withdraw/` — `IsAuthenticated`,
  **owner-only** (403 for a non-owner admin; 404 for another STAFF, via
  the existing queryset scope, so IDs aren't disclosed), **PENDING-only**
  (409 otherwise), hard delete → 204. Requests page shows a **"Withdraw"**
  action on any PENDING row whose `requested_by` is the caller; the
  actions column is now always rendered (was ADMIN-only). Mirrors
  training's self-service `cancel-registration`.
- **F7** — History is reachable from the Archived page without restoring.
  `HistoryModal` extracted from `EquipmentPage.jsx` into shared
  `components/ItemHistoryModal.jsx`; new
  `components/TrainingHistoryModal.jsx` (read-only Registrations /
  Personnel roster / Manual attendees, reusing the three existing GET
  endpoints — all already work for archived trainings). `ArchivedPage`
  gains `history: 'item'` / `history: 'training'` keys on the
  Items/Trainings tab configs and a per-row **"History"** action. No
  backend change.
- **Tests (+14 → 217):** `Wave2UsersEndpointTests` (4),
  `Wave2PersonnelAccountLinkTests` (6), `Wave2RequestWithdrawTests` (5).
  F7 is frontend-only, verified in a 20/20 real-browser run
  (`DEBUG=False` single-origin, re-run 2×): F1 link/unlink persistence +
  option filtering + the 400 guard reaching the client; F5 owner-sees-
  Withdraw / admin-doesn't / withdrawn-row-gone; F7 both History modals.

### Wave 3 — UX polish  ·  planned

Registrations empty-state parity (U1); "Archived by" column on the
Archived page (U2); drop Staff's dead "State" column (U4);
permanent-delete confirm text names what's lost (D2, confirm-text
version only); admin-only archived-record detail retrieve (S1);
path-neutral `_matrix_bridge` "no linked Personnel" wording (S2).

**Deferred, out of scope for all three waves:** F2 full production
`/media/` serving (Step 10), F4 (`my-registrations` UI), F6 (admin
removing a registration), blocking permanent-delete on audit-trail
presence (D2's alternative fix — doing the confirm-text version instead).

## Current Git State

On branch `main`: `11c8a3c` scaffold → Step 2 reference-data → Step 3a/3b
Personnel models + CRUD + auth → Step 4 personnel/matrix frontend → Step 5
remaining core models (`core/0003` inventory + `core/0004` training
events) → Step 6 full inventory CRUD (6a catalog/custody, 6b stock
integrity `services.py`, 6c training events + `attendance→TrainingRecord`
bridge, `core/0005` `Personnel.user`) → Step 7 all frontend pages
(7a shared infra + Categories/Staff, 7b Equipment + Stock movements,
7c Requests, 7d Training schedules, 7e Archived) → Step 8 full
`admin.py` (all 12 models, `apps/core/admin.py`, no migration;
lifecycle/audit fields read-only, StockMovement/ItemHolderLog view-only,
`Personnel.user` autocomplete linking, custom `UserAdmin` +
`UserProfileInline`; `seed_personnel` admin user now a superuser) →
Step 9 end-to-end testing (4 headless-Chromium workflow chains through
the real UI, 86/86 assertions, **no code changed** — the chain-3
negative case, Dennis Cruz staying blank after registering-without-
attending, was the load-bearing assertion) → a full UI/button audit that
found + fixed 2 role-related frontend bugs (`common.css` `[hidden]`
specificity; STAFF Equipment page broke on the ADMIN-only categories
fetch) → **React frontend rebuild started (R1)**: `frontend/` Vite +
React 19 + Tailwind v4 scaffold, `docs/design-system-export.md` copied
in as the authoritative design reference, backend gains SimpleJWT
(`/api/token/`, `/api/token/refresh/`) + `/api/me/` + env-gated
`django-cors-headers` (SessionAuth/BasicAuth kept) → R2 React shared
infra (`frontend/src/{lib,components,pages}`, `App.jsx` router,
`AuthContext` + `lib/api.js` refresh-on-401, the primitive component
layer, role-filtered `Sidebar`, `ProtectedRoute`, `LoginPage`; 8 pages
still placeholders; **no backend changes**) → R3 React Categories +
Staff pages (real content replacing the placeholders; "Remove current
photo" is now a conditional render so the DOM node is absent when there
is no photo — closes UI-audit Finding 1 structurally; backend gains a
**DEBUG-only** `/media/` route in `config/urls.py` for dev photo
thumbnails) → R4 React Equipment + Stock movements pages (role-aware
category filter — the STAFF audit fix reimplemented; CSV export via new
`lib/csv.js`; image upload as JSON + follow-up FormData PATCH;
holder-history modal; inline insufficient-stock error on the movements
form; **no backend changes**) → R5a React Requests page (server-scoped
list, PENDING-only Approve/Reject with an inline per-row insufficient-
stock error, decided rows render zero controls; **no backend changes**).
R5 was **split into R5a (Requests) + R5b (Trainings)** — Requests/
Trainings share no surface and Trainings is the app's biggest page (its
own cycle, like Step 7d); **both sub-steps now done**. R5b: full
Trainings page — client-side 5-blocker register gating (server 409
backup), expandable roster panel with matrix-bridge feedback per
attendance toggle (optimistic UI, cross-checked against the real
`/api/personnel/` in testing), manual-attendees sub-table marked as not
feeding the matrix, catalog-grouped create/edit modal, full archive
lifecycle; **no backend changes**) → R6 React Personnel matrix
(`PersonnelPage.jsx` + scoped `PersonnelMatrix.css`; district/muni/view
filters, two-row MANAGERIAL/SKILLS banded header with NO rowspan,
triple-sticky layout — frozen Name + frozen actions + two-row header +
nested-sticky band labels, verified via measured
`getBoundingClientRect()` deltas across 3 scroll positions; all identity
fields + 27 training cells inline-editable, modal New Personnel,
archive/restore; **no backend changes**) → R7 React Archived page
(`ArchivedPage.jsx`, config-driven 4-tab layout, Restore for all admins,
Delete-permanently gated on `can_permanently_delete`) → **R7 cutover:
the React SPA is now the production frontend and the Django template
frontend is deleted.** `settings.py` + `urls.py` serve `frontend/dist/`
single-origin (whitenoise for `/` + `/assets/*`, a SPA catch-all →
`index.html`); removed `context_processors.role` and
`LOGIN_URL`/`LOGIN_REDIRECT_URL`/`LOGOUT_REDIRECT_URL`; deleted 24 files
(`apps/core/templates/`, `apps/core/static/core/*.{js,css}`,
`web_urls.py`, `context_processors.py`), the 9 page views, and the 5
`Step7*PageShellTests` classes (21 tests). Landed as one atomic commit
after a **60/60 full parity click-through** + a **single-origin smoke
test** both passed. → **Post-R7 follow-ups** (real-usage testing):
Improvement 1 — Personnel matrix defaults its district select to the
first district on load (`PersonnelPage.jsx`, `49243f7`); **Post-R7
Personnel-roster attendance** — new `PersonnelAttendee` model (migration
`core/0006`), `?search=` on `PersonnelViewSet`, nested
`PersonnelAttendeeViewSet` roster routes, an extracted shared
`_matrix_bridge` helper (pure refactor), and a third "Personnel roster"
section with a search-as-you-type picker in the Trainings page (see the
dedicated section above).

**The whole R1–R7 React rebuild is complete. Steps 1–9 done + R1–R7
done.** Step 10 (deploy — Render + external Postgres; the single-origin
serving mechanism is already wired) is the last build-order item. Step
11 (fold this project's React frontend into `PDRRMO_v3`'s actual app +
its role/JWT system) remains a later, separate effort — **unchanged in
scope**; the SPA now being production here doesn't advance it. Then a
**logic / data-consistency audit** (see the section above). **Wave 1**
landed: `core/0007` (partial unique index on active
`TrainingRegistration`s), `_matrix_bridge` archived guard, register /
roster-add race fixes, `Personnel.district` KeyError guard, Equipment
Remarks/Description field split. **Wave 2** landed (no migration): `GET
/api/users/` + writable `Personnel.user` link with a record-named
conflict error + an "Account" column in the matrix (F1); self-service
`DELETE /api/requests/<id>/withdraw/` + Withdraw button (F5); History
access from the Archived page for Items and Trainings via a shared
`ItemHistoryModal` and a new read-only `TrainingHistoryModal` (F7).
Migrations: `core/0001`–`core/0007` (`0006` = `PersonnelAttendee`;
`0007` = active-registration unique constraint). Test suite: **217
passing** (192 + 11 audit Wave 1 + 14 audit Wave 2; the React frontend
has no test suite — it's covered by the R1–R7 + Post-R7 + audit-wave
headless-Chromium runs). Remote `origin` is
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
