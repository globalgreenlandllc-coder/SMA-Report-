export const money = (n) =>
  n == null || isNaN(n)
    ? "--"
    : "$" + Math.round(n).toLocaleString("en-US");

export const pct = (n) => `${(n * 100).toFixed(1)}%`;

// Cost-vs-Value style recovery rates: share of an upgrade's cost recouped at
// resale. Seeds the what-if simulator (a real build would refresh these from the
// annual Cost vs. Value report per region).
export const RECOVERY = {
  "Minor kitchen remodel": 0.85,
  "Major kitchen remodel": 0.7,
  "Bathroom remodel": 0.66,
  "Add bathroom": 0.6,
  "New roof": 0.61,
  "Garage door replacement": 0.94,
  "Deck addition (wood)": 0.83,
  "Window replacement": 0.68,
  "Finished basement": 0.7,
  "Landscaping / curb appeal": 0.75,
  "Solar panels": 0.5,
  "Pool installation": 0.43,
};

// Debounce a function (used to throttle engine round-trips on slider/toggle).
export function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
