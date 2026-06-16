import { money } from "../util.js";

export default function PricePanel({ result, loading }) {
  if (!result) return <div className="card">Run a valuation to see pricing.</div>;
  const adj = result.adjustments || {};
  const conf = result.confidence ?? 0;
  return (
    <div className={"card price-panel" + (loading ? " loading" : "")}>
      <div className="band">
        <div className="box">
          <div className="lbl">Low</div>
          <div className="val">{money(result.low)}</div>
        </div>
        <div className="box likely">
          <div className="lbl">Likely</div>
          <div className="val">{money(result.likely)}</div>
        </div>
        <div className="box">
          <div className="lbl">High</div>
          <div className="val">{money(result.high)}</div>
        </div>
      </div>

      <div className="conf">
        <div className="conf-row">
          <strong>Confidence {conf}/100</strong>
          <span className="muted">
            {adj.method === "regression" && adj.regression
              ? `regression R² ${adj.regression.r2} (n=${adj.regression.n})`
              : "heuristic model"}
            {" · "}${adj.price_per_sqft}/sqft
          </span>
        </div>
        <div className="conf-bar">
          <div className="conf-fill" style={{ width: `${conf}%` }} />
        </div>
      </div>

      <details className="why">
        <summary>Why this price</summary>
        <ul>
          {(result.reasons || []).map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}
