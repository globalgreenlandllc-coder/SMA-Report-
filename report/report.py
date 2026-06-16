"""
report.py -- Branded, seller-ready CMA report generation.

Two output surfaces from one engine result:
  * HTML  -- always available, no third-party dependencies.
  * PDF   -- rendered with ReportLab when it is installed (see requirements.txt).

Compliance is baked in (do not remove):
  * Per-comp brokerage attribution -- "Listing courtesy of <ListOfficeName>".
  * MLS listing links as the authoritative verification source for every comp.
  * A prominent "this is not an appraisal" disclaimer.
"""
from __future__ import annotations

import html
import os

from .templates import get_template

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:  # ReportLab is optional; HTML still works without it.
    REPORTLAB_AVAILABLE = False


DISCLAIMER = (
    "This Comparative Market Analysis is an opinion of value prepared by a real "
    "estate licensee for marketing purposes. It is NOT an appraisal and is not a "
    "substitute for one. Comparable data is sourced from the MLS and believed "
    "reliable but is not guaranteed; verify each comparable via its MLS listing."
)


def _money(n) -> str:
    try:
        return "${:,.0f}".format(float(n))
    except (TypeError, ValueError):
        return "n/a"


def _signed_money(n) -> str:
    v = float(n)
    sign = "+" if v > 0 else ("-" if v < 0 else "")
    return f"{sign}${abs(v):,.0f}"


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _sparkline(series, width=220, height=44):
    """Tiny inline SVG sparkline of monthly price-per-sqft."""
    pts = [p["ppsf"] for p in series]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    rng = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    coords = " ".join(
        f"{i*step:.1f},{height - 4 - ((v - lo) / rng) * (height - 8):.1f}"
        for i, v in enumerate(pts)
    )
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<polyline points="{coords}" fill="none" stroke="#1f6feb" stroke-width="2"/>'
            f'</svg>')


def _render_trends(trends) -> str:
    if not trends:
        return ""
    spark = _sparkline(trends.get("ppsf_series", []))
    moi = trends.get("months_of_inventory")
    s2l = trends.get("sold_to_list_pct")
    return f"""
  <div class="section">
    <h2>Market Trends</h2>
    <div class="kv">
      <div><span>Months of inventory</span><br>{moi if moi is not None else 'n/a'} ({html.escape(trends.get('market_label',''))})</div>
      <div><span>Sold-to-list ratio</span><br>{str(s2l) + '%' if s2l is not None else 'n/a'}</div>
      <div><span>Closed / active comps</span><br>{trends.get('n_closed',0)} / {trends.get('n_active',0)}</div>
      <div><span>$/sqft trend</span><br>{spark or 'n/a'}</div>
    </div>
  </div>"""


def render_html(result: dict, branding: dict, template: str = "seller") -> str:
    s = result["subject"]
    tpl = get_template(template)
    primary = branding.get("primary_color", "#1f6feb")
    accent = branding.get("accent_color", "#0b3d91")
    addr = html.escape(str(s.get("UnparsedAddress", "Subject Property")))

    # ---- comp rows ----
    rows = []
    for c in result["comps"]:
        included = c.get("included", True)
        outlier = c.get("is_outlier", False)
        flags = []
        if not included:
            flags.append("excluded")
        if outlier:
            flags.append("outlier")
        status_badge = c.get("StandardStatus", "")
        row_style = "opacity:.45;" if not included else ""
        link = c.get("ListingUrl") or "#"
        rows.append(f"""
          <tr style="{row_style}">
            <td>
              <a href="{html.escape(link)}" target="_blank" rel="noopener">{html.escape(str(c.get('ListingId','')))}</a>
              <div class="addr">{html.escape(str(c.get('address') or ''))}</div>
              <div class="courtesy">Listing courtesy of {html.escape(str(c.get('ListOfficeName') or 'N/A'))}</div>
            </td>
            <td>{html.escape(str(status_badge))}</td>
            <td class="num">{_money(c.get('base_price'))}</td>
            <td class="num">{_signed_money(c.get('total_adjustment'))}</td>
            <td class="num"><strong>{_money(c.get('adjusted_price'))}</strong></td>
            <td class="num">{c.get('distance_mi')} mi</td>
            <td class="num">{c.get('months_old')} mo</td>
            <td class="num">{c.get('weight')}</td>
            <td>{' '.join(f'<span class="flag">{f}</span>' for f in flags)}</td>
          </tr>""")
    comp_rows = "\n".join(rows)

    reasons = "\n".join(f"<li>{html.escape(r)}</li>" for r in result["reasons"])
    adj = result["adjustments"]
    conf = result["confidence"]
    trends_html = _render_trends(result.get("trends"))
    rec = result.get("recommendation") or {}
    narrative = html.escape(result.get("narrative", "")) if result.get("narrative") else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CMA -- {addr}</title>
<style>
  :root {{ --primary: {primary}; --accent: {accent}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         margin: 0; color: #1a1a1a; background: #f6f7f9; }}
  .wrap {{ max-width: 940px; margin: 0 auto; background: #fff; }}
  header {{ background: var(--primary); color: #fff; padding: 28px 36px; }}
  header h1 {{ margin: 0 0 4px; font-size: 22px; }}
  header .agent {{ font-size: 14px; opacity: .92; }}
  .section {{ padding: 24px 36px; border-bottom: 1px solid #eee; }}
  .price-band {{ display: flex; gap: 16px; text-align: center; }}
  .price-band .box {{ flex: 1; border: 1px solid #e3e3e3; border-radius: 10px; padding: 16px; }}
  .price-band .likely {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
  .price-band .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .05em; opacity: .8; }}
  .price-band .val {{ font-size: 26px; font-weight: 700; margin-top: 4px; }}
  .conf-wrap {{ margin-top: 18px; }}
  .conf-bar {{ height: 14px; border-radius: 7px; background: #e7e7e7; overflow: hidden; }}
  .conf-fill {{ height: 100%; background: linear-gradient(90deg, #d9534f, #f0ad4e, #5cb85c); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
  th {{ background: #fafbfc; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #555; }}
  td.num, th.num {{ text-align: right; white-space: nowrap; }}
  .addr {{ color: #666; font-size: 12px; }}
  .courtesy {{ color: #999; font-size: 11px; font-style: italic; }}
  .flag {{ display: inline-block; background: #ffe9e9; color: #b00; font-size: 10px;
          padding: 1px 6px; border-radius: 4px; text-transform: uppercase; }}
  .kv {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px 20px; font-size: 13px; }}
  .kv div span {{ color: #777; }}
  ul.reasons {{ margin: 0; padding-left: 18px; font-size: 13px; line-height: 1.6; }}
  .disclaimer {{ background: #fff8e6; border-top: 2px solid #f0ad4e; color: #5b4500;
                font-size: 12px; padding: 18px 36px; }}
  h2 {{ font-size: 15px; text-transform: uppercase; letter-spacing: .04em; color: var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{html.escape(tpl['title'])}</h1>
    <div class="subtitle" style="font-size:13px;opacity:.9;margin-bottom:4px;">{html.escape(tpl['subtitle'])}</div>
    <div class="agent">
      {html.escape(str(branding.get('agent_name','')))} &middot;
      {html.escape(str(branding.get('brokerage','')))} &middot;
      {html.escape(str(branding.get('phone','')))} &middot;
      {html.escape(str(branding.get('email','')))}
    </div>
  </header>

  <div class="section" style="background:#f8fafd;">
    <p style="margin:0;font-size:14px;color:#333;">{html.escape(tpl['intro'])}</p>
  </div>

  <div class="section">
    <h2>Subject Property</h2>
    <div style="font-size:16px;font-weight:600;margin-bottom:10px;">{addr}</div>
    <div class="kv">
      <div><span>Living area</span><br>{int(s.get('LivingArea',0)):,} sqft</div>
      <div><span>Beds / Baths</span><br>{s.get('BedroomsTotal','?')} / {s.get('BathroomsTotalInteger','?')}</div>
      <div><span>Garage</span><br>{s.get('GarageSpaces','?')} car</div>
      <div><span>Pool</span><br>{'Yes' if s.get('PoolPrivateYN') else 'No'}</div>
      <div><span>Year built</span><br>{s.get('YearBuilt','?')}</div>
      <div><span>As of</span><br>{result.get('ref_date','')}</div>
    </div>
  </div>

  <div class="section">
    <h2>Estimated Value</h2>
    <div class="price-band">
      <div class="box"><div class="label">Low</div><div class="val">{_money(result['low'])}</div></div>
      <div class="box likely"><div class="label">Likely</div><div class="val">{_money(result['likely'])}</div></div>
      <div class="box"><div class="label">High</div><div class="val">{_money(result['high'])}</div></div>
    </div>
    <div class="conf-wrap">
      <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px;">
        <strong>Confidence: {conf}/100</strong>
        <span>Derived price/sqft: {_money(adj['price_per_sqft'])}</span>
      </div>
      <div class="conf-bar"><div class="conf-fill" style="width:{conf}%;"></div></div>
    </div>
  </div>

  {(f'''<div class="section" style="background:#eef4ff;">
    <div style="font-size:13px;color:#555;">Recommended list price</div>
    <div style="font-size:24px;font-weight:700;color:{accent};">{_money(rec.get('recommended_list_price'))}</div>
    <div style="font-size:13px;color:#444;margin-top:4px;">{html.escape(rec.get('rationale',''))} <em>Expected pace: {html.escape(rec.get('expected_pace',''))}.</em></div>
  </div>''') if rec else ''}

  <div class="section">
    <h2>Why This Price</h2>
    {(f'<p style="font-size:14px;line-height:1.6;color:#333;">{narrative}</p>') if narrative else ''}
    <ul class="reasons">{reasons}</ul>
  </div>

  <div class="section">
    <h2>Market-Derived Adjustments</h2>
    <p style="font-size:12px;color:#666;margin-top:-4px;">
      Method: <strong>{html.escape(str(adj.get('method','heuristic')))}</strong>{
        f" (regression R&sup2; {adj['regression']['r2']}, n={adj['regression']['n']}, "
        f"fit: {', '.join(adj['regression']['features_used']) or 'none'})"
        if adj.get('regression') else ''
      }
    </p>
    <div class="kv">
      <div><span>$/sqft</span><br>{_money(adj['price_per_sqft'])}</div>
      <div><span>Per bedroom</span><br>{_money(adj['bed_value'])}</div>
      <div><span>Per bath</span><br>{_money(adj['bath_value'])}</div>
      <div><span>Per garage space</span><br>{_money(adj['garage_value'])}</div>
      <div><span>Pool ({adj['pool_value_source']})</span><br>{_money(adj['pool_value'])}</div>
      <div><span>Per year of age</span><br>{_money(adj['age_value_per_year'])}</div>
    </div>
  </div>

  {trends_html}

  <div class="section">
    <h2>Comparable Listings ({result['n_comps']} used, {result['n_closed']} closed)</h2>
    <table>
      <thead><tr>
        <th>Comp / Verification</th><th>Status</th><th class="num">Sale/List</th>
        <th class="num">Adjust.</th><th class="num">Adjusted</th>
        <th class="num">Dist.</th><th class="num">Age</th><th class="num">Weight</th><th></th>
      </tr></thead>
      <tbody>{comp_rows}</tbody>
    </table>
    <p style="font-size:11px;color:#888;margin-top:10px;">
      Each comp links to its MLS listing -- the authoritative source for verification.
    </p>
  </div>

  <div class="disclaimer"><strong>Disclaimer.</strong> {html.escape(DISCLAIMER)}</div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# PDF report (ReportLab)
# ---------------------------------------------------------------------------

def _render_pdf(result: dict, branding: dict, target, template: str = "seller") -> None:
    s = result["subject"]
    tpl = get_template(template)
    primary = colors.HexColor(branding.get("primary_color", "#1f6feb"))
    accent = colors.HexColor(branding.get("accent_color", "#0b3d91"))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("H", parent=styles["Heading2"], textColor=accent, fontSize=12))
    styles.add(ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey))
    styles.add(ParagraphStyle("Courtesy", parent=styles["Normal"], fontSize=7,
                              textColor=colors.grey, fontName="Helvetica-Oblique"))

    doc = SimpleDocTemplate(target, pagesize=letter,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    flow = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"], textColor=primary, fontSize=20)
    flow.append(Paragraph(tpl["title"], title_style))
    flow.append(Paragraph(
        f"{branding.get('agent_name','')} &middot; {branding.get('brokerage','')} "
        f"&middot; {branding.get('phone','')} &middot; {branding.get('email','')}",
        styles["Small"]))
    flow.append(Spacer(1, 14))

    flow.append(Paragraph("Subject Property", styles["H"]))
    flow.append(Paragraph(f"<b>{html.escape(str(s.get('UnparsedAddress','')))}</b>", styles["Normal"]))
    flow.append(Paragraph(
        f"{int(s.get('LivingArea',0)):,} sqft &middot; {s.get('BedroomsTotal','?')} bd / "
        f"{s.get('BathroomsTotalInteger','?')} ba &middot; {s.get('GarageSpaces','?')}-car garage "
        f"&middot; {'Pool' if s.get('PoolPrivateYN') else 'No pool'} &middot; built {s.get('YearBuilt','?')}",
        styles["Normal"]))
    flow.append(Spacer(1, 12))

    band = Table([
        ["LOW", "LIKELY", "HIGH"],
        [_money(result["low"]), _money(result["likely"]), _money(result["high"])],
    ], colWidths=[2.3 * inch] * 3)
    band.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.grey),
        ("BACKGROUND", (1, 0), (1, 1), accent),
        ("TEXTCOLOR", (1, 0), (1, 1), colors.white),
        ("BOX", (0, 0), (0, 1), 0.5, colors.lightgrey),
        ("BOX", (2, 0), (2, 1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    flow.append(band)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(f"<b>Confidence: {result['confidence']}/100</b> &middot; "
                          f"derived $/sqft {_money(result['adjustments']['price_per_sqft'])}",
                          styles["Normal"]))
    flow.append(Spacer(1, 12))

    if result.get("recommendation"):
        rec = result["recommendation"]
        flow.append(Paragraph(
            f"<b>Recommended list price: {_money(rec['recommended_list_price'])}</b> "
            f"&mdash; {html.escape(rec['rationale'])} Expected pace: {html.escape(rec['expected_pace'])}.",
            styles["Normal"]))
        flow.append(Spacer(1, 10))

    flow.append(Paragraph("Why This Price", styles["H"]))
    if result.get("narrative"):
        flow.append(Paragraph(html.escape(result["narrative"]), styles["Normal"]))
        flow.append(Spacer(1, 6))
    for r in result["reasons"]:
        flow.append(Paragraph(f"&bull; {html.escape(r)}", styles["Normal"]))
    flow.append(Spacer(1, 12))

    flow.append(Paragraph(
        f"Comparable Listings ({result['n_comps']} used, {result['n_closed']} closed)",
        styles["H"]))
    data = [["Comp", "Status", "Sale/List", "Adjust.", "Adjusted", "Dist", "Age", "Wt"]]
    for c in result["comps"]:
        if not c.get("included", True):
            continue
        comp_cell = Paragraph(
            f"<b>{html.escape(str(c.get('ListingId','')))}</b>"
            + (" <font color='red'>[outlier]</font>" if c.get("is_outlier") else "")
            + f"<br/><font size=6>Listing courtesy of {html.escape(str(c.get('ListOfficeName') or 'N/A'))}</font>",
            styles["Normal"])
        data.append([
            comp_cell, c.get("StandardStatus", ""), _money(c.get("base_price")),
            _signed_money(c.get("total_adjustment")), _money(c.get("adjusted_price")),
            f"{c.get('distance_mi')}mi", f"{c.get('months_old')}mo", str(c.get("weight")),
        ])
    tbl = Table(data, colWidths=[1.9 * inch, 0.6 * inch, 0.8 * inch, 0.7 * inch,
                                 0.8 * inch, 0.5 * inch, 0.5 * inch, 0.5 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(tbl)
    flow.append(Paragraph("Each comp links to its MLS listing -- the authoritative "
                          "source for verification.", styles["Small"]))
    flow.append(Spacer(1, 16))

    flow.append(Paragraph("Disclaimer", styles["H"]))
    flow.append(Paragraph(DISCLAIMER, styles["Small"]))

    doc.build(flow)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_report(result: dict, branding: dict, out_dir: str = "output",
                    basename: str = "cma_report", template: str = "seller") -> dict:
    """
    Write the report to ``out_dir``. Always writes HTML; also writes PDF when
    ReportLab is installed. Returns {"html": path, "pdf": path|None}.
    """
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"{basename}.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(result, branding, template=template))

    pdf_path = None
    if REPORTLAB_AVAILABLE:
        pdf_path = os.path.join(out_dir, f"{basename}.pdf")
        _render_pdf(result, branding, pdf_path, template=template)

    return {"html": html_path, "pdf": pdf_path}


def generate_pdf_bytes(result: dict, branding: dict, template: str = "seller") -> bytes:
    """Render the branded PDF to bytes (for HTTP download). Requires ReportLab."""
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab is not installed; run pip install -r requirements.txt")
    import io
    buf = io.BytesIO()
    _render_pdf(result, branding, buf, template=template)
    return buf.getvalue()
