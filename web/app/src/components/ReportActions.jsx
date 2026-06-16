import { useState } from "react";
import { api } from "../api.js";

// Convert the current analysis into a deliverable: download the branded PDF, or
// open a print-ready preview in a new tab.
export default function ReportActions({ buildPayload }) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  async function downloadPdf() {
    setBusy(true); setStatus("Generating PDF…");
    try {
      const { blob, filename } = await api.downloadPdf(buildPayload());
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; document.body.appendChild(a); a.click();
      a.remove(); URL.revokeObjectURL(url);
      setStatus("Downloaded " + filename);
    } catch (e) {
      setStatus("Error: " + e.message);
    } finally { setBusy(false); }
  }

  return (
    <div className="card">
      <h3>Report</h3>
      <p className="muted small">Turn this analysis into a branded, seller-ready report.</p>
      <button className="primary block" disabled={busy} onClick={downloadPdf}>
        ⬇ Download PDF
      </button>
      {status && <div className="status">{status}</div>}
    </div>
  );
}
