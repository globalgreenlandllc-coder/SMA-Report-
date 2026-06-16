import { useEffect, useState } from "react";
import { api } from "../api.js";

// Slide-over panel: agent branding (applied to every report), the embeddable
// lead-capture widget snippet, and captured leads.
export default function AccountPanel({ agent, onClose, onBrandingSaved }) {
  const [b, setB] = useState(agent.branding || {});
  const [leads, setLeads] = useState([]);
  const [status, setStatus] = useState("");

  useEffect(() => {
    api.listLeads().then((d) => setLeads(d.leads)).catch(() => {});
  }, []);

  const set = (k, v) => setB((s) => ({ ...s, [k]: v }));

  async function save() {
    setStatus("Saving…");
    try {
      const res = await api.updateBranding(b);
      onBrandingSaved(res.branding);
      setStatus("Branding saved — applied to every report.");
    } catch (e) {
      setStatus("Error: " + e.message);
    }
  }

  const widgetUrl = `${window.location.origin}/widget/${agent.id}`;
  const embed = `<iframe src="${widgetUrl}" width="440" height="520" style="border:0" title="Home value"></iframe>`;

  const F = ({ label, k, type }) => (
    <label className="field tight"><span>{label}</span>
      <input type={type || "text"} value={b[k] || ""} onChange={(e) => set(k, e.target.value)} />
    </label>
  );

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <h2>Account & branding</h2>
          <button onClick={onClose}>✕</button>
        </div>

        <h3>Branding</h3>
        <p className="muted small">Applied to every report and your lead widget.</p>
        <div className="grid2">
          <F label="Agent name" k="agent_name" />
          <F label="Title" k="title" />
          <F label="Brokerage" k="brokerage" />
          <F label="License" k="license" />
          <F label="Phone" k="phone" />
          <F label="Email" k="email" type="email" />
          <F label="Logo URL" k="logo_url" />
          <F label="Headshot URL" k="headshot_url" />
          <label className="field tight"><span>Primary color</span>
            <input type="color" value={b.primary_color || "#1f6feb"} onChange={(e) => set("primary_color", e.target.value)} />
          </label>
          <label className="field tight"><span>Accent color</span>
            <input type="color" value={b.accent_color || "#0b3d91"} onChange={(e) => set("accent_color", e.target.value)} />
          </label>
        </div>
        <button className="primary" onClick={save}>Save branding</button>
        {status && <div className="status">{status}</div>}

        <h3 style={{ marginTop: 24 }}>Lead-capture widget</h3>
        <p className="muted small">Embed this “What's my home worth?” form on your site.</p>
        <div className="link-row">
          <input readOnly value={widgetUrl} onFocus={(e) => e.target.select()} />
          <a href={widgetUrl} target="_blank" rel="noopener"><button>Open</button></a>
        </div>
        <textarea className="embed" readOnly rows={2} value={embed} onFocus={(e) => e.target.select()} />

        <h3 style={{ marginTop: 24 }}>Leads ({leads.length})</h3>
        {leads.length === 0 ? (
          <p className="muted small">No leads yet. Share your widget to start capturing them.</p>
        ) : (
          <div className="lead-list">
            {leads.map((l, i) => (
              <div className="lead" key={i}>
                <div><strong>{l.address || "(no address)"}</strong></div>
                <div className="muted small">
                  {[l.name, l.email, l.phone].filter(Boolean).join(" · ")}
                </div>
                <div className="muted small">{new Date(l.at).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
