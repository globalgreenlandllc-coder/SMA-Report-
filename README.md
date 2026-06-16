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

No install is required to run — the engine, sample data, and HTML report use only
the Python standard library. For **branded PDF** output, install the optional
dependency:

```bash
pip install -r requirements.txt   # adds ReportLab for PDF
```

Output lands in `output/` (git-ignored): `cma_report.html` always, plus
`cma_report.pdf` when ReportLab is installed.

## Architecture

Four independent modules, so swapping sample data for a live RESO feed is a
**single-file change** — the engine and report never learn where the data came from.

| Module | Responsibility |
| --- | --- |
| `engine/cma_engine.py` | Core IP. Pure Python, zero data-source dependency. Derives adjustment values from local comps, weights by similarity/recency/distance, flags outliers, returns Low/Likely/High + a 0–100 confidence score with plain-language reasons. |
| `data/sample_comps.py` | The **only** file that knows about specific properties. Sample subject + comps in RESO Data Dictionary field names. Replace with a live SimplyRETS / MLSGrid / Trestle loader of the same shape. |
| `report/report.py` | Branded report. HTML always; PDF via ReportLab when installed. Bakes in brokerage attribution, MLS verification links, and the "not an appraisal" disclaimer. |
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

## Roadmap (next tasks)

- Live SimplyRETS loader to replace `data/sample_comps.py`
- React agent UI (`web/`) with synced map, live price panel, net-proceeds and
  what-if-upgrade simulators
- Send-to-client flow (branded link + email + text, agent confirms before send)
- Auth + multi-tenant accounts
- Regression-fit adjustment model per market (replacing the ppsf-anchored heuristics)

> This tool produces an opinion of value for marketing purposes. It is **not an
> appraisal** and is not a substitute for one.
