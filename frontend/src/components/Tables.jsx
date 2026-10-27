import { mw, signedMw, pct, utcLabel } from "../format.js";

export function DailyTable({ daily }) {
  const max = Math.max(1, ...daily.map((d) => d.mae_mw ?? 0));
  return (
    <section aria-labelledby="daily-h">
      <h2 id="daily-h">Daily error summary</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Date</th><th className="n">MAE</th><th></th><th className="n">RMSE</th><th className="n">Bias</th><th className="n">Matched</th></tr>
          </thead>
          <tbody>
            {daily.map((d) => (
              <tr key={d.date}>
                <td>{d.date}</td>
                <td className="n">{mw(d.mae_mw)}</td>
                <td className="bar-cell"><span className="bar" style={{ width: `${((d.mae_mw ?? 0) / max) * 100}%` }} /></td>
                <td className="n">{mw(d.rmse_mw)}</td>
                <td className="n">{signedMw(d.bias_mw)}</td>
                <td className="n">{d.matched_intervals}/{d.expected_intervals} ({pct(d.coverage, 0)})</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function TopErrors({ rows, onInspect }) {
  return (
    <section aria-labelledby="top-h">
      <h2 id="top-h">Largest forecast errors</h2>
      {rows.length === 0 ? (
        <p className="empty">No matched intervals.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Delivery interval</th><th className="n">Actual</th><th className="n">Forecast</th><th className="n">Error</th><th>Published</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.t}>
                  <td>{utcLabel(r.t)}</td>
                  <td className="n">{mw(r.actual_mw)}</td>
                  <td className="n">{mw(r.forecast_mw)}</td>
                  <td className="n strong">{signedMw(r.error_mw)}</td>
                  <td>{utcLabel(r.publish_time)}</td>
                  <td><button className="link" onClick={() => onInspect(r.t)}>Vintages</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
