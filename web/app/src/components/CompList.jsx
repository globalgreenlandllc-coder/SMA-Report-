import { money } from "../util.js";

// Comp toggle list. Toggling a comp recomputes the valuation server-side.
// Hover syncs with the map; clicking the row selects it for side-by-side compare.
export default function CompList({ comps, includes, onToggle, onHover, onSelect, selectedId }) {
  if (!comps) return null;
  return (
    <div className="card">
      <h3>Comparables <span className="muted">({comps.length})</span></h3>
      <div className="comp-list">
        {comps.map((c) => {
          const included = includes[c.ListingId] !== false;
          return (
            <div
              key={c.ListingId}
              className={
                "comp-row" +
                (included ? "" : " excluded") +
                (c.is_outlier ? " outlier" : "") +
                (selectedId === c.ListingId ? " selected" : "")
              }
              onMouseEnter={() => onHover && onHover(c.ListingId)}
              onMouseLeave={() => onHover && onHover(null)}
              onClick={() => onSelect && onSelect(c.ListingId)}
            >
              <label className="comp-toggle" onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  checked={included}
                  onChange={() => onToggle(c.ListingId)}
                />
              </label>
              <div className="comp-main">
                <div className="comp-id">
                  {c.ListingId}
                  {c.is_outlier && <span className="tag">outlier</span>}
                  <span className="status">{c.StandardStatus}</span>
                </div>
                <div className="comp-addr">{c.address}</div>
                <div className="comp-courtesy">Listing courtesy of {c.ListOfficeName}</div>
              </div>
              <div className="comp-nums">
                <div className="adj">{money(c.adjusted_price)}</div>
                <div className="muted small">
                  base {money(c.base_price)} · {c.distance_mi}mi · {c.months_old}mo
                </div>
                {c.ListingUrl && (
                  <a
                    className="mls-link"
                    href={c.ListingUrl}
                    target="_blank"
                    rel="noopener"
                    onClick={(e) => e.stopPropagation()}
                  >
                    verify on MLS ↗
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
