import { useEffect, useState } from "react";
import { money } from "../util.js";

// Smart pricing recommendation + auto-generated, editable "why this price" copy.
export default function SmartSummary({ result, narrative, onNarrative }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(narrative || "");

  // Refresh editable draft when the engine regenerates the narrative,
  // unless the agent is mid-edit.
  useEffect(() => {
    if (!editing) setDraft(result?.narrative || "");
  }, [result?.narrative, editing]);

  if (!result) return null;
  const rec = result.recommendation || {};

  return (
    <div className="card smart">
      <div className="smart-head">
        <span className="badge-ai">✦ Smart</span>
        <h3 style={{ margin: 0 }}>Pricing recommendation</h3>
      </div>

      <div className="rec-box">
        <div>
          <div className="rec-label">Recommended list price</div>
          <div className="rec-price">{money(rec.recommended_list_price)}</div>
        </div>
        <div className="rec-pace">{rec.expected_pace}</div>
      </div>
      <p className="rec-rationale">{rec.rationale}</p>

      <div className="narr-head">
        <span className="muted small">Auto-generated narrative (editable)</span>
        {!editing ? (
          <button className="link-btn" onClick={() => { setDraft(result.narrative || ""); setEditing(true); }}>Edit</button>
        ) : (
          <span>
            <button className="link-btn" onClick={() => { onNarrative(draft); setEditing(false); }}>Save</button>
            <button className="link-btn" onClick={() => { onNarrative(null); setEditing(false); }}>Reset</button>
          </span>
        )}
      </div>
      {editing ? (
        <textarea className="narr-edit" rows={6} value={draft} onChange={(e) => setDraft(e.target.value)} />
      ) : (
        <p className="narr-text">{narrative || result.narrative}</p>
      )}
    </div>
  );
}
