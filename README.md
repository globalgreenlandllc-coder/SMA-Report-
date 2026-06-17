# SMA-Report

Smart Comparative Market Analysis (CMA) reports for real estate agents.

An agent enters a property; the app pulls comparable sold + active MLS listings,
runs a **market-aware pricing engine** (adjustments derived from local comps, not
hardcoded), and produces a **branded, seller-ready report** where every comp links
back to its MLS listing for verification.

## Quick start

```bash
python main.py                    # value the sample subject, write report to output/
python main.py --exclude A-1007   # toggle a comp out and re-run
python main.py --json             # print the full engine result as JSON
```

No install is required to run the CLI — the engine, sample data, and HTML report
use only the Python standard library. For **branded PDF** output and the
**backend API**, install dependencies:

```bash
pip install -r requirements.txt   # ReportLab (PDF) + Flask (API)
```

Output lands in `output/` (git-ignored): `cma_report.html` always, plus
`cma_report.pdf` when ReportLab is installed.

### Live MLS data

```bash
python main.py --source simplyrets   # pulls live comps from the RESO Web API
```

Uses the SimplyRETS sandbox by default; set credentials in `.env` (see
`.env.example`) for your own feed. Falls back to sample data if the feed is
unreachable.

### Agent web app (interactive)

One command starts both the API and the UI (installs deps on first run; Ctrl+C
stops both):

```bash
./run.sh                 # then open http://localhost:5173
```

Or start them separately:

```bash
# 1) backend API (serves the engine + shareable reports)
python web/server.py                         # http://localhost:8000

# 2) agent UI (in another terminal)
cd web/app && npm install && npm run dev      # http://localhost:5173
```

The UI talks to the backend (engine stays the single source of truth) and
provides: editable subject, live price panel, comp toggles synced with a map,
side-by-side comp comparison, net-proceeds calculator, what-if upgrade simulator,
pricing-strategy slider, and the send-to-client flow (shareable link + email/text
with a "client viewed" indicator — the agent always confirms before anything sends).

## Architecture

Four independent modules, so swapping sample data for a live RESO feed is a
**single-file change** — the engine and report never learn where the data came from.

| Module | Responsibility |
| --- | --- |
| `engine/cma_engine.py` | Core IP. Pure Python, zero data-source dependency. Derives adjustment values from local comps, weights by similarity/recency/distance, flags outliers, returns Low/Likely/High + a 0–100 confidence score with plain-language reasons. |
| `data/sample_comps.py` | The **only** file that knows about specific properties. Sample subject + comps in RESO Data Dictionary field names. Replace with a live SimplyRETS / MLSGrid / Trestle loader of the same shape. |
| `report/report.py` | Branded report. HTML always; PDF via ReportLab when installed. Bakes in brokerage attribution, MLS verification links, and the "not an appraisal" disclaimer. |
| `engine/regression.py` | Optional data-driven adjustments — ridge regression fit on each market's comps, with validation and per-feature fallback to the heuristics. |
| `data/reso_loader.py` | Live SimplyRETS / RESO Web API loader. Same dict shape as the sample data. |
| `web/server.py` | Flask backend: engine over HTTP, shareable tokenized reports, client view tracking, confirmation-gated send-to-client. |
| `web/app/` | React (Vite) agent UI. |
| `main.py` | CLI entry point that wires it together. |

## What "smart" means

- **Market-derived adjustments** — price/sqft is the median of `ClosePrice / LivingArea`
  across the closed comps; per-feature values (bed, bath, garage, age) are anchored to
  that local price/sqft; pool value is measured from the comp set when the data supports it.
- **Weighted comps** — each comp is weighted by similarity × recency × distance × listing
  status; active listings count less than closed sales.
- **Outlier handling** — statistical outliers (robust median/MAD) are flagged and
  down-weighted, never silently dropped.
- **Transparent** — the agent can toggle comps in/out (`--exclude`) and the valuation
  recomputes. Every adjustment is itemized.

## Data & compliance

- Targets the **RESO Web API** via an aggregator: SimplyRETS sandbox for build/test;
  MLSGrid or Trestle for production. Uses RESO Data Dictionary field names
  (`LivingArea`, `ClosePrice`, `StandardStatus`, `ListingId`, `ListOfficeName`, …).
- Reports include brokerage attribution ("Listing courtesy of …"), MLS listing links
  as the authoritative verification source, and a prominent "not an appraisal" disclaimer.
- **MLS credentials never get committed.** `.gitignore` blocks `.env`, `*.key`, and
  `credentials.json` — put aggregator keys in a `.env` file.

## Status & roadmap

Done:
- Market-derived engine + regression model; sample, SimplyRETS, and MLSGrid/Trestle
  (RESO OData) data sources
- Branded HTML/PDF report with 4 templates (seller / buyer / expired / FSBO),
  market-trend mini-charts, MLS verification links, and the disclaimer
- **Multi-tenant accounts**: agent sign-in (PBKDF2 + signed tokens), per-agent
  branding applied to every report, owner-scoped + **versioned** reports with
  price-movement diffs
- Send-to-client flow with view tracking (draft → confirm; handoff or app-mode
  via SMTP/Twilio behind the confirmation gate)
- Public "what's my home worth" lead-capture widget (`/widget/<agent_id>`) +
  agent leads dashboard
- React agent UI: auth, account/branding drawer, live price panel, comp toggles +
  synced map, trends, side-by-side compare, net-proceeds, what-if simulator,
  pricing-strategy slider, versioned share
- **Admin role** (first account to register): manage the active MLS data source +
  API credentials and email/SMS transport, test the connection, and see all
  agents — from an in-app Admin panel
- **Smart** auto-generated, editable "why this price" narrative + a market-aware
  list-price recommendation
- **PDF export** of the branded report from the UI ("Download PDF") and the CLI
- "Pull comps from MLS" in the UI uses the admin-configured source

- **SQLite database** (stdlib) backs all persistence — accounts, versioned
  reports, leads, settings — with one-time import of any legacy JSON store
- **Billing tiers** (free / pro / team) with per-month report limits enforced on
  create; in-app plan picker (demo upgrade, no payment) and admin plan control
- **Per-MLS display rules**: retention windows (drop sales too old to display),
  attribution enforcement, refresh/cache TTL, and per-source display disclaimers,
  admin-configurable per source

Next:
- Wire a real payment processor (Stripe Checkout) behind the upgrade flow
- Wire a real email/SMS transport account for production sends
- Move PDF rendering to use each template's copy (HTML already does)
- Background refresh jobs + retention sweeps for cached MLS data

> The web app now requires sign-in. Create an account on first load, or use the
> CLI (`python main.py`) which needs no account.

> This tool produces an opinion of value for marketing purposes. It is **not an
> appraisal** and is not a substitute for one.
