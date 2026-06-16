// Thin client for the SMA-Report backend. All paths are relative; the Vite dev
// server proxies /api and /r to the Flask backend on :8000.

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}

async function get(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}

export const api = {
  getSample: () => get("/api/sample"),
  runCma: (payload) => post("/api/cma", payload),
  createReport: (payload) => post("/api/reports", payload),
  getViews: (token) => get(`/api/reports/${token}/views`),
  share: (token, payload) => post(`/api/reports/${token}/share`, payload),
};
