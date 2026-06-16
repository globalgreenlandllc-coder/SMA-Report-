#!/usr/bin/env python3
"""
main.py -- CLI entry point for SMA-Report.

Loads sample data, runs the CMA engine, prints a summary, and writes a branded
report. Swap ``data.sample_comps`` for a live RESO loader (same shape) and nothing
else changes.

Usage:
    python main.py                 # value the sample subject, write report to output/
    python main.py --exclude A-1007  # drop a comp and re-run (agent toggle)
    python main.py --json          # print the full engine result as JSON
"""
from __future__ import annotations

import argparse
import json

from data import SUBJECT, COMPS, AGENT_BRANDING
from engine import run_cma
from report import generate_report, REPORTLAB_AVAILABLE


def _money(n) -> str:
    return "${:,.0f}".format(n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a CMA report.")
    parser.add_argument("--exclude", nargs="*", default=[],
                        help="ListingId(s) to toggle out of the valuation.")
    parser.add_argument("--out", default="output", help="Output directory.")
    parser.add_argument("--source", default="sample", choices=["sample", "simplyrets"],
                        help="Comp data source (default: sample). 'simplyrets' pulls "
                             "live from the RESO Web API sandbox.")
    parser.add_argument("--limit", type=int, default=25,
                        help="Max comps to pull from a live source.")
    parser.add_argument("--method", default="auto",
                        choices=["auto", "regression", "heuristic"],
                        help="Adjustment model (default: auto).")
    parser.add_argument("--json", action="store_true",
                        help="Print the full engine result as JSON and exit.")
    args = parser.parse_args()

    comps = COMPS
    if args.source == "simplyrets":
        try:
            from data.reso_loader import load_comps
            comps = load_comps(limit=args.limit)
            print(f"[source] Pulled {len(comps)} live comps from SimplyRETS RESO API.")
        except Exception as exc:  # network/auth failure -> fall back, don't crash
            print(f"[source] Live feed unavailable ({exc}); falling back to sample data.")
            comps = COMPS

    include = {lid: False for lid in args.exclude}
    result = run_cma(SUBJECT, comps, include=include, method=args.method)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return

    s = result["subject"]
    print("=" * 64)
    print("  SMA-Report -- Comparative Market Analysis")
    print("=" * 64)
    print(f"  Subject : {s.get('UnparsedAddress')}")
    print(f"            {int(s.get('LivingArea',0)):,} sqft | "
          f"{s.get('BedroomsTotal')}bd/{s.get('BathroomsTotalInteger')}ba | "
          f"built {s.get('YearBuilt')} | as of {result['ref_date']}")
    print("-" * 64)
    print(f"  LOW      {_money(result['low'])}")
    print(f"  LIKELY   {_money(result['likely'])}   <-- recommended")
    print(f"  HIGH     {_money(result['high'])}")
    adj = result["adjustments"]
    method_note = adj.get("method", "heuristic")
    if adj.get("regression"):
        reg = adj["regression"]
        method_note += f" (R2={reg['r2']}, n={reg['n']}, fit: {', '.join(reg['features_used']) or 'none'})"
    print(f"  Confidence: {result['confidence']}/100   "
          f"(derived $/sqft {_money(adj['price_per_sqft'])})")
    print(f"  Model: {method_note}")
    print("-" * 64)
    print("  Why this price:")
    for r in result["reasons"]:
        print(f"    - {r}")
    print("-" * 64)
    print(f"  Comps ({result['n_comps']} used, {result['n_closed']} closed):")
    for c in result["comps"]:
        tags = []
        if not c.get("included", True):
            tags.append("EXCLUDED")
        if c.get("is_outlier"):
            tags.append("OUTLIER")
        tag = f"  [{', '.join(tags)}]" if tags else ""
        print(f"    {c['ListingId']:<8} {c.get('StandardStatus',''):<7} "
              f"base {_money(c['base_price']):>10}  ->  adj {_money(c['adjusted_price']):>10}  "
              f"(w={c['weight']}){tag}")
    print("-" * 64)

    paths = generate_report(result, AGENT_BRANDING, out_dir=args.out)
    print(f"  Report (HTML): {paths['html']}")
    if paths["pdf"]:
        print(f"  Report (PDF) : {paths['pdf']}")
    else:
        print("  Report (PDF) : skipped -- run `pip install -r requirements.txt` "
              "to enable ReportLab PDF output.")
    print("=" * 64)


if __name__ == "__main__":
    main()
