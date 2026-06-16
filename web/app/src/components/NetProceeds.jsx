import { useState } from "react";
import { money } from "../util.js";

// Net proceeds calculator -- "what the seller actually takes home."
export default function NetProceeds({ likely }) {
  const [salePrice, setSalePrice] = useState(likely || 0);
  const [commissionPct, setCommissionPct] = useState(5.5);
  const [loanPayoff, setLoanPayoff] = useState(0);
  const [closingPct, setClosingPct] = useState(1.5);
  const [repairs, setRepairs] = useState(0);

  const sp = Number(salePrice) || 0;
  const commission = sp * (Number(commissionPct) / 100);
  const closing = sp * (Number(closingPct) / 100);
  const net = sp - commission - closing - Number(loanPayoff || 0) - Number(repairs || 0);

  const Row = ({ label, children }) => (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );

  return (
    <div>
      <Row label="Sale price">
        <input type="number" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} />
      </Row>
      <Row label="Commission %">
        <input type="number" step="0.1" value={commissionPct} onChange={(e) => setCommissionPct(e.target.value)} />
      </Row>
      <Row label="Loan payoff">
        <input type="number" value={loanPayoff} onChange={(e) => setLoanPayoff(e.target.value)} />
      </Row>
      <Row label="Closing costs %">
        <input type="number" step="0.1" value={closingPct} onChange={(e) => setClosingPct(e.target.value)} />
      </Row>
      <Row label="Repairs / concessions">
        <input type="number" value={repairs} onChange={(e) => setRepairs(e.target.value)} />
      </Row>

      <div className="breakdown">
        <div><span>Commission</span><span>-{money(commission)}</span></div>
        <div><span>Closing</span><span>-{money(closing)}</span></div>
        <div><span>Loan payoff</span><span>-{money(loanPayoff)}</span></div>
        <div><span>Repairs</span><span>-{money(repairs)}</span></div>
      </div>
      <div className="net-result">
        Seller nets <strong>{money(net)}</strong>
      </div>
    </div>
  );
}
