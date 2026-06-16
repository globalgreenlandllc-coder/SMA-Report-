import { useEffect, useRef, useState } from "react";
import { api, token } from "./api.js";
import AuthScreen from "./components/AuthScreen.jsx";
import AccountPanel from "./components/AccountPanel.jsx";
import PricePanel from "./components/PricePanel.jsx";
import CompList from "./components/CompList.jsx";
import MiniMap from "./components/MiniMap.jsx";
import TrendsPanel from "./components/TrendsPanel.jsx";
import NetProceeds from "./components/NetProceeds.jsx";
import WhatIf from "./components/WhatIf.jsx";
import PricingStrategy from "./components/PricingStrategy.jsx";
import CompCompare from "./components/CompCompare.jsx";
import SharePanel from "./components/SharePanel.jsx";

const TABS = ["Net proceeds", "What-if upgrade", "Pricing strategy", "Compare"];
const TEMPLATES = [
  ["seller", "Seller CMA"], ["buyer", "Buyer CMA"],
  ["expired", "Expired listing"], ["fsbo", "FSBO"],
];

export default function App() {
  const [agent, setAgent] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [showAccount, setShowAccount] = useState(false);

  const [subject, setSubject] = useState(null);
  const [comps, setComps] = useState(null);
  const [includes, setIncludes] = useState({});
  const [method, setMethod] = useState("auto");
  const [template, setTemplate] = useState("seller");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hoverId, setHoverId] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [tab, setTab] = useState(TABS[0]);
  const timer = useRef(null);

  // Restore session.
  useEffect(() => {
    if (!token.get()) { setAuthChecked(true); return; }
    api.me().then((d) => setAgent(d.agent)).catch(() => token.clear()).finally(() => setAuthChecked(true));
  }, []);

  // Load defaults once authed.
  useEffect(() => {
    if (!agent) return;
    api.getSample().then((d) => { setSubject(d.subject); setComps(d.comps); });
  }, [agent]);

  // Recompute (debounced) when inputs change. Engine stays the source of truth.
  useEffect(() => {
    if (!subject || !comps) return;
    clearTimeout(timer.current);
    setLoading(true);
    timer.current = setTimeout(async () => {
      try {
        setResult(await api.runCma({ subject, comps, include: includes, method }));
      } finally { setLoading(false); }
    }, 250);
    return () => clearTimeout(timer.current);
  }, [subject, comps, includes, method]);

  if (!authChecked) return <div className="loading-screen">Loading…</div>;
  if (!agent) return <AuthScreen onAuthed={setAgent} />;
  if (!subject) return <div className="loading-screen">Loading SMA-Report…</div>;

  const branding = agent.branding || {};
  const toggle = (id) => setIncludes((m) => ({ ...m, [id]: m[id] === false ? true : false }));
  const setSubjField = (k, v) => setSubject((s) => ({ ...s, [k]: v }));

  const compView = (result?.comps || comps).map((c) => ({
    ...comps.find((x) => x.ListingId === c.ListingId),
    ...c,
  }));
  const selectedComp = compView.find((c) => c.ListingId === selectedId) || null;

  const buildPayload = () => ({ subject, comps, include: includes, method, template, branding });

  const logout = () => { token.clear(); setAgent(null); };

  const Num = ({ label, field, step }) => (
    <label className="field tight"><span>{label}</span>
      <input type="number" step={step || 1} value={subject[field] ?? ""}
        onChange={(e) => setSubjField(field, Number(e.target.value))} />
    </label>
  );

  return (
    <div className="app">
      <header className="topbar">
        <div><strong>SMA-Report</strong> <span className="muted">Smart CMA</span></div>
        <div className="topbar-right">
          <span className="agent-chip">{branding.agent_name} · {branding.brokerage}</span>
          <button onClick={() => setShowAccount(true)}>Account</button>
          <button onClick={logout}>Sign out</button>
        </div>
      </header>

      <div className="layout">
        <aside className="col left">
          <div className="card">
            <h3>Subject property</h3>
            <label className="field tight"><span>Address</span>
              <input value={subject.UnparsedAddress || ""} onChange={(e) => setSubjField("UnparsedAddress", e.target.value)} />
            </label>
            <div className="grid2">
              <Num label="Living area (sqft)" field="LivingArea" />
              <Num label="Year built" field="YearBuilt" />
              <Num label="Beds" field="BedroomsTotal" />
              <Num label="Baths" field="BathroomsTotalInteger" />
              <Num label="Garage" field="GarageSpaces" />
              <label className="field tight"><span>Pool</span>
                <select value={subject.PoolPrivateYN ? "yes" : "no"} onChange={(e) => setSubjField("PoolPrivateYN", e.target.value === "yes")}>
                  <option value="no">No</option><option value="yes">Yes</option>
                </select>
              </label>
            </div>
            <div className="grid2">
              <label className="field tight"><span>Pricing model</span>
                <select value={method} onChange={(e) => setMethod(e.target.value)}>
                  <option value="auto">Auto</option>
                  <option value="regression">Regression</option>
                  <option value="heuristic">Heuristic</option>
                </select>
              </label>
              <label className="field tight"><span>Report template</span>
                <select value={template} onChange={(e) => setTemplate(e.target.value)}>
                  {TEMPLATES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </label>
            </div>
          </div>

          <MiniMap subject={subject} comps={compView} hoverId={hoverId} selectedId={selectedId} onHover={setHoverId} onSelect={setSelectedId} />
          <TrendsPanel trends={result?.trends} />
        </aside>

        <main className="col center">
          <PricePanel result={result} loading={loading} />
          <CompList comps={compView} includes={includes} onToggle={toggle} onHover={setHoverId} onSelect={setSelectedId} selectedId={selectedId} />
        </main>

        <aside className="col right">
          <div className="card">
            <div className="tabs">
              {TABS.map((t) => (
                <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>
              ))}
            </div>
            <div className="tab-body">
              {tab === "Net proceeds" && <NetProceeds likely={result?.likely} />}
              {tab === "What-if upgrade" && <WhatIf likely={result?.likely} />}
              {tab === "Pricing strategy" && <PricingStrategy result={result} />}
              {tab === "Compare" && <CompCompare subject={subject} comp={selectedComp} />}
            </div>
          </div>
          <SharePanel buildPayload={buildPayload} />
        </aside>
      </div>

      <footer className="disclaimer-bar">
        Opinion of value for marketing purposes — <strong>not an appraisal</strong>. Comps verified via their MLS listings.
      </footer>

      {showAccount && (
        <AccountPanel agent={agent} onClose={() => setShowAccount(false)}
          onBrandingSaved={(b) => setAgent((a) => ({ ...a, branding: b }))} />
      )}
    </div>
  );
}
