// Synced mini-map: plots comps relative to the subject by lat/lon offset (no tile
// dependency, works offline). Hover/selection is shared with the comp list.
export default function MiniMap({ subject, comps, hoverId, selectedId, onHover, onSelect }) {
  if (!subject || !comps) return null;
  const W = 320, H = 240, pad = 24;

  const pts = comps
    .filter((c) => c.Latitude != null && c.Longitude != null)
    .map((c) => ({ id: c.ListingId, lat: c.Latitude, lng: c.Longitude, c }));

  const lats = [subject.Latitude, ...pts.map((p) => p.lat)];
  const lngs = [subject.Longitude, ...pts.map((p) => p.lng)];
  let minLat = Math.min(...lats), maxLat = Math.max(...lats);
  let minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  // pad degenerate ranges
  if (maxLat - minLat < 1e-4) { minLat -= 0.002; maxLat += 0.002; }
  if (maxLng - minLng < 1e-4) { minLng -= 0.002; maxLng += 0.002; }

  const x = (lng) => pad + ((lng - minLng) / (maxLng - minLng)) * (W - 2 * pad);
  const y = (lat) => H - pad - ((lat - minLat) / (maxLat - minLat)) * (H - 2 * pad);

  return (
    <div className="card">
      <h3>Location <span className="muted">subject + comps</span></h3>
      <svg className="minimap" viewBox={`0 0 ${W} ${H}`} width="100%">
        <rect x="0" y="0" width={W} height={H} rx="8" fill="#eef2f7" />
        {pts.map((p) => {
          const included = p.c.included !== false;
          const active = hoverId === p.id || selectedId === p.id;
          return (
            <g
              key={p.id}
              onMouseEnter={() => onHover && onHover(p.id)}
              onMouseLeave={() => onHover && onHover(null)}
              onClick={() => onSelect && onSelect(p.id)}
              style={{ cursor: "pointer" }}
            >
              <circle
                cx={x(p.lng)}
                cy={y(p.lat)}
                r={active ? 9 : 6}
                fill={p.c.is_outlier ? "#d9534f" : included ? "#1f6feb" : "#aab"}
                fillOpacity={included ? 0.9 : 0.4}
                stroke="#fff"
                strokeWidth="1.5"
              />
              {active && (
                <text x={x(p.lng) + 11} y={y(p.lat) + 4} fontSize="10" fill="#222">
                  {p.id}
                </text>
              )}
            </g>
          );
        })}
        {/* subject marker */}
        <g>
          <circle cx={x(subject.Longitude)} cy={y(subject.Latitude)} r="8" fill="#0b3d91" stroke="#fff" strokeWidth="2" />
          <text x={x(subject.Longitude) + 11} y={y(subject.Latitude) + 4} fontSize="10" fontWeight="700" fill="#0b3d91">
            Subject
          </text>
        </g>
      </svg>
    </div>
  );
}
