import { useState, useEffect } from "react";
import { api } from "../api.js";
import { money } from "../util.js";

// Send-to-client flow. The agent saves a shareable report, then shares via link,
// email, or text. Email/text first returns a DRAFT the agent reviews; nothing is
// sent until the agent clicks Confirm & send.
export default function SharePanel({ buildPayload }) {
  const [token, setToken] = useState(null);
  const [url, setUrl] = useState("");
  const [clientName, setClientName] = useState("");
  const [channel, setChannel] = useState("email");
  const [to, setTo] = useState("");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState(null);
  const [status, setStatus] = useState("");
  const [views, setViews] = useState(null);
  const [history, setHistory] = useState(null);
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);

  // Poll view tracking so the agent sees the "client viewed" indicator.
  useEffect(() => {
    if (!token) return;
    const tick = () => api.getViews(token).then(setViews).catch(() => {});
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [token]);

  async function save() {
    setBusy(true);
    setStatus("");
    try {
      const res = await api.createReport({
        ...buildPayload(),
        client_name: clientName,
        token: token || undefined, // re-save same report -> new version
      });
      setToken(res.token);
      setVersion(res.version);
      setUrl(window.location.origin + res.url.replace(/^https?:\/\/[^/]+/, ""));
      setStatus(res.version > 1 ? `Saved v${res.version}.` : "Saved.");
      try { setHistory(await api.getHistory(res.token)); } catch {}
    } catch (e) {
      setStatus("Error: " + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function prepare() {
    setBusy(true); setDraft(null); setStatus("");
    try {
      const res = await api.share(token, { channel, to, message });
      if (res.status === "link_generated") { setUrl(res.url); setStatus("Link ready."); }
      else { setDraft(res.draft); setStatus("Review the draft, then confirm to send."); }
    } catch (e) { setStatus("Error: " + e.message); }
    finally { setBusy(false); }
  }

  async function confirmSend(mode) {
    setBusy(true);
    try {
      const res = await api.share(token, { channel, to, message, confirmed: true, mode });
      if (res.status === "handoff") {
        window.location.href = res.handoff_url; // open agent's own mail/sms client
        setStatus("Opened your mail/messages app to send.");
      } else {
        setStatus(res.transmitted ? "Sent." : "Recorded (simulated): " + (res.note || ""));
      }
      setDraft(null);
    } catch (e) { setStatus("Error: " + e.message); }
    finally { setBusy(false); }
  }

  return (
    <div className="card share">
      <h3>Send to client</h3>

      {!token ? (
        <>
          <label className="field"><span>Client name</span>
            <input value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="e.g. The Garcias" />
          </label>
          <button disabled={busy} onClick={save}>Save shareable report</button>
        </>
      ) : (
        <>
          <div className="link-row">
            <input readOnly value={url} onFocus={(e) => e.target.select()} />
            <button onClick={() => navigator.clipboard?.writeText(url)}>Copy</button>
          </div>

          <div className={"view-indicator " + (views?.viewed ? "seen" : "")}>
            {views?.viewed
              ? `✓ Client viewed (${views.view_count}× · last ${new Date(views.last_viewed_at).toLocaleString()})`
              : "Not viewed yet"}
          </div>

          <div className="version-row">
            <span className="muted small">Version {version}</span>
            <button disabled={busy} onClick={save}>Re-run & save new version</button>
          </div>
          {history && history.versions.length > 1 && (
            <div className="history">
              <span className={"delta " + (history.delta_likely >= 0 ? "up" : "down")}>
                {history.delta_likely >= 0 ? "▲" : "▼"} {money(Math.abs(history.delta_likely))} ({history.delta_pct.toFixed(1)}%) since v1
              </span>
              <div className="muted small">
                {history.versions.map((v) => `v${v.version}: ${money(v.likely)}`).join("  ·  ")}
              </div>
            </div>
          )}

          <div className="channel-row">
            {["email", "sms", "link"].map((ch) => (
              <button key={ch} className={channel === ch ? "active" : ""} onClick={() => setChannel(ch)}>
                {ch}
              </button>
            ))}
          </div>

          {channel !== "link" && (
            <label className="field"><span>{channel === "email" ? "Email" : "Phone"}</span>
              <input value={to} onChange={(e) => setTo(e.target.value)}
                placeholder={channel === "email" ? "client@email.com" : "+15125550100"} />
            </label>
          )}
          {channel === "email" && (
            <label className="field"><span>Note (optional)</span>
              <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={2} />
            </label>
          )}

          <button disabled={busy} onClick={prepare}>
            {channel === "link" ? "Get link" : "Prepare draft"}
          </button>

          {draft && (
            <div className="draft">
              <div className="draft-head">Draft — review before sending</div>
              {draft.subject && <div className="draft-sub"><b>Subject:</b> {draft.subject}</div>}
              <pre>{draft.body}</pre>
              <div className="confirm-row">
                <button className="primary" disabled={busy} onClick={() => confirmSend("handoff")}>
                  Confirm & send from my {channel === "email" ? "email" : "phone"}
                </button>
                <button disabled={busy} onClick={() => confirmSend("app")}>
                  Confirm & send via app
                </button>
              </div>
              <p className="muted small">Nothing is sent to your client until you confirm.</p>
            </div>
          )}
        </>
      )}
      {status && <div className="status">{status}</div>}
    </div>
  );
}
