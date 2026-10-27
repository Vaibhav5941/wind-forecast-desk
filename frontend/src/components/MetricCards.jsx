import { mw, signedMw, pct } from "../format.js";

function Card({ label, value, hint }) {
  return (
    <div className="metric">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-hint">{hint}</div>
    </div>
  );
}

export default function MetricCards({ metrics }) {
  return (
    <section aria-labelledby="acc-h">
      <h2 id="acc-h">Forecast accuracy</h2>
      <div className="metrics">
        <Card label="MAE" value={mw(metrics.mae_mw)} hint="mean of |forecast − actual|" />
        <Card label="RMSE" value={mw(metrics.rmse_mw)} hint="penalises large misses more" />
        <Card label="Mean bias" value={signedMw(metrics.bias_mw)}
          hint="mean of forecast − actual; + means over-forecast" />
        <Card label="nMAE" value={metrics.nmae_pct == null ? "–" : `${metrics.nmae_pct.toFixed(1)}%`}
          hint="MAE ÷ mean actual output of the same pairs" />
        <Card label="Sample" value={`${metrics.n.toLocaleString("en-GB")} / ${metrics.expected_intervals.toLocaleString("en-GB")}`}
          hint={`half-hours matched · coverage ${pct(metrics.coverage)}`} />
      </div>
    </section>
  );
}
