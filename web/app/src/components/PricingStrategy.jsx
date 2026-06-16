import { useState } from "react";
import { money } from "../util.js";

// Pricing strategy slider: drag a list price, see where it sits in the comp
// range and the projected days-on-market / overpricing risk.
export default function PricingStrategy({ result }) {
  const low = result?.low ?? 0;
  const high = result?.high ?? 0;
  const likely = result?.likely ?? 0;
  const min = Math.round(low * 0.92);
  const max = Math.round(high * 1.12);
  const [price, setPrice] = useState(likely);

  // Overpricing premium relative to likely value.
  const premium = likely ? (price - likely) / likely : 0;
  // Simple DOM model: baseline ~30 days at likely, climbs fast when overpriced,
  // dips slightly when priced below market.
  const baseDom = 30;
  const dom = Math.max(5, Math.round(baseDom * (1 + Math.max(0, premium) * 6 + (premium < 0 ? premium * 1.5 : 0))));

  let risk = "Aggressive (fast sale)";
  let cls = "good";
  if (premium > 0.06) { risk = "High overpricing risk"; cls = "bad"; }
  else if (premium > 0.02) { risk = "Slightly above market"; cls = "warn"; }
  else if (premium >= -0.02) { risk = "At market"; cls = "ok"; }

  const posPct = ((price - min) / (max - min)) * 100;

  return (
    <div>
      <div className="strategy-readout">
        <div className="strategy-price">{money(price)}</div>
        <div className={"pill " + cls}>{risk}</div>
      </div>
      <input
        className="slider"
        type="range"
        min={min}
        max={max}
        step={1000}
        value={price}
        onChange={(e) => setPrice(Number(e.target.value))}
      />
      <div className="range-track">
        <span className="tick" style={{ left: `${((low - min) / (max - min)) * 100}%` }}>Low</span>
        <span className="tick" style={{ left: `${((likely - min) / (max - min)) * 100}%` }}>Likely</span>
        <span className="tick" style={{ left: `${((high - min) / (max - min)) * 100}%` }}>High</span>
        <span className="marker" style={{ left: `${posPct}%` }} />
      </div>
      <div className="breakdown" style={{ marginTop: 28 }}>
        <div><span>vs. likely value</span><span>{(premium * 100).toFixed(1)}%</span></div>
        <div><span>Projected days on market</span><span>~{dom} days</span></div>
      </div>
    </div>
  );
}
