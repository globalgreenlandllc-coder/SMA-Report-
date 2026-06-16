import { useEffect, useState } from "react";
import { api } from "../api.js";

// Subscription plan + usage. Upgrade is a demo (no real payment is collected).
export default function Billing() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("");

  const load = () => api.getBilling().then(setData).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!data) return null;

  const { plan, plans, usage } = data;

  async function choose(p) {
    if (p === plan) return;
    setStatus("Updating…");
    try { await api.upgrade(p); setStatus("Plan updated (demo — no payment collected)."); load(); }
    catch (e) { setStatus("Error: " + e.message); }
  }

  return (
    <div>
      <div className="usage-bar">
        <span>Reports this month: <strong>{usage.reports_this_month}</strong>
          {usage.limit != null ? ` / ${usage.limit}` : " (unlimited)"}</span>
      </div>
      <div className="plan-grid">
        {Object.entries(plans).map(([key, p]) => (
          <div key={key} className={"plan-card" + (key === plan ? " current" : "")}>
            <div className="plan-name">{p.label}</div>
            <div className="plan-price">{p.price === 0 ? "Free" : `$${p.price}/mo`}</div>
            <div className="plan-feat muted small">
              {p.reports_per_month == null ? "Unlimited reports" : `${p.reports_per_month} reports/mo`}
              <br />{p.seats} seat{p.seats > 1 ? "s" : ""}
            </div>
            <button className={key === plan ? "" : "primary"} disabled={key === plan} onClick={() => choose(key)}>
              {key === plan ? "Current plan" : "Choose"}
            </button>
          </div>
        ))}
      </div>
      {status && <div className="status">{status}</div>}
    </div>
  );
}
