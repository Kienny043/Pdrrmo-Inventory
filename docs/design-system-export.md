# PDRRMO_v3 Design System — One-Time Export

**Purpose:** A self-contained snapshot of `PDRRMO_v3`'s frontend visual
system (colors, typography, component patterns, layout conventions,
assets) so `inventory-system` can rebuild its own frontend to visually
match — without its session ever needing to open this repo again. This
is not a living reference; if `PDRRMO_v3`'s design changes later, this
doc goes stale and nobody updates it.

**Source:** `PDRRMO_v3/frontend/src/**` as of this export. The original
is a React 19 + Vite + Tailwind v4 SPA. `inventory-system` is plain
Django templates + vanilla JS with no build step — the component
patterns below are written so the structure and class names port
directly to plain HTML; the JSX is source-fidelity, not a requirement
to use React.

**Everything here is inline Tailwind utility classes composed
per-page.** There is no shared component library (no `Button.jsx`,
`Card.jsx`, `Modal.jsx`, `Badge.jsx` etc.) — every page hand-writes its
own buttons/cards/tables/modals using the same handful of class
patterns by convention, not by import. That convention *is* the design
system; Sections 2–5 below document the repeated patterns exactly as
they appear across the real pages.

---

## 1. Tailwind Config

**Tailwind v4, CSS-based config — no `tailwind.config.js` file exists.**
Everything lives in `frontend/src/index.css`, in full:

```css
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700&family=DM+Sans:wght@300;400;500&display=swap');
@import "tailwindcss";

/* PDRRMO Light Theme Colors */
@theme {
  --color-pd-navy: #102B6A;
  --color-pd-red: #D62828;
  --color-pd-gold: #F4A300;
  --color-pd-green: #1FAF38;
  --color-pd-gray: #F0F2F5;
  --color-pd-white: #FFFFFF;
  --color-pd-text-primary: #0B1F3A;
  --color-pd-text-secondary: #4B5563;
  --color-pd-border: #D6DCE5;
}

body {
  background-color: #F8F9FC;
  color: var(--color-pd-text-primary);
  font-family: 'DM Sans', sans-serif;
}

.municipality-boundary {
  cursor: default !important;
  outline: none !important;
}
```

Wired into Vite via the `@tailwindcss/vite` plugin (`vite.config.js`):

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

### Color tokens (the only custom tokens defined)

| Token | Hex | Used for |
|---|---|---|
| `pd-navy` | `#102B6A` | Primary brand color — sidebars, primary buttons, active nav, headings on dark bg |
| `pd-red` | `#D62828` | Alerts, destructive actions (as text/links, never solid buttons — see Section 5), active-tab underline, low-stock/urgent numbers |
| `pd-gold` | `#F4A300` | Secondary accent — stat highlights, one of the three login-role dots, occasional status badge |
| `pd-green` | `#1FAF38` | Positive/operational status (lifelines "OPERATIONAL", staff "PERMANENT" badge) — used less often than plain Tailwind `green-*`, both appear interchangeably across pages |
| `pd-gray` | `#F0F2F5` | Page background (`bg-pd-gray`), hover row background, filter-chip inactive background |
| `pd-white` | `#FFFFFF` | Rarely referenced directly — plain `bg-white` is used almost everywhere instead |
| `pd-text-primary` | `#0B1F3A` | Default body/heading text |
| `pd-text-secondary` | `#4B5563` | Secondary/muted text — labels, timestamps, placeholder-ish copy |
| `pd-border` | `#D6DCE5` | All borders — cards, table dividers, inputs, sidebar divider |

Body background is actually `#F8F9FC` (set directly, not a token) —
very slightly lighter than `pd-gray` (`#F0F2F5`), which is used for
*page containers* inside the authenticated shell (`bg-pd-gray` on the
flex wrapper) while raw white cards sit on top of it.

Opacity-modified tokens are used constantly for tints instead of
defining separate light-variant tokens: `bg-pd-red/10`, `border-pd-red/20`,
`bg-pd-navy/90` (hover), `text-pd-red/80` (hover), `bg-white/10` /
`bg-white/5` (sidebar hover states on the navy background), `bg-pd-red/5`
(low-stock table row tint). Plain Tailwind palette colors (`green-100`/
`green-700`, `red-100`/`red-700`, `yellow-100`/`yellow-700`, `blue-100`/
`blue-700`) are used just as often as the `pd-*` tokens for status
badges — there is no strict rule about which to reach for; see the
badge tables in Section 2.

### Fonts

Two Google Fonts, loaded via `@import url(...)` at the top of
`index.css` (not self-hosted, not a Tailwind `--font-*` token):

- **Sora** (weights 300/400/600/700) — headings, brand wordmarks, big
  stat numbers. Applied via inline `style={{ fontFamily: "'Sora', sans-serif" }}`
  on the element, *not* a Tailwind utility class — there is no
  `font-sora` class defined anywhere.
- **DM Sans** (weights 300/400/500) — body default, set once on `body`
  in `index.css`. Everything not explicitly given the Sora inline style
  inherits DM Sans.

### Spacing / radius / shadow / breakpoints

**No custom scale for any of these** — `@theme` only defines the color
tokens above. Radius, shadow, spacing, and breakpoints are all
Tailwind v4's unmodified defaults, reached for directly:

- Radius: `rounded-lg` (inputs, small buttons), `rounded-xl` (buttons,
  nav items, filter chips), `rounded-2xl` (cards, modals, tables —
  the dominant "container" radius), `rounded-full` (avatars, badges,
  spinners, dots).
- Shadow: `shadow-sm` (cards/tables at rest), `shadow-lg` (modals,
  dropdowns), `shadow-xl shadow-black/10` (the OPS sidebar specifically).
- Breakpoints: only `md:` and, rarely, nothing beyond it — this app
  doesn't lean on `lg:`/`xl:`/`2xl:` much. Default Tailwind breakpoint
  values apply (`md` = 768px) wherever `md:` appears (e.g.
  `grid-cols-2 md:grid-cols-4`, `hidden md:flex`).

---

## 2. Core Reusable Components & Patterns

None of these are extracted into components — this is the *recipe*
each page follows by hand. Copy the class strings.

### Buttons

**Primary (solid navy)** — the only solid-fill button variant in the
whole app. Used for every "positive create/submit" action:

```html
<button class="bg-pd-navy hover:bg-pd-navy/90 text-white text-sm font-semibold px-5 py-2 rounded-xl transition-all">
  + Add New Item
</button>
```
Disabled state just adds `disabled` + a text swap (`"Submitting…"`),
no separate disabled visual treatment is applied consistently (a few
places add `disabled:opacity-50`, most don't bother since the button
usually also becomes unclickable text).

**Secondary / cancel (outline)** — pairs with the primary button in
modal footers:
```html
<button class="px-4 py-2 text-sm border border-pd-border rounded-lg">
  Cancel
</button>
```

**Destructive / positive as text-links, not buttons** — this is the
load-bearing convention: there is **no solid red button anywhere in
the codebase** (confirmed — no `bg-red-*`/`bg-pd-red` solid fill is
ever paired with a button-shaped element). Destructive and
state-changing row actions are plain colored text links, sized small:
```html
<button class="text-xs text-green-600 hover:text-green-800 disabled:opacity-50 font-medium">Restore</button>
<button class="text-xs text-red-600 hover:text-red-800 disabled:opacity-50 font-medium">Delete Forever</button>
<button class="text-xs text-pd-red hover:text-pd-red/80">Archive</button>
<button class="text-xs text-pd-navy hover:text-pd-navy/80 font-medium">View</button>
<button class="text-xs text-pd-text-secondary hover:text-pd-navy">Edit</button>
```
See Section 5 for the full destructive-vs-safe color logic.

**Filter chip / toggle button** (category filters, tab-like selectors
that aren't underline tabs):
```html
<!-- active -->
<button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-pd-navy text-white transition-colors">All</button>
<!-- inactive -->
<button class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-pd-border text-pd-text-secondary hover:bg-pd-gray transition-colors">Medical</button>
```

### Cards

**Stat tile** (dashboard summary numbers, in a `grid grid-cols-2 md:grid-cols-4 gap-4`):
```html
<div class="bg-white border border-pd-border rounded-2xl p-5 shadow-sm">
  <div class="text-2xl font-bold text-pd-navy" style="font-family:'Sora',sans-serif">128</div>
  <div class="text-xs text-pd-text-secondary uppercase tracking-wider mt-1">Total Items</div>
</div>
```
The big number's color is swapped per-tile to carry meaning:
`text-pd-navy` (neutral count), `text-pd-red` (alert count, e.g. low
stock), `text-pd-gold` (secondary metric), `text-blue-600` (tertiary —
not even a brand token, plain Tailwind blue).

**Content card** (wraps a table, a form section, anything boxed):
```html
<div class="bg-white border border-pd-border rounded-2xl overflow-hidden shadow-sm">
  ...
</div>
```

### Tables

One consistent recipe everywhere (`ArchivedPage`, `InventoryRequestsPage`,
`InventoryDashboard`, etc.):
```html
<div class="bg-white border border-pd-border rounded-2xl overflow-hidden shadow-sm">
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-pd-border">
          <th class="text-left text-[11px] font-semibold text-pd-text-secondary uppercase tracking-wider px-4 py-3">Name</th>
          <!-- ...one <th> per column, same classes -->
        </tr>
      </thead>
      <tbody>
        <tr class="border-b border-pd-border hover:bg-pd-gray transition-colors">
          <td class="px-4 py-3 font-medium">Row value</td>
          <td class="px-4 py-3 text-pd-text-secondary">Muted value</td>
          <!-- action cell, see Buttons above -->
        </tr>
      </tbody>
    </table>
  </div>
</div>
```
Notes:
- Header cells: always uppercase, `11px`, `font-semibold`,
  `text-pd-text-secondary`, letter-spaced (`tracking-wider`).
- Row hover is always `hover:bg-pd-gray`.
- A row can carry a semantic tint on top of the hover state — e.g. low
  stock items get `bg-pd-red/5` permanently, not just on hover.
- No zebra striping — only the border-bottom + hover convey rows.
- `overflow-x-auto` wrapper is always present for horizontal scroll on
  narrow viewports (this is the *only* responsive concession most
  authenticated tables make — see Section 3).

### Modals

Every modal in the app is the same overlay + centered white card:
```html
<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
  <div class="bg-white border border-pd-border rounded-2xl w-full max-w-md p-6 shadow-lg">
    <h3 class="text-lg font-bold mb-4">Request Equipment</h3>
    <form class="flex flex-col gap-4">
      <!-- form fields, see next section -->
      <div class="flex justify-end gap-3 mt-2">
        <button type="button" class="px-4 py-2 text-sm border border-pd-border rounded-lg">Cancel</button>
        <button type="submit" class="bg-pd-navy hover:bg-pd-navy/90 text-white text-sm font-semibold px-5 py-2 rounded-xl">Submit Request</button>
      </div>
    </form>
  </div>
</div>
```
- `max-w-md` for simple forms, `max-w-xl`/`max-w-2xl` for detail/edit
  views, always with `max-h-[80vh]` or `max-h-[90vh]` + `overflow-y-auto`
  once the form has enough fields to need it.
- No animation/transition on open — it's a conditional render
  (`{showModal && (...)}`), not a portal or animated dialog primitive.
- No dedicated close (×) button convention — closing is via the
  Cancel button or (inconsistently) a backdrop click depending on the
  page; don't assume backdrop-click-to-close is universal.

### Form inputs / selects

One recipe for every text/number/date input, select, and textarea:
```html
<div>
  <label class="text-xs text-pd-text-secondary block mb-1">Quantity *</label>
  <input type="number" min="1" required
    class="w-full bg-white border border-pd-border rounded-lg px-3 py-2 text-sm" />
</div>
```
Selects use the identical wrapper class list. Required fields get a
literal `*` appended to the label text, not a styled asterisk span.
Search/filter inputs outside of modals use a slightly different,
rounder variant: `rounded-xl` instead of `rounded-lg`, plus
`outline-none` and sometimes `focus:border-pd-navy/40`:
```html
<input type="text" placeholder="Search..."
  class="bg-white border border-pd-border text-sm text-pd-text-primary rounded-xl px-4 py-2 w-56 outline-none" />
```

### Badges / status pills

Always the same shape — `text-xs font-semibold px-2 py-0.5 rounded-full`
(sometimes `px-2 py-1`) — with the color pair swapped per status.
Real mappings pulled directly from the code:

| Context | Value | Classes |
|---|---|---|
| Inventory item condition | NEW | `bg-green-100 text-green-700` |
| | GOOD | `bg-blue-100 text-blue-700` |
| | FAIR | `bg-yellow-100 text-yellow-700` |
| | NEEDS_REPAIR / DAMAGED | `bg-red-100 text-red-700` |
| Staff status | PERMANENT | `bg-pd-green/10 text-pd-green` |
| | CASUAL | `bg-pd-gold/10 text-pd-gold` |
| | INTERN | `bg-blue-100 text-blue-700` |
| | INACTIVE | `bg-red-100 text-red-700` |
| Inventory request status | PENDING | `bg-yellow-100 text-yellow-700` |
| | APPROVED | `bg-green-100 text-green-700` |
| | REJECTED | `bg-red-100 text-red-700` |
| Personnel org affiliation | EMPLOYEE | `bg-blue-100 text-blue-700` |
| | VOLUNTEER | `bg-green-100 text-green-700` |
| Archived training | CANCELLED | `bg-red-100 text-red-700` |
| Item holder log action | ASSIGNED | `bg-green-100 text-green-700` |
| | REMOVED | `bg-red-100 text-red-700` |

The pattern to copy for any new status enum: green = good/positive,
blue = neutral/informational, yellow = caution/pending, red =
bad/negative/final — pick whichever of the plain Tailwind pair or the
`pd-*` token pair reads best against the row, both are treated as
equivalent in this codebase.

**Notification count badge** (sidebar nav item, small circular
counter):
```html
<span class="ml-auto inline-flex items-center justify-center px-1.5 py-0.5 text-[10px] font-bold leading-none text-white bg-pd-red rounded-full min-w-[20px]">
  {count > 99 ? "99+" : count}
</span>
```

### Navigation / sidebar

See full pattern in Section 3 (Layout) — it's structural, not just a
component snippet.

### Tabs

Underline-style, used for in-page section switching (not routed):
```html
<div class="bg-white border-b border-pd-border px-8 flex gap-6">
  <button class="py-3 text-sm font-medium border-b-2 border-pd-red text-pd-red transition-colors">Items</button>
  <button class="py-3 text-sm font-medium border-b-2 border-transparent text-pd-text-secondary hover:text-pd-text-primary transition-colors">Staff</button>
</div>
```

### Toasts / notifications

**There is no toast system anywhere in the codebase** — no toast
library, no custom toast component. All success/failure feedback for
an action uses the browser's native `alert()` for errors and
`confirm()` for destructive-action confirmation:
```js
if (!confirm("PERMANENTLY DELETE this item? This CANNOT be undone.")) return;
// ...
} catch (e) {
  alert("Failed to delete: " + e.message);
}
```
Successful actions generally show no explicit confirmation at all —
the UI just re-fetches and the list updates. The one persistent,
passive "notification" surface is the sidebar's numeric badge (above)
next to the OPS "Report" nav item, driven by an unread-count prop.

---

## 3. Layout Patterns

### Shell structure — two variants exist, pick the cleaner one

**Variant A — `Outlet`-based layout wrapper** (used by Admin and
Coordinator modules): a dedicated `*Layout.jsx` renders the sidebar
once and an `<Outlet/>` for the routed page content.
```jsx
// AdminLayout.jsx
export default function AdminLayout() {
  return (
    <div className="flex min-h-screen min-w-[320px] overflow-x-auto bg-pd-gray text-pd-text-primary">
      <AdminSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Outlet />
      </div>
    </div>
  );
}
```

**Variant B — duplicated per-page shell** (used by OPS and Inventory
modules): every single page re-renders the sidebar and the same flex
wrapper itself, no shared layout component:
```jsx
<div className="flex min-h-screen bg-pd-gray text-pd-text-primary" style={{ fontFamily: "'DM Sans', sans-serif" }}>
  <InventorySidebar />
  <div className="flex-1 flex flex-col min-w-0">
    <header>...</header>
    <main>...</main>
  </div>
</div>
```
**Recommendation for `inventory-system`:** use Variant A (a single
shell + router outlet, or the Django-template equivalent — one
`base.html` with a sidebar block and a content block) rather than
copying Variant B's duplication. It's the same visual result with far
less repetition.

### Sidebar structure (both variants share this internally)

Fixed-width, full-height, sticky, on a navy background:
```html
<aside class="w-56 bg-pd-navy border-r border-pd-border flex flex-col flex-shrink-0 h-screen sticky top-0">
  <!-- Brand block -->
  <a href="/inventory/dashboard" class="flex items-center gap-2 px-5 py-6 border-b border-pd-border">
    <img src="/logo.png" alt="PDRRMO Logo" class="h-8 w-auto" />
    <div>
      <div class="text-xs font-bold text-white tracking-wide">PDRRMO</div>
      <div class="text-[10px] text-pd-gray">Inventory</div>
    </div>
  </a>

  <!-- Nav -->
  <nav class="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
    <!-- active item -->
    <a class="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium bg-pd-red/10 text-pd-red border border-pd-red/20">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><!-- icon paths --></svg>
      Dashboard
    </a>
    <!-- inactive item -->
    <a class="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium text-pd-gray hover:text-white hover:bg-white/10">
      Staff
    </a>
  </nav>

  <!-- User + logout footer -->
  <div class="border-t border-pd-border p-4">
    <div class="flex items-center gap-3 mb-3">
      <div class="w-8 h-8 rounded-full bg-pd-gold/20 flex items-center justify-center flex-shrink-0 text-xs font-bold text-pd-gold">JD</div>
      <div class="min-w-0">
        <div class="text-xs font-semibold text-white truncate">Jane Dela Cruz</div>
        <div class="text-[10px] text-pd-gray truncate">Admin & Training</div>
      </div>
    </div>
    <button class="w-full flex items-center gap-2 text-xs text-pd-gray hover:text-pd-red hover:bg-pd-red/10 px-3 py-2 rounded-lg transition-colors">
      Sign out
    </button>
  </div>
</aside>
```
The active-nav treatment differs slightly by module: OPS uses a
left-edge accent bar (`before:absolute before:left-0 ... before:bg-pd-red`
pseudo-element on a `bg-white/10` pill), while Admin/Inventory use a
tinted pill with border (`bg-pd-red/10 text-pd-red border border-pd-red/20`)
instead. Either is faithful to the system; pick one and stay
consistent within the new project.

User-initial avatar circle: two-letter initials
(`{first_name[0]}{last_name[0]}`) on a tinted brand-color circle —
`bg-pd-gold/20`/`text-pd-gold` in Admin/Inventory,
`bg-pd-red/30`/`text-white` in OPS. Not a real avatar image anywhere.

### Role-based nav visibility pattern

**Not** a single sidebar with conditionally-hidden items. Instead:
1. Each role/module gets its **own dedicated sidebar component**
   (`OpsSidebar`, `InventorySidebar`, `AdminSidebar`,
   `CoordinatorSidebar`) with a hardcoded `NAV_ITEMS` list — no item
   is ever conditionally shown/hidden inside one of these based on a
   finer-grained permission.
2. Route-level gating happens one level up, via a `ProtectedRoute`
   wrapper that checks the logged-in user's role against an
   `allowedRoles` array before rendering the module's routes at all:
   ```jsx
   <Route element={<ProtectedRoute allowedRoles={["LGU", "OPS", "ADMIN_TRAINING"]} />}>
     <Route path="/trainings" element={<TrainingRegistrationPage />} />
   </Route>
   ```
   ```jsx
   export default function ProtectedRoute({ allowedRoles }) {
     const { user, isLoading } = useAuth();
     if (isLoading) return <Spinner />;      // see Section 5
     if (!user) return <Navigate to="/" replace />;
     if (allowedRoles && !allowedRoles.includes(user.role)) {
       return <Navigate to={user.redirect_to ?? "/"} replace />;
     }
     return <Outlet />;
   }
   ```
3. A few pages *within* a module still do inline role checks for a
   single action, not a nav item — e.g. `InventoryRequestsPage` only
   renders the Approve/Reject actions column
   (`{isAdmin && (...)}`) and the "Delete Forever" links only render
   when `user?.is_inventory_admin` is true. This maps directly onto
   `inventory-system`'s own STAFF/ADMIN + `can_permanently_delete`
   plan from `docs/spec-inventory-system.md`.

### Page-container conventions

Every authenticated page's main content area follows this structure:
```html
<div class="flex-1 flex flex-col min-w-0">
  <header class="bg-white border-b border-pd-border px-8 py-4 flex items-center justify-between gap-4 sticky top-0 z-20">
    <div>
      <h1 class="text-lg font-bold text-pd-text-primary" style="font-family:'Sora',sans-serif">Page Title</h1>
      <p class="text-xs text-pd-text-secondary mt-0.5">128 items</p>
    </div>
    <!-- search input / primary action button(s), right-aligned -->
  </header>
  <main class="flex-1 px-8 py-6 overflow-y-auto">
    <!-- stat cards, filters, table/content -->
  </main>
</div>
```
- Header: white, bordered bottom, sticky (`sticky top-0 z-20`), title
  in Sora + a one-line muted subtitle/count under it, primary actions
  on the right.
- Main: `px-8 py-6`, independently scrollable — the sidebar stays
  fixed while this area scrolls.

### Responsive behavior

Honest assessment: **only the public landing page is actually mobile
responsive.** `Navbar.jsx` (landing page) has a real `md:hidden`
hamburger toggle and a full mobile dropdown menu. The authenticated
dashboard shells (OPS/Inventory/Admin/Coordinator) do **not** — the
sidebar is a fixed `w-56`/`w-[220px]` with no collapse/drawer behavior
at any breakpoint, and there's no mobile nav toggle in any of the four
sidebar components. The only responsive concessions inside the
authenticated app are: stat-card grids going `grid-cols-2 md:grid-cols-4`,
and tables wrapped in `overflow-x-auto` so they scroll horizontally
rather than break the layout. Treat the authenticated shell as
desktop-first/desktop-only when rebuilding — don't invent mobile
behavior that doesn't exist in the source.

---

## 4. Icons & Logo/Seal Assets

**No icon library is installed or used** — confirmed via a full search
of `package.json` and `src/` for `lucide`, `react-icons`,
`@heroicons`, etc.: none found. Every icon in the app is a **hand-written
inline `<svg>`**, consistently in this style (Feather/Lucide-*shaped*
paths, just not the package):
```html
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <!-- path/rect/circle/polyline/line elements -->
</svg>
```
Nav-item icons are usually `20×20`, action-row icons `16×16` or `13–14`
for the small logout icon. `stroke="currentColor"` means icon color is
driven entirely by the parent's text color class — no separate icon
color utility is ever set. If `inventory-system` wants matching icons
without hand-drawing SVGs, **lucide-react's actual icon set is visually
near-identical to what's hand-drawn here** (same 24×24/stroke-2/round-cap
conventions) and would be a reasonable drop-in — but note the source
app itself doesn't use it.

**Logo/seal:** there is exactly **one** image asset,
`frontend/public/logo.png` (also duplicated at
`frontend/src/assets/logo.png`, ~1 MB), referenced everywhere as
`/logo.png` and alt-texted `"PDRRMO Logo"`. **No separate Quezon
Province seal file exists** — every "Quezon Province" reference in the
UI is plain text (`"PDRRMO Quezon Province"`, footer copyright line,
etc.), not a second seal graphic. If the single `logo.png` doesn't
visually already combine both seals, `inventory-system` has nothing
else to copy for a province seal and would need to source one
separately.

Other `public/` assets, for completeness: `favicon.svg`, `icons.svg`
(an unused/legacy sprite sheet — not referenced by any `<use>` found
in `src/`), and two GeoJSON files (`quezon.geojson`,
`quezon_municipalities.geojson`) used only by the Leaflet map pages —
not relevant to `inventory-system`.

---

## 5. General Visual Conventions

### Archived / inactive states

There is **no dimmed/greyed-out inline styling** for archived records
sitting in the same list as active ones — archived items simply don't
appear in the default list at all (the API's default list excludes
`is_archived`/soft-deleted rows). Instead there's a dedicated
`/inventory/archived` page with its own tabbed view (Items / Staff /
Trainings / Personnel) that fetches *only* archived records and shows
them in the same table style as everywhere else, just with different
row actions (`Restore` / `Delete Forever` instead of `Edit` / `Archive`).
So: don't build a "greyed out row" treatment — build a separate
archived view instead, matching this app's actual pattern (also what
`spec-inventory-system.md`'s own Section 5 page list already assumes).

### Destructive vs. safe actions — the actual rule

This is consistent enough across the whole codebase to state as a
hard rule:

- **Never a solid-fill red button.** Confirmed by search — no
  `bg-red-*`/`bg-pd-red` solid background is ever applied to a
  button-shaped element anywhere in the app.
- **Destructive actions** (Archive, Delete Forever, Reject) are small
  text-only links: `text-red-600 hover:text-red-800` or
  `text-pd-red hover:text-pd-red/80`, always paired with a
  `confirm()` dialog before firing — and for anything irreversible
  the confirm copy is explicit and shouty: `"PERMANENTLY DELETE this
  item? This CANNOT be undone."` vs. a softer `"Archive this item?"`
  for the reversible action.
- **Safe/positive actions** (Restore, Approve) are the same small
  text-link shape but green: `text-green-600 hover:text-green-800`.
- **The one primary/positive solid button color is navy**
  (`bg-pd-navy`), used for create/submit actions — it is *not*
  color-coded to the action's semantics (there's no separate "success
  green" solid button anywhere), it's simply the one brand primary.
- **Error/alert banners** (as opposed to buttons) do use a red tint,
  but as a soft background, never solid:
  ```html
  <div class="flex items-start gap-3 bg-pd-red/10 border border-pd-red/20 rounded-xl px-4 py-3">
    <svg class="w-4 h-4 text-pd-red mt-0.5 flex-shrink-0" ...><!-- alert-circle icon --></svg>
    <p class="text-sm text-pd-red">Login failed.</p>
  </div>
  ```

### Loading states

Two forms, used consistently:
1. **Full-section spinner** (page/table load):
   ```html
   <div class="flex justify-center py-24 text-pd-text-secondary">
     <div class="w-5 h-5 border-2 border-pd-red border-t-transparent rounded-full animate-spin mr-3" />
     Loading...
   </div>
   ```
   (`ProtectedRoute`'s auth-check spinner is the same idea, slightly
   larger, centered full-screen with no "Loading..." text.)
2. **Inline button busy state** — swap the button's own label while a
   submit is in flight, no separate spinner element:
   ```jsx
   <button disabled={submitting}>{submitting ? "Submitting…" : "Submit Request"}</button>
   ```
   Row-level actions (Restore/Delete on a specific record) instead
   track a single `actionLoading` id in state and disable/relabel just
   that row's button (`{actionLoading === req.id ? "..." : "Approve"}`).

### Empty states

One consistent recipe — centered, muted, generous vertical padding,
no icon or illustration:
```html
<p class="text-center text-pd-text-secondary py-24">No archived records.</p>
```
Copy is always a short, specific `"No {things}."`/`"No {things} yet."`
sentence, not a generic "Nothing here."

### Error / validation display

There is **no per-field inline validation UI** — forms rely on native
HTML `required`/`type` browser validation for empty/malformed fields,
and on the alert-banner pattern above (or a plain `alert()` call) for
server/business-logic errors surfaced after submit:
```js
try {
  await apiFetch(url, { method, body: fd });
} catch (e) {
  alert("Save failed: " + e.message);
}
```
The one place with a real persistent error UI (not just an `alert()`)
is the login form, using the banner markup shown above under
"destructive vs safe actions." If `inventory-system` wants nicer
field-level validation than this, it would be an *improvement* over
the source app, not a pattern to copy — worth deciding deliberately
rather than assuming it should match.

---

## 6. Versions & Key Libraries

From `frontend/package.json`, exact versions in use:

| Package | Version | Notes |
|---|---|---|
| `react` / `react-dom` | `^19.2.5` | |
| `vite` | `^8.0.9` | |
| `@vitejs/plugin-react` | `^6.0.1` | |
| `tailwindcss` | `^4.2.4` | CSS-based config, no JS config file — see Section 1 |
| `@tailwindcss/vite` | `^4.2.4` | Vite plugin, replaces the old PostCSS setup |
| `react-router-dom` | `^7.14.2` | `BrowserRouter`, nested `<Route>` + `<Outlet>`, the `ProtectedRoute` pattern in Section 3 |
| `axios` | `^1.15.2` | Used inside a thin `apiFetch()` wrapper (`src/utils/api.js`) that also handles JWT refresh-on-401 — not directly relevant to a session-auth project, but the axios version is noted for completeness |
| `recharts` | `^3.8.1` | All charts (OPS analytics, inventory analytics — the latter explicitly out of scope for `inventory-system`'s rebuild). Worth reusing if/when `inventory-system` ever adds its own charts, for visual consistency with the parent system it may integrate with later. |
| `leaflet`, `react-leaflet`, `react-leaflet-cluster`, `leaflet.heat`, `leaflet.markercluster` | various | Map/weather/seismic pages only — not relevant to `inventory-system`. |

**Not installed / not used, worth calling out explicitly since their
absence is itself part of the design system:** no icon library
(Section 4), no component/UI kit (no MUI, shadcn/ui, Radix, Headless
UI, etc. — everything is hand-rolled Tailwind as shown above), no
toast/notification library (Section 2), no animation library (no
Framer Motion — the few transitions that exist are plain CSS
`transition-colors`/`transition-all`), no state-management library
beyond React's built-in Context (`AuthContext`) — no Redux/Zustand/etc.

For `inventory-system` specifically (plain templates + vanilla JS, no
build step): the color tokens, font imports, and utility-class
patterns in this doc all translate directly if pulling in Tailwind via
its CDN `<script>` build with an inline `tailwind.config`-equivalent
(v4's CDN build supports the same `@theme` CSS syntax) — no Vite/React
required to get a visually matching result.
