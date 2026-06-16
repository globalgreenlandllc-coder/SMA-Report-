import { useState } from "react";
import { money, pct, RECOVERY } from "../util.js";

// What-if upgrade simulator: pick an upgrade + cost, see projected price lift
// (cost x recovery rate) vs cost -- answers "should I renovate before selling?"
export default function WhatIf({ likely }) {
  const options = Object.keys(RECOVERY);
  const [type, setType] = useState(options[0]);
  const [cost, setCost] = useState(25000);

  const recovery = RECOVERY[type] ?? 0.6;
  const lift = Number(cost) * recovery;
  const newLikely = (likely || 0) + lift;
  const netEffect = lift - Number(cost);

  return (
    <div>
      <label className="field">
        <span>Upgrade</span>
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Cost</span>
        <input type="number" value={cost} onChange={(e) => setCost(e.target.value)} />
      </label>

      <div className="breakdown">
        <div><span>Cost recovery</span><span>{pct(recovery)}</span></div>
        <div><span>Projected price lift</span><span>+{money(lift)}</span></div>
        <div><span>New likely value</span><span>{money(newLikely)}</span></div>
      </div>
      <div className={"net-result " + (netEffect >= 0 ? "good" : "bad")}>
        {netEffect >= 0
          ? <>Adds ~{money(netEffect)} above its cost</>
          : <>Costs ~{money(-netEffect)} more than it returns</>}
      </div>
      <p className="muted small">
        Recovery rates seeded from Cost-vs-Value data; a renovation rarely returns 100%.
      </p>
    </div>
  );
}
