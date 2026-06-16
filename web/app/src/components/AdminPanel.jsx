import { useEffect, useState } from "react";
import { api } from "../api.js";

// Admin-only: manage the MLS/RESO data source + API credentials, test the
// connection, and see all agents on the account.
export default function AdminPanel({ onClose }) {
  const [s, setS] = useState({});
  const [agents, setAgents] = useState([]);
  const [status, setStatus] = useState("");
  const [test, setTest] = useState(null);

  useEffect(() => {
    api.adminGetSettings().then((d) => setS(d.settings || {})).catch(() => {});
    api.adminAgents().then((d) => setAgents(d.agents)).catch(() => {});
  }, []);

  const set = (k, v) => setS((p) => ({ ...p, [k]: v }));
  const source = s.data_source || "sample";

  async function save() {
    setStatus("Saving…");
    try { await api.adminPutSettings(s); setStatus("Saved."); }
    catch (e) { setStatus("Error: " + e.message); }
  }
  async function runTest() {
    setTest({ loading: true });
    try { setTest(await api.adminTestSource()); }
    catch (e) { setTest({ ok: false, note: e.message }); }
  }
  async function changePlan(id, plan) {
    setAgents((list) => list.map((a) => (a.id === id ? { ...a, plan } : a)));
    try { await api.adminSetPlan(id, plan); } catch (e) { setStatus("Error: " + e.message); }
  }

  const F = ({ label, k, ph, type }) => (
    <label className="field tight"><span>{label}</span>
      <input type={type || "text"} value={s[k] || ""} placeholder={ph}
        onChange={(e) => set(k, e.target.value)} />
    </label>
  );

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Admin · API & data sources</h2>
          <button onClick={onClose}>✕</button>
        </div>

        <h3>MLS data source</h3>
        <label className="field tight"><span>Active source</span>
          <select value={source} onChange={(e) => set("data_source", e.target.value)}>
            <option value="sample">Sample data (no MLS)</option>
            <option value="simplyrets">SimplyRETS (sandbox/test)</option>
            <option value="mlsgrid">MLSGrid (production)</option>
            <option value="trestle">Trestle / CoreLogic (production)</option>
          </select>
        </label>

        {source === "simplyrets" && (
          <div className="grid2">
            <F label="API key" k="simplyrets_key" ph="leave blank for sandbox" />
            <F label="API secret" k="simplyrets_secret" ph="leave blank for sandbox" type="password" />
          </div>
        )}
        {source === "mlsgrid" && (
          <>
            <F label="API token" k="mlsgrid_token" type="password" />
            <F label="Base URL" k="mlsgrid_base_url" ph="https://api.mlsgrid.com/v2" />
          </>
        )}
        {source === "trestle" && (
          <div className="grid2">
            <F label="Client ID" k="trestle_client_id" />
            <F label="Client secret" k="trestle_client_secret" type="password" />
            <F label="Base URL" k="trestle_base_url" ph="…/trestle/odata" />
            <F label="Token URL" k="trestle_token_url" ph="…/connect/token" />
          </div>
        )}

        <div className="admin-actions">
          <button className="primary" onClick={save}>Save settings</button>
          <button onClick={runTest}>Test connection</button>
        </div>
        {status && <div className="status">{status}</div>}
        {test && !test.loading && (
          <div className={"test-result " + (test.ok ? "ok" : "bad")}>
            {test.ok ? `✓ ${test.source}: pulled ${test.sample_count} records.`
                     : `✕ ${test.note || "failed"}`}
            {test.meta && (
              <div className="muted small" style={{ marginTop: 4 }}>
                Retention: {test.meta.retention_months ?? "n/a"} mo · refresh every {test.meta.refresh_minutes || 0} min
                {test.meta.dropped_retention ? ` · ${test.meta.dropped_retention} dropped (too old)` : ""}
                <br />{test.meta.disclaimer}
              </div>
            )}
          </div>
        )}

        <h3 style={{ marginTop: 24 }}>Display rules (per source)</h3>
        <p className="muted small">Match these to your MLS license terms.</p>
        <div className="grid2">
          <F label="Retention (months)" k={`${source}_retention_months`} ph="e.g. 36" />
          <F label="Refresh (minutes)" k={`${source}_refresh_minutes`} ph="e.g. 60" />
        </div>
        <label className="field tight"><span>Display disclaimer</span>
          <textarea rows={2} value={s[`${source}_disclaimer`] || ""}
            onChange={(e) => set(`${source}_disclaimer`, e.target.value)} />
        </label>
        <button className="primary" onClick={save}>Save display rules</button>

        <h3 style={{ marginTop: 24 }}>Email / SMS transport</h3>
        <p className="muted small">Used for app-mode sends (behind agent confirmation).</p>
        <div className="grid2">
          <F label="SMTP host" k="smtp_host" />
          <F label="SMTP port" k="smtp_port" ph="587" />
          <F label="SMTP user" k="smtp_user" />
          <F label="SMTP password" k="smtp_pass" type="password" />
          <F label="From address" k="smtp_from" />
        </div>
        <div className="grid2">
          <F label="Twilio SID" k="twilio_account_sid" />
          <F label="Twilio token" k="twilio_auth_token" type="password" />
          <F label="Twilio from #" k="twilio_from" />
        </div>
        <button className="primary" onClick={save}>Save transport</button>

        <h3 style={{ marginTop: 24 }}>Agents ({agents.length})</h3>
        <div className="lead-list">
          {agents.map((a) => (
            <div className="lead" key={a.id}>
              <div className="agent-row">
                <div>
                  <strong>{a.branding?.agent_name || a.email}</strong>
                  {a.role === "admin" && <span className="tag" style={{ marginLeft: 6 }}>admin</span>}
                  <div className="muted small">{a.email} · {a.report_count} reports · {a.lead_count} leads</div>
                </div>
                <select value={a.plan || "free"} onChange={(e) => changePlan(a.id, e.target.value)}>
                  <option value="free">Free</option>
                  <option value="pro">Pro</option>
                  <option value="team">Team</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
