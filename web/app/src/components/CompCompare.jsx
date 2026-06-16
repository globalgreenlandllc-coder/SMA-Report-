import { money } from "../util.js";

// Side-by-side: subject vs the selected comp, feature by feature, with the
// dollar adjustment the engine applied for each line.
export default function CompCompare({ subject, comp }) {
  if (!comp) return <p className="muted">Select a comp to compare it with the subject.</p>;
  const b = comp.breakdown || {};
  const rows = [
    ["Living area", `${subject.LivingArea} sqft`, `${comp.LivingArea} sqft`, b.sqft],
    ["Bedrooms", subject.BedroomsTotal, comp.BedroomsTotal, b.beds],
    ["Bathrooms", subject.BathroomsTotalInteger, comp.BathroomsTotalInteger, b.baths],
    ["Garage", subject.GarageSpaces, comp.GarageSpaces, b.garage],
    ["Pool", subject.PoolPrivateYN ? "Yes" : "No", comp.PoolPrivateYN ? "Yes" : "No", b.pool],
    ["Year built", subject.YearBuilt, comp.YearBuilt, b.age],
  ];
  return (
    <div>
      <table className="compare">
        <thead>
          <tr><th>Feature</th><th>Subject</th><th>{comp.ListingId}</th><th>Adj.</th></tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r[0]}</td>
              <td>{r[1]}</td>
              <td>{r[2]}</td>
              <td className={Number(r[3]) >= 0 ? "pos" : "neg"}>
                {r[3] > 0 ? "+" : ""}{money(r[3])}
              </td>
            </tr>
          ))}
          <tr className="total">
            <td>Comp sale/list</td><td colSpan={2}></td><td>{money(comp.base_price)}</td>
          </tr>
          <tr className="total">
            <td>Total adjustment</td><td colSpan={2}></td>
            <td>{comp.total_adjustment > 0 ? "+" : ""}{money(comp.total_adjustment)}</td>
          </tr>
          <tr className="total grand">
            <td>Adjusted value</td><td colSpan={2}></td><td>{money(comp.adjusted_price)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
