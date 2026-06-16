// Thin client for the SMA-Report backend. All paths are relative; the Vite dev
// server proxies /api and /r to the Flask backend on :8000. The bearer token is
// kept in localStorage and attached to every request.

const TOKEN_KEY = "sma_token";

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

function headers(extra) {
  const h = { "Content-Type": "application/json", ...(extra || {}) };
  const t = token.get();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function req(path, method, body) {
  const res = await fetch(path, {
    method,
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { msg = (await res.json()).error || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  // auth
  register: (b) => req("/api/auth/register", "POST", b),
  login: (b) => req("/api/auth/login", "POST", b),
  me: () => req("/api/auth/me", "GET"),
  updateBranding: (b) => req("/api/account/branding", "PUT", b),
  // engine + data
  getSample: () => req("/api/sample", "GET"),
  runCma: (b) => req("/api/cma", "POST", b),
  getTemplates: () => req("/api/templates", "GET"),
  // reports
  createReport: (b) => req("/api/reports", "POST", b),
  listReports: () => req("/api/reports", "GET"),
  getHistory: (tok) => req(`/api/reports/${tok}/history`, "GET"),
  getViews: (tok) => req(`/api/reports/${tok}/views`, "GET"),
  share: (tok, b) => req(`/api/reports/${tok}/share`, "POST", b),
  // leads
  listLeads: () => req("/api/leads", "GET"),
  // data source
  getComps: (limit = 25) => req(`/api/comps?limit=${limit}`, "GET"),
  // billing
  getBilling: () => req("/api/billing", "GET"),
  upgrade: (plan) => req("/api/billing/upgrade", "POST", { plan }),
  // admin
  adminGetSettings: () => req("/api/admin/settings", "GET"),
  adminPutSettings: (b) => req("/api/admin/settings", "PUT", b),
  adminAgents: () => req("/api/admin/agents", "GET"),
  adminTestSource: () => req("/api/admin/test-source", "POST", {}),
  adminSetPlan: (id, plan) => req(`/api/admin/agents/${id}/plan`, "PUT", { plan }),
  // pdf download (returns a Blob, not JSON)
  async downloadPdf(payload) {
    const res = await fetch("/api/report/pdf", {
      method: "POST", headers: headers(), body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`PDF failed (HTTP ${res.status})`);
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="(.+?)"/);
    return { blob, filename: m ? m[1] : "cma-report.pdf" };
  },
};

