// Market trend mini-charts: $/sqft sparkline, months of inventory, sold-to-list.
export default function TrendsPanel({ trends }) {
  if (!trends) return null;
  const series = trends.ppsf_series || [];
  const spark = sparkline(series);
  return (
    <div className="card">
      <h3>Market trends</h3>
      <div className="trend-grid">
        <div className="trend-cell">
          <div className="trend-num">{trends.months_of_inventory ?? "--"}</div>
          <div className="trend-lbl">months of inventory</div>
          <div className={"pill " + marketCls(trends.market_label)}>{trends.market_label}</div>
        </div>
        <div className="trend-cell">
          <div className="trend-num">{trends.sold_to_list_pct != null ? trends.sold_to_list_pct + "%" : "--"}</div>
          <div className="trend-lbl">sold-to-list ratio</div>
        </div>
      </div>
      <div className="trend-spark">
        <div className="trend-lbl">$/sqft over time</div>
        {spark}
        {series.length > 1 && (
          <div className="muted small">
            {series[0].month} → {series[series.length - 1].month}
            {" · "}${series[0].ppsf} → ${series[series.length - 1].ppsf}
          </div>
        )}
      </div>
    </div>
  );
}

function marketCls(label) {
  if (!label) return "ok";
  if (label.startsWith("seller")) return "good";
  if (label.startsWith("buyer")) return "bad";
  return "ok";
}

function sparkline(series) {
  const pts = series.map((p) => p.ppsf);
  if (pts.length < 2) return <div className="muted small">not enough sales</div>;
  const W = 260, H = 50, lo = Math.min(...pts), hi = Math.max(...pts), rng = hi - lo || 1;
  const step = W / (pts.length - 1);
  const coords = pts.map((v, i) => `${(i * step).toFixed(1)},${(H - 4 - ((v - lo) / rng) * (H - 8)).toFixed(1)}`).join(" ");
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="spark">
      <polyline points={coords} fill="none" stroke="var(--primary)" strokeWidth="2" />
    </svg>
  );
}
