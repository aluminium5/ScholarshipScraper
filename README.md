# ScholarTrack

Scholarship discovery and application tracker for Indian students.

ScholarTrack pulls open scholarships from the National Scholarship Portal,
Buddy4Study and Vidyasaarathi into one list ordered by the nearest deadline,
stores the details students retype on every application form, and tracks each
application from *Saved* through to *Awarded*.

Every **Apply** button opens the scholarship's own page — never a portal
homepage.

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Running it locally](#running-it-locally)
- [Environment variables](#environment-variables)
- [Deploying to Vercel + Neon](#deploying-to-vercel--neon)
- [The scrapers](#the-scrapers)
- [Seed data](#seed-data)
- [API reference](#api-reference)
- [Tests](#tests)
- [What is stored, and what is not](#what-is-stored-and-what-is-not)
- [Known limitations](#known-limitations)

---

## What it does

| | |
|---|---|
| **Discover** | Merges live listings from three portals, deduplicated on `(source, external_id)`. |
| **Sort by urgency** | Nearest deadline first, undated last. Expired scholarships are hidden by default. |
| **Portfolio** | Personal, academic, family, bank, documents and CV details, with a **Copy** button on every field. |
| **Deep links** | Apply opens the specific scholarship's page. A scraper that cannot find one skips the record. |
| **Track** | Saved → Applied → Under review → Awarded / Rejected, on a kanban board. |

Clicking **Apply** also adds the scholarship to the tracker as *Saved*, so
nothing is lost between opening a form and finishing it.

---

## Architecture

```
                         ┌──────────────────────────────┐
  Browser  ──────────────▶  Vercel static build          │
                         │  frontend/dist (React SPA)    │
                         └───────────────┬───────────────┘
                                         │  relative /api/* calls
                                         │  (same origin → no CORS)
                         ┌───────────────▼───────────────┐
                         │  api/index.py                 │
                         │  → backend.main:app (FastAPI) │
                         │     routers: auth, scholar-   │
                         │     ships, portfolio,         │
                         │     applications, cron        │
                         └───────┬───────────────┬───────┘
                                 │               │
                   SQLAlchemy    │               │  httpx + BeautifulSoup
                   (NullPool)    │               │
                         ┌───────▼───────┐  ┌────▼────────────────────────┐
                         │ Neon Postgres │  │ services/ingest.py          │
                         │ (pooled URL)  │  │  ├─ scrapers/nsp            │
                         │               │  │  ├─ scrapers/buddy4study    │
                         │ users         │  │  ├─ scrapers/vidyasaarathi  │
                         │ scholarships  │  │  └─ seed/scholarships.json  │
                         │ portfolios    │  │     (fallback)              │
                         │ applications  │  └────▲────────────────────────┘
                         │ refresh_runs  │       │
                         └───────────────┘       │
                                                 │
            Vercel Cron ─── GET /api/cron/refresh ┘
            (00:30 UTC / 06:00 IST, Bearer CRON_SECRET)
```

**The ingest contract.** A refresh must never make the dashboard worse:

1. Each scraper runs inside its own `try`. One failing scraper cannot stop the
   others or fail the run.
2. Records are upserted on `(source, external_id)`.
3. Only a source that **actually returned records** may deactivate its own
   unseen rows. A scraper that raises — or returns nothing — leaves its existing
   rows untouched, so a site outage never wipes that source.
4. Anything past its deadline is deactivated.
5. If the table is completely empty, `seed/scholarships.json` is loaded, so the
   dashboard still works even if every scraper fails.
6. The run and its per-source summary are written to `refresh_runs`, which is
   what powers "Last updated 3h ago".

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18, Vite 5, TypeScript (strict), Tailwind CSS 3, React Router 6, TanStack Query 5 |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2 |
| Database | Postgres on Neon in production; SQLite locally when `DATABASE_URL` is unset |
| Auth | Email + password, bcrypt hashes, JWT in `Authorization: Bearer` |
| Scraping | `httpx` + `beautifulsoup4` + `lxml` (no headless browser — it will not run on Vercel functions) |
| Hosting | Vercel: static frontend + FastAPI as a Python serverless function under `/api` |
| Schedule | Vercel Cron → `GET /api/cron/refresh`, once daily |

Python 3.12 is the Vercel runtime target. The code is tested on 3.13 locally and
uses nothing version-specific.

---

## Running it locally

Two terminals. No database to install — it falls back to SQLite.

**1. Backend**

```bash
python -m venv .venv
.venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

# Minimum to run; see "Environment variables" for the rest.
export JWT_SECRET="dev-secret"
export CRON_SECRET="dev-cron-secret"
export ADMIN_EMAILS="you@example.com"   # enables the Refresh button in the UI

uvicorn backend.main:app --reload --port 8000
```

Tables are created on startup. Interactive API docs: <http://localhost:8000/docs>.

**2. Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to port 8000,
so the frontend always uses relative paths and never needs a base URL.

**3. Load some scholarships**

The database starts empty. Either run a real refresh:

```bash
curl -H "Authorization: Bearer dev-cron-secret" http://localhost:8000/api/cron/refresh
```

…or sign up with an email listed in `ADMIN_EMAILS` and press **Refresh now** on
the dashboard. A refresh hits the live portals and takes roughly 20–40 seconds,
mostly in the Buddy4Study crawl.

---

## Environment variables

Copy `.env.example`. Every value has a working local default except the secrets.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | production | Neon **pooled** connection string. `postgres://` and `postgresql://` are rewritten to `postgresql+psycopg://` automatically. Unset → SQLite at `./scholartrack.db`. |
| `JWT_SECRET` | yes | Signs session tokens. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `CRON_SECRET` | yes | Vercel Cron sends it as `Authorization: Bearer …`. The endpoint refuses to run if it is unset, rather than running unauthenticated. |
| `ADMIN_EMAILS` | no | Comma-separated. These accounts see the manual **Refresh now** button. |
| `JWT_EXPIRE_MINUTES` | no | Session length. Default 14 days. |
| `CORS_ORIGINS` | no | Only needed for local dev; production is same-origin. Defaults to the Vite dev server. |
| `BUDDY4STUDY_MAX_PAGES` | no | Pages crawled per refresh. Default 25. See [the scrapers](#the-scrapers). |
| `BUDDY4STUDY_CRAWL_DELAY` | no | Seconds between page fetches. Default 0.25. |

---

## Deploying to Vercel + Neon

1. **Push the branch** and import the repository at
   [vercel.com/new](https://vercel.com/new). `vercel.json` already sets the build
   command, output directory, the `/api` rewrite, the cron schedule, and a 60 s
   function timeout (the refresh crawls, so it needs more than the 10 s default).

2. **Add Neon**: Vercel dashboard → *Storage* → *Marketplace* → **Neon** →
   create a database. This sets `DATABASE_URL` for you. Open the Neon dashboard
   and confirm the value is the **pooled** connection string (its host contains
   `-pooler`); serverless functions open a connection per invocation, so the app
   uses `NullPool` and relies on Neon's pooler.

3. **Set the remaining env vars** under *Settings → Environment Variables*, for
   Production and Preview:

   ```
   JWT_SECRET      <a long random string>
   CRON_SECRET     <another long random string>
   ADMIN_EMAILS    you@example.com
   ```

4. **Deploy**, then check:

   ```bash
   curl https://<your-app>.vercel.app/api/health
   # {"ok": true}
   ```

5. **Populate the catalogue** once, by hand:

   ```bash
   curl -H "Authorization: Bearer $CRON_SECRET" \
        https://<your-app>.vercel.app/api/cron/refresh
   ```

   The response is the per-source summary. Check that `errors` is empty for each
   source, then open the app, sign up, and confirm the dashboard lists
   scholarships with the soonest deadline first.

6. **Confirm the cron** under *Settings → Cron Jobs*. It runs daily at 00:30 UTC
   (06:00 IST). Vercel's Hobby plan allows one cron per day, which is what
   `vercel.json` declares. Vercel sends `CRON_SECRET` automatically; nothing else
   is needed.

### Screenshots

Not included: these were not captured, because the environment this was built in
had no browser available to take them. To add them, run the app locally, then
drop the images in `docs/` and link them here — the dashboard, the detail drawer,
the portfolio tab strip and the kanban board are the four worth showing.

---

## The scrapers

All three share one interface (`scrapers/base.py`): a real browser User-Agent, a
15-second timeout, at most 2 retries, and a per-scraper error boundary in the
ingest service. Each was verified against the live site on **17 October 2026**,
and the HTML it was verified against is committed under
`backend/tests/fixtures/` so the parsers are unit-tested without the network.

### NSP — `scholarships.gov.in/All-Scholarships`

Server-rendered; a plain `GET` is enough. Schemes sit in ministry accordions:
the ministry is the `accordion-header` button, each scheme title is an `<h6>`,
and the dates are badge `<span>`s.

- `deadline` comes from **"Student Application Open till"**. The page also shows
  later verification deadlines, which must not be picked up.
- The labels contain **doubled spaces** (`Student Application  Open till`), so
  all matching runs through `normalize_space` first.
- `info_url` is the scheme's *Specifications* PDF. Some are linked relatively,
  and a missing document is rendered as `href="null"` — both are handled.
- `apply_url` is `https://scholarships.gov.in/ApplicationForm/` for every
  scheme. NSP has no public per-scheme page: you pick the scheme after an OTR
  login, so the UI shows a note naming the exact scheme to select.
- `external_id` is a hash of the normalised title, because the guideline PDF
  filenames change every academic year.

Currently returns **31 central-sector schemes**.

### Buddy4Study — `buddy4study.com`

The `/scholarships` listing is rendered entirely on the client and its
`__NEXT_DATA__` holds only interface strings, so the listing page is useless.
What works instead is the site's own per-scholarship pages:

- `sitemap1.xml` (declared in `robots.txt`) lists ~1,350 `/scholarship/<slug>`
  URLs, each with a `<lastmod>`.
- Every such page server-renders a full `__NEXT_DATA__` payload at
  `props.pageProps.scholarship.brandPage.scholarships[]` — an array of that
  programme's editions across years, each with an ISO `deadline`, `purposeAward`,
  `eligibility`, `applicationLaunchDate` and `pageSlug`.
- `pageSlug` is `page/<brand-slug>`, which is exactly the deep link this source
  needs. Only editions that are still open are kept.
- The site **soft-404s**: an unknown slug returns HTTP 200 with its generic
  title, so the scraper checks the title rather than the status code.

`robots.txt` permits `/scholarship/*` and `/page/*`; only `/media-url/*` and
`/UID/*` are disallowed.

**Crawl budget.** Visiting all 1,350 pages would never fit in a serverless
invocation, so the crawl is capped by `BUDDY4STUDY_MAX_PAGES` (default 25) and
visits the most recently modified pages first. Most programmes' current edition
has already closed, so expect only a handful of open records per run — this
source adds private and corporate variety, not bulk. Raise the cap when running
the ingest somewhere without a request timeout.

If the JSON listing endpoint is ever captured from DevTools (Network → Fetch/XHR
on the listing page), set `LISTING_ENDPOINT` in `scrapers/buddy4study.py` and it
is used instead of the crawl. Nothing else needs to change.

### Vidyasaarathi — `vidyasaarathi.co.in`

Server-rendered Java/Spring, but the scheme cards are not in the HTML: the open
schemes are embedded as a JavaScript array literal, `var a=[{…}]`, which the
page's own `getOpenSchemes()` renders. Two traps, both now covered by regression
tests:

- The string **"Currently No Schemes are Available" is always present**, because
  it is the `else` branch of that renderer's source. Testing for it in the raw
  page reports "no schemes" even when 15 are open. The empty check runs against
  the page with `<script>` and `<style>` stripped out.
- The page is served as **ISO-8859-1 with cp1252 bytes** (0x92 smart quotes), so
  decoding it as UTF-8 raises.

Every per-scheme detail URL the portal builds (`resources/<entityCode>/<id>_<v>.html`)
returns 404 without a session, so there is no usable per-scheme public page.
`apply_url` is therefore the **Open Schemes listing** — a real path, never the
bare homepage — and each record's description names the exact scheme to select
after logging in, mirroring the exception the spec grants NSP for OTR.

Currently returns **15 open JSW Foundation schemes**.

### When one breaks

A broken scraper is a logged error and an untouched source, not an outage. To
diagnose:

```bash
# Per-source summary, including the exception text
curl -H "Authorization: Bearer $CRON_SECRET" .../api/cron/refresh | python -m json.tool

# Re-run one parser against the committed fixture
pytest backend/tests/test_scrapers.py -k nsp -v
```

If a site's markup has changed, refresh the fixture and fix the parser against
it — each parser is a pure function over HTML, so no network is needed to iterate.

---

## Seed data

`backend/seed/scholarships.json` is the curated fallback, loaded **only when the
scholarships table is completely empty**. It currently holds 75 real open
scholarships: 37 from Buddy4Study, 18 from NSP, 15 from Vidyasaarathi, and 5
hand-checked private programmes (Vidyadhan, JN Tata Endowment, Inlaks, Aditya
Birla, Sitaram Jindal).

Every entry's `apply_url` is checked to have a path before it is written, and
`test_ingest.py` asserts the same over the committed file — the loader silently
skips a bad record, so the file needs its own guard. The Reliance Foundation
programmes were dropped for this reason: their site is a single-page app that
answers every path with HTTP 200 and an identical title, so no per-programme URL
could be verified and the UG and PG awards would have shared one link.

Because it stores real deadlines, **it goes stale**: once every dated entry has
passed, the fallback shows nothing. Regenerate it from the live portals:

```bash
python -m backend.seed.generate_seed
```

The curated private entries carry `"deadline": null` where no deadline could be
confirmed on an official page. They stay visible and sort last, which is honest
about what is known rather than inventing a date.

---

## API reference

Everything lives under `/api`. Interactive docs at `/docs`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/auth/signup` | — | name, email, password → JWT |
| `POST` | `/auth/login` | — | → JWT |
| `GET` | `/auth/me` | user | current user |
| `GET` | `/scholarships` | user | `q`, `source`, `level`, `tag` (repeatable, matches all), `include_expired`, `due_within_days`, `limit`, `offset`. Ordered by deadline ascending, nulls last. |
| `GET` | `/scholarships/{id}` | user | detail |
| `GET` | `/scholarships/meta` | user | source/level/tag counts, totals, last refresh |
| `GET`/`PUT` | `/portfolio` | user | read / replace |
| `GET` | `/applications` | user | tracker, joined with scholarship info |
| `POST` | `/applications` | user | `{scholarship_id, status}`, upsert |
| `PATCH` | `/applications/{id}` | user | status, notes, applied_on |
| `DELETE` | `/applications/{id}` | user | remove |
| `GET` | `/cron/refresh` | cron secret | run ingest |
| `POST` | `/admin/refresh` | admin | manual refresh |
| `GET` | `/health` | — | `{"ok": true}` |

Each scholarship in a list response carries `days_left` and the caller's own
`application_status`, so the dashboard renders from a single request.

Two behaviours worth knowing:

- `POST /applications` is an upsert, and it **never downgrades progress**.
  Clicking Apply again on something already marked *Awarded* leaves it awarded.
- `GET /cron/refresh` compares the secret in constant time and returns 503 — not
  200 — if `CRON_SECRET` was never configured.

---

## Tests

```bash
pytest                      # 157 tests
cd frontend && npm run build   # typecheck + production build
```

- `test_scrapers.py` — parsers against the committed real-HTML fixtures: field
  extraction, date formats, the deep-link rule, soft-404 detection, the
  JavaScript empty-state trap, and malformed input.
- `test_ingest.py` — the resilience contract: a failing scraper does not wipe its
  source, an empty-but-successful scrape does not either, one broken scraper does
  not stop the others, the seed fallback loads when everything fails, and bare
  portal homepages are rejected.
- `test_api.py` — auth, per-user isolation, deadline ordering, every filter, the
  Apply-auto-saves behaviour, and the storage restrictions below.

---

## What is stored, and what is not

- Passwords are **bcrypt** hashes. The API never echoes a password back.
- The bank section accepts **only the last four digits** of an account number. A
  longer value is a validation error.
- There is **no field anywhere for an Aadhaar number** or a full account number.
  Every portfolio section is `extra="forbid"`, so an attempt to post one is
  rejected rather than quietly stored.
- The documents checklist records *whether you have* a document and its expiry —
  never a document number.
- Login does not reveal which emails exist: a wrong password and an unknown
  address return the same 401 and the same message.
- A user can only ever read or change their own portfolio and applications;
  another user's ID returns 404 rather than 403, so IDs cannot be probed.

---

## Known limitations

- **The Buddy4Study crawl is capped**, so it surfaces a handful of open
  scholarships per refresh rather than everything the site lists. See
  [the crawl budget](#buddy4study--buddy4studycom).
- **Vidyasaarathi has no per-scheme public page**, so Apply opens its Open
  Schemes tab with a note naming the scheme. Same for NSP, which requires OTR.
- **NSP covers the Central Sector list only.** The "Centrally Sponsored" and
  "State Schemes" tabs are driven by form posts and are not scraped yet.
- **The seed file dates go stale** and need regenerating — see
  [Seed data](#seed-data).
- **Level and tag inference is heuristic.** It reads the title for who a
  scholarship is *for* and the full text for the nature of the award; it will
  occasionally mislabel an unusually worded scheme.
- **No screenshots in this README** — see the note under
  [Deploying](#screenshots).
- The frontend keeps its JWT in `localStorage`, which is appropriate for this
  app but means a token is readable by any script running on the origin.

---

Scholarship data is pulled from public portals. Always confirm dates and
eligibility on the official page before applying.
