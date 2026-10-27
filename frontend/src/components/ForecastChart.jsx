import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import { mw, signedMw, utcLabel, utcShort } from "../format.js";

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="tip">
      <div className="tip-time">{utcLabel(p.t)}</div>
      <div><span className="sw actual" /> Actual: {mw(p.actual_mw)}</div>
      <div><span className="sw fc" /> Forecast: {mw(p.forecast_mw)}</div>
      <div>Error (forecast − actual): {signedMw(p.error_mw)}</div>
      <div>Absolute error: {mw(p.abs_error_mw)}</div>
      <div className="tip-meta">Forecast published: {utcLabel(p.publish_time)}</div>
      <div className="tip-meta">Cutoff: {utcLabel(p.cutoff)}</div>
      {p.status !== "matched" && <div className="tip-warn">Unmatched: {p.status.replace(/_/g, " ")}</div>}
    </div>
  );
}

export default function ForecastChart({ points }) {
  const [showError, setShowError] = useState(false);
  // Gaps stay gaps: null values break the line rather than being drawn as zero.
  const data = useMemo(() => points, [points]);
  return (
    <section aria-labelledby="cmp-h">
      <div className="section-head">
        <h2 id="cmp-h">Actual vs decision-time forecast</h2>
        <label className="inline">
          <input type="checkbox" checked={showError} onChange={(e) => setShowError(e.target.checked)} />
          Show error (forecast − actual)
        </label>
      </div>
      <div className="chart" role="img" aria-label="Time series of actual and forecast wind generation in megawatts">
        <ResponsiveContainer width="100%" height={showError ? 240 : 340}>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 8 }} syncId="wind">
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis dataKey="t" tickFormatter={utcShort} minTickGap={48} stroke="var(--muted)" fontSize={12} />
            <YAxis tickFormatter={(v) => v.toLocaleString("en-GB")} stroke="var(--muted)" fontSize={12} width={64}
              label={{ value: "MW", angle: -90, position: "insideLeft", fill: "var(--muted)", fontSize: 12 }} />
            <Tooltip content={<Tip />} />
            <Legend verticalAlign="top" height={28} />
            <Line type="monotone" dataKey="actual_mw" name="Actual (FUELHH)" stroke="var(--actual)" dot={false} strokeWidth={1.6} connectNulls={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="forecast_mw" name="Forecast at cutoff (WINDFOR)" stroke="var(--forecast)" dot={false} strokeWidth={1.6} strokeDasharray="5 3" connectNulls={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        {showError && (
          <ResponsiveContainer width="100%" height={150}>
            <LineChart data={data} margin={{ top: 4, right: 16, bottom: 0, left: 8 }} syncId="wind">
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="t" tickFormatter={utcShort} minTickGap={48} stroke="var(--muted)" fontSize={12} />
              <YAxis tickFormatter={(v) => v.toLocaleString("en-GB")} stroke="var(--muted)" fontSize={12} width={64} />
              <ReferenceLine y={0} stroke="var(--muted)" />
              <Tooltip content={<Tip />} />
              <Line type="monotone" dataKey="error_mw" name="Error" stroke="var(--error)" dot={false} strokeWidth={1.2} connectNulls={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <p className="note">Times in UTC. Gaps in a line are intervals with no valid value; they are not zero-filled.</p>
    </section>
  );
}
