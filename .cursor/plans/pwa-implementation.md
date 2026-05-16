# PWA Implementation Guide for `aboros/daad`

## Project Analysis

The app is a single-page, self-contained festival lineup builder hosted on GitHub Pages (`aboros.github.io/daad`). It consists of:

- `index.html` — the entire app (~1200 lines, all HTML/CSS/JS inline)
- `downloads.html` — ICS download page (normal website; **not** required to work offline — see scope)
- `data/` — schedule data directory
- External dependencies loaded from CDNs until **vendored assets** land (prerequisite for shipping PWA)

### The critical offline problem

The app currently **fetches schedule data live from Google Sheets** on every load. At a festival with no network, that fails and the schedule is empty. **Baked `data/events.json` + same-origin caching** fixes this. The service worker can only cache responses it can fetch; external Sheet + `no-store` is not a reliable offline source.

---

## Decisions (finalized)

| Topic | Decision |
|-------|----------|
| **Canonical CSV (Sheet export)** | See **Canonical CSV** below. Stable integer **`id`**, **`stage`**, **`band`**, **`date`**, **`time`**, **`duration`** — **all required** on every row. **Optional only:** sample URL column, **`tags`**. End instants = **start + `duration`** in **`csv_to_events.py`**. |
| **`data/events.json`** | Produced by a **repo script** you run manually: `CSV → events.json`. **Top-level JSON array** of event objects the UI consumes (no raw CSV in the browser). |
| **Event identity** | Use **`id` from CSV** as **`event.id`** (integer). Do **not** derive IDs from `startUtcMs` + title + stage. |
| **`fetchEvents` / parsing** | Load **`./data/events.json`** only in the shipped app. No GViz/CSV fetch for schedule data. |
| **Vendored assets** | **PWA (manifest + service worker + offline behavior) ships only after** Tailwind / Font Awesome / fonts are **self-hosted** under `assets/` during your manual review. Until then, no meaningful offline UI. |
| **`downloads.html`** | **Out of scope for offline.** Do **not** register a service worker there; **omit `downloads.html` from precache**. It may stay online-only (CDN assets, no SW). |
| **`start_url` / scope / SW** | **`/daad/`** on GitHub Pages. Local `python server.py` uses `/`; validate install/offline on real Pages URL. |
| **Analytics** | Not required offline. Do **not** precache analytics. |
| **Git / deploy** | Maintainer handles commits, push, and deploy; this doc is implementation-only. |

### Canonical CSV (column headers)

Real export shape (example file: `daad2026 - Lineup.csv`). **Required on every row:** `id`, `stage`, `band`, `date`, `time`, `duration` (all non-empty). **Optional columns only:** sample URL, `tags` (cells may be empty; column may be omitted).

| Column | Notes |
|--------|--------|
| **`id`** | **Integer** from Sheet; must appear in final exports (add to Sheet + CSV). |
| **`stage`** | Stage name (same strings as today; normalization still applied in app or script). |
| **`band`** | Artist / set title → maps to `summary`. **Required.** |
| **`date`** | Dot format with trailing dot, e.g. `2026.06.18.` |
| **`time`** | 12-hour clock, e.g. `7:30:00 PM` |
| **`duration`** | `H:MM:SS` (e.g. `0:30:00`, `1:30:00`); script computes `endUtcMs` from start + duration. |
| **`samlpe set URL`** | **Optional.** Sample link (historic typo); match with same tolerance as today’s `sampleI` / header matching. |
| **`tags`** | **Optional.** Comma-separated (may be quoted); empty cell allowed. |

**Script requirement:** Implement **`scripts/csv_to_events.py`** (or similar) that:

1. Reads a CSV path (CLI argument).
2. Parses headers by **name** (order-independent).
3. Emits **`data/events.json`** as a **JSON array** of objects with at least: `id`, `summary`, `location`, `startUtcMs`, `endUtcMs`, `dayKey`, `duration`, `startTime`, `endTime`, `description`, `sampleSetUrl`, `tags` — **`endUtcMs` / ISO duration string** derived from **start + CSV `duration`** (required fields).
4. Uses **`Europe/Budapest`** for wall-clock → UTC (parity with `EVENT_TIMEZONE` in `index.html`).

The browser **`fetchEvents()`** loads the array and attaches any UI-only fields (e.g. `clean_title`) if needed.

---

## Implementation Plan

### Step 1 — `events.json` + CSV conversion script

**Goal**: Eliminate runtime Google Sheets dependency.

1. Add **`scripts/csv_to_events.py`** (stdlib + `zoneinfo`; document `python3 scripts/csv_to_events.py /path/to/export.csv`).
2. After Sheet export, run the script; commit **`data/events.json`**.
3. In **`index.html`**, replace GViz/CSV path with `fetch('./data/events.json')` → parse as **array**, **use `event.id` from JSON** for selection / `localStorage` (remove string ID derivation from time+stage+title).

**Breaking change:** Existing saved lineups in `localStorage` used **old string IDs**; after cutover, those keys no longer match. Accept reset or document one-time migration (optional, low priority).

---

### Step 2 — Self-host CDN dependencies (manual, before PWA)

**Gate:** Complete this **before** enabling offline PWA (Step 4–5).

| Resource | Target |
|----------|--------|
| Tailwind | `assets/app.css` (Tailwind CLI or committed build output) |
| Font Awesome | `assets/fontawesome/` (css + webfonts) |
| Google Fonts | `assets/fonts/` (Barlow, Bebas Neue `.woff2`) |

Update `<link>` / `<script>` in **`index.html`** (and **`downloads.html`** if it should still look correct online-only).

---

### Step 3 — Add `manifest.json`

Create `manifest.json` in the repo root (icons under `assets/icons/`).

Use **`start_url`** / **`scope`** **`/daad/`** on GitHub Pages.

Add to **`<head>` in `index.html` only** (PWA entry is main app):

```html
<link rel="manifest" href="/daad/manifest.json">
```

*(Optional: omit manifest on `downloads.html`, or add same link for icon/theming only — does not affect SW scope.)*

---

### Step 4 — Add `sw.js` (after Step 2)

**Precache only what makes `index.html` work offline** — **not** `downloads.html`.

```js
const CACHE_NAME = 'daad-2026-v1';

const PRECACHE_URLS = [
  '/daad/',
  '/daad/index.html',
  '/daad/manifest.json',
  '/daad/data/events.json',
  // After Step 2, include every local asset referenced by index.html, e.g.:
  // '/daad/assets/app.css',
  // '/daad/assets/fontawesome/css/all.min.css',
  // '/daad/assets/fonts/....woff2',
];

// install / activate / fetch handlers unchanged from earlier draft:
// cache-first: caches.match → else fetch
```

Bump **`CACHE_NAME`** when schedule or shell assets change.

**Analytics:** never list analytics hosts in `PRECACHE_URLS`.

---

### Step 5 — Register the Service Worker (`index.html` only)

```html
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/daad/sw.js')
        .catch(err => console.warn('SW registration failed:', err));
    });
  }
</script>
```

**Do not** add this snippet to **`downloads.html`**.

---

### Step 6 — iOS "Add to Home Screen" hint

Add the banner + script to **`index.html`** only (same as prior plan).

---

## File Checklist

```
/
├── index.html              (events.json fetch, integer id, manifest, SW, iOS hint; local asset links)
├── downloads.html          (optional: local assets for online appearance only; no SW)
├── scripts/
│   └── csv_to_events.py   (manual CSV → data/events.json)
├── manifest.json
├── sw.js
├── data/
│   └── events.json        (generated; committed)
└── assets/                 (after manual vendoring)
    ├── icons/
    ├── fonts/
    ├── fontawesome/
    └── app.css
```

---

## Testing Checklist

1. **Script:** Run `csv_to_events.py` on a fresh Sheet export; validate `events.json` loads and schedule matches CSV.
2. **Desktop Chrome:** Application → Service Workers → active on **`/daad/`**; offline → **`index.html`** loads (not `downloads.html`).
3. **Android** install + Airplane Mode: main app works.
4. **iOS** Add to Home Screen + offline: main app + selections (keyed by integer `id`).

---

## Notes

- **`localStorage`** — selections keyed by **`id`** after cutover.
- **ICS** — still client-side from loaded events.
- **Tailwind CLI** — allowed as a **dev-time** step to produce `assets/app.css`; not required in the browser.
- **HTTPS** — GitHub Pages already satisfies secure context for PWAs.

---

## Residual assumptions (not blocking)

- **`id`** unique per row (Sheet discipline).
- Only **`tags`** and the sample URL column may be empty; everything else required per row.

If Google Sheets renames a header, update **`csv_to_events.py`** header matching (keep tolerant match for the sample URL column like today).
