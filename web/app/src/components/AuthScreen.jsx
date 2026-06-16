import { useState } from "react";
import { api, token } from "../api.js";

// Sign-in / sign-up gate. On success, stores the token and hands the agent up.
export default function AuthScreen({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agentName, setAgentName] = useState("");
  const [brokerage, setBrokerage] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const fn = mode === "login" ? api.login : api.register;
      const res = await fn({ email, password, agent_name: agentName, brokerage });
      token.set(res.token);
      onAuthed(res.agent);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <h1>SMA-Report</h1>
        <p className="muted">Smart CMA for real estate agents</p>

        <div className="auth-tabs">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Sign in</button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Create account</button>
        </div>

        {mode === "register" && (
          <>
            <label className="field"><span>Your name</span>
              <input value={agentName} onChange={(e) => setAgentName(e.target.value)} placeholder="Jordan Avery" />
            </label>
            <label className="field"><span>Brokerage</span>
              <input value={brokerage} onChange={(e) => setBrokerage(e.target.value)} placeholder="Lone Star Realty" />
            </label>
          </>
        )}
        <label className="field"><span>Email</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label className="field"><span>Password</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required placeholder="6+ characters" />
        </label>

        {err && <div className="auth-err">{err}</div>}
        <button className="primary" disabled={busy}>{mode === "login" ? "Sign in" : "Create account"}</button>
      </form>
    </div>
  );
}
