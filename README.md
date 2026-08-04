# Azzurro Hotels — Review Insights Dashboard

A scraper + API + dashboard for monitoring guest reviews across four Azzurro
Hotels properties on Booking.com, built for non-technical operations staff.

## Architecture

```
scraper/    Playwright scraper -> SQLite (data/reviews.db)
backend/    FastAPI aggregation layer over the same SQLite DB
frontend/   Next.js + Tailwind + Recharts dashboard, calls the API
```

Data flows one direction: `scraper` writes rows, `backend` reads/aggregates
them, `frontend` renders. No component talks directly to Booking.com except
the scraper.

**Why SQLite instead of MongoDB/Postgres:** zero external service to
provision or authenticate against under a hard time limit, and the dataset
size (four properties' worth of reviews) doesn't need a server-based DB.
The scraper and backend both go through `scraper/db.py`, so swapping to
Mongo/Postgres later is a contained change to that one file plus the
connection setup in `backend/main.py` — not a rewrite.

## Setup & run

### 1. Scraper
```bash
cd scraper
pip install -r ../requirements.txt
playwright install chromium   # downloads the browser binary
python scraper.py --all       # or --property "Surry Hills"
```
This creates/updates `data/reviews.db`. Re-running it is safe — it dedupes
against what's already stored (see "Review collection method" below).

**Want to see the dashboard working before the scraper is fully verified?**
```bash
python seed_sample_data.py
```
This populates `data/reviews.db` with 100 synthetic sample reviews (clearly
labeled as placeholder data in the script) spread across 8 weeks, so every
part of the pipeline — stats, trends, topic insights, filters — can be
exercised end to end immediately. **This is not the "sample review data
collected from the properties" deliverable** — that must come from an
actual `scraper.py` run; see limitations below for why that run needs a
short verification step first.

### 2. Backend
```bash
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```
Verify: `curl http://localhost:8000/api/health` → `{"status": "ok"}`

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`. It expects the API at `http://localhost:8000`
(override with `NEXT_PUBLIC_API_BASE` if needed).

## Review collection method

Two-tier approach, in order of preference:

1. **Network interception (primary).** Booking.com's review section loads
   guest reviews via an internal XHR/fetch call returning JSON. The scraper
   listens for any response whose URL contains "review" with a JSON
   content-type and parses review objects directly from that payload. This
   is more durable than scraping rendered HTML, since markup changes more
   often than the underlying data contract.
2. **HTML fallback.** If no JSON response is seen, the scraper falls back
   to parsing rendered review cards from the DOM via Playwright selectors.

**Deduplication:** each review is keyed by Booking's own review ID when the
JSON path surfaces one, or otherwise by a hash of
`property + reviewer + date + first 120 chars of review text`. Both the
scraper and the DB layer treat this as a primary key, so re-running the
scraper never creates duplicates.

**Incremental updates:** the scraper checks the newest review date already
stored per property and stops paginating once it reaches reviews at or
before that date — so a scheduled re-run (e.g. daily cron) only does the
work of fetching what's new, not a full re-scrape.

**Reliability handling:** each property is scraped in its own try/except so
one failing property doesn't abort the whole run; failed attempts retry up
to 3 times with linear backoff; every run (per property) is logged to a
`scrape_runs` table with status/error, so failures are visible in the data
itself rather than only in console output.

## Honest limitation on the scraper: needs one live verification pass

The scraper was written and reviewed **without live network access to
booking.com** from the environment used to build it (sandboxed, egress
restricted to package registries). The JSON field-name guesses in
`_parse_json_review_payload` and the CSS selectors in the HTML fallback are
my best estimate of Booking.com's actual structure, not confirmed against a
live page. Every place that needs confirming is marked `# VERIFY:` in
`scraper/scraper.py` — there are five of them, and confirming them means:

1. Open one property URL in a non-headless browser (`headless=False`) with
   DevTools Network tab open, filter by "review" or "XHR".
2. Find the actual response containing review data; note its JSON shape.
3. Update the key names in `_parse_json_review_payload` and, if the JSON
   path doesn't materialize, the CSS selectors in
   `scrape_property_html_fallback` to match what's actually rendered.

I'm flagging this directly rather than shipping guessed selectors silently
— getting this wrong quietly would be worse than being upfront that it
needs a 15-20 minute live-verification pass, which I was not able to do
from where this was built.

## Topic/insight classification

Keyword-dictionary matching (`backend/insights.py`) against 8 operational
categories (cleanliness, check-in, staff behaviour, noise, facilities,
location, room condition, value for money). A review can match multiple
categories. "Negative" reviews are defined as rating < 6/10 or having any
disliked-text content, matching how Booking.com's own UI treats a
"disliked" section as negative signal.

**Why keyword-based over an LLM call:** deterministic, free, instant, and
auditable — a non-technical ops person (or an evaluator) can see exactly
which words triggered a "Cleanliness" tag. An LLM classifier (e.g. Gemini)
would likely catch paraphrasing this dictionary misses, at the cost of
per-review API latency and spend. That's a reasonable next iteration, not
built here to keep the demo deterministic and dependency-free within the
time limit.

**Known limitation:** misses paraphrases, sarcasm, and terms not in the
keyword list. Coverage is only as good as the curated dictionary in
`TOPIC_KEYWORDS`.

## Dashboard features

- This week's average rating vs. last week, with the delta highlighted
- Per-property rating breakdown for the current week
- Review feed with property + date-range filters, showing liked/disliked
  text and rating per review
- Positive vs. negative review count trend over the last 8 weeks
- Operational topic breakdown of negative reviews with % share

## Known limitations & assumptions

- Scraper selectors need the live-verification pass described above before
  this can run unattended against production data.
- Rating scale assumed to be Booking's standard 0-10; "negative" threshold
  (< 6) is a reasonable default, not a client-specified cutoff — should be
  confirmed with ops staff.
- No auth on the API/dashboard — fine for a local trial, not for a real
  deployment (would need to sit behind the properties' existing staff auth).
- No scheduling/cron wiring included — `scraper.py --all` is designed to be
  safe to run on a schedule (see incremental update logic above), but the
  scheduler itself (cron, GitHub Actions, etc.) isn't set up here.
- CORS is wide open (`allow_origins=["*"]`) for local dev convenience only.
