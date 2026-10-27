import { useEffect, useState } from "react";
import { apiGet } from "../api.js";
import { mw, signedMw, utcLabel } from "../format.js";

export default function VintageDialog({ target, params, onClose }) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let live = true;
    apiGet("/api/vintages", { target, mode: params.mode, cutoff_time: params.cutoff_time, lead_days: params.lead_days, horizon_hours: params.mode === "horizon" ? params.horizon_hours : undefined })
      .then((d) => live && setState({ data: d }))
      .catch((e) => live && setState({ error: e.message }));
    return () => { live = false; };
  }, [target, params]);

  return (
    <div className="dialog-back" onClick={onClose}>
      <div className="dialog" role="dialog" aria-modal="true" aria-label="Forecast vintages" onClick={(e) => e.stopPropagation()}>
        <div className="section-head">
          <h2>Forecast vintages for {utcLabel(target)}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {state.loading && <p>Loading…</p>}
        {state.error && <p className="error">{state.error}</p>}
        {state.data && (
          <>
            <p className="note">Cutoff {utcLabel(state.data.cutoff)} · Actual {mw(state.data.actual_mw)}. Vintages published after the cutoff were not available to the buyer.</p>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Published</th><th className="n">Lead</th><th className="n">Forecast</th><th className="n">Error</th><th>Status</th></tr></thead>
                <tbody>
                  {state.data.vintages.map((v) => (
                    <tr key={v.publish_time} className={v.selected ? "selected" : v.eligible ? "" : "late"}>
                      <td>{utcLabel(v.publish_time)}</td>
                      <td className="n">{v.hours_before_delivery.toFixed(1)} h</td>
                      <td className="n">{mw(v.forecast_mw)}</td>
                      <td className="n">{signedMw(v.error_mw)}</td>
                      <td>{v.selected ? "Used" : v.eligible ? "Earlier vintage" : "After cutoff – excluded"}</td>
                    </tr>
                  ))}
                  {state.data.vintages.length === 0 && <tr><td colSpan="5">No forecasts published for this interval.</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
