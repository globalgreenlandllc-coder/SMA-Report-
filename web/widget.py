"""
widget.py -- Embeddable public "What's my home worth?" lead-capture widget.

Served at /widget/<agent_id>. A homeowner enters their address + contact details;
the form POSTs to /api/leads, which files the lead under the agent. Branded with
the agent's colors so it drops cleanly onto their own website (via an <iframe>).
"""
from __future__ import annotations

import html


def render_widget(account: dict, base_url: str) -> str:
    b = account.get("branding", {})
    agent = html.escape(str(b.get("agent_name", "Your Agent")))
    brokerage = html.escape(str(b.get("brokerage", "")))
    primary = b.get("primary_color", "#1f6feb")
    agent_id = html.escape(str(account.get("id", "")))

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>What's my home worth?</title>
<style>
  :root {{ --primary: {primary}; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; margin: 0;
         background: transparent; color: #1a1a1a; }}
  .widget {{ max-width: 420px; margin: 0 auto; border: 1px solid #e6e8ec; border-radius: 14px;
            padding: 22px; background: #fff; }}
  .widget h2 {{ margin: 0 0 4px; font-size: 19px; }}
  .widget p.sub {{ margin: 0 0 16px; color: #7a8290; font-size: 13px; }}
  .widget label {{ display: block; font-size: 12px; color: #7a8290; margin: 10px 0 4px; }}
  .widget input {{ width: 100%; padding: 10px; border: 1px solid #e6e8ec; border-radius: 8px; font: inherit; }}
  .widget button {{ width: 100%; margin-top: 16px; padding: 12px; border: none; border-radius: 8px;
                   background: var(--primary); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }}
  .widget .agent {{ margin-top: 14px; font-size: 12px; color: #7a8290; text-align: center; }}
  .widget .ok {{ text-align: center; padding: 20px 0; }}
  .widget .ok h3 {{ color: var(--primary); }}
</style></head>
<body>
  <div class="widget" id="w">
    <h2>What's my home worth?</h2>
    <p class="sub">Get a free, no-obligation market analysis from {agent}.</p>
    <form id="lead-form">
      <label>Property address</label>
      <input name="address" required placeholder="123 Main St, City, ST" />
      <label>Your name</label>
      <input name="name" placeholder="First and last name" />
      <label>Email</label>
      <input name="email" type="email" placeholder="you@email.com" />
      <label>Phone</label>
      <input name="phone" placeholder="(555) 555-5555" />
      <button type="submit">Get my home value</button>
    </form>
    <div class="agent">{agent}{(" &middot; " + brokerage) if brokerage else ""}</div>
  </div>
<script>
  const BASE = {("'" + base_url + "'")};
  const AGENT_ID = "{agent_id}";
  document.getElementById('lead-form').addEventListener('submit', async (e) => {{
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {{ agent_id: AGENT_ID }};
    fd.forEach((v, k) => payload[k] = v);
    try {{
      const res = await fetch(BASE + '/api/leads', {{
        method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload)
      }});
      if (!res.ok) throw new Error('failed');
      document.getElementById('w').innerHTML =
        '<div class="ok"><h3>Thank you!</h3><p>' +
        '{agent} will be in touch with your home value analysis shortly.</p></div>';
    }} catch (err) {{
      alert('Sorry, something went wrong. Please try again.');
    }}
  }});
</script>
</body></html>"""
