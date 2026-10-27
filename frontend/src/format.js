export const mw = (v, digits = 0) =>
  v === null || v === undefined ? "–" : `${Number(v).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;

export const signedMw = (v, digits = 0) => {
  if (v === null || v === undefined) return "–";
  const n = Number(v);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;
};

export const pct = (v, digits = 1) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(digits)}%`);

// All times are shown in UTC and labelled as such (Elexon startTime/publishTime are UTC).
export const utcLabel = (iso) => (iso ? `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC` : "–");
export const utcShort = (iso) => (iso ? `${iso.slice(5, 10)} ${iso.slice(11, 16)}` : "");

export const SOURCE_LABEL = {
  live: "Live Elexon API",
  cached: "Cached snapshot of Elexon API data",
  synthetic: "SYNTHETIC development fixtures (not real data)",
};
