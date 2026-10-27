import { SOURCE_LABEL, pct, utcLabel } from "../format.js";

function Row({ k, v, warn }) {
  return (
    <tr className={warn ? "warn-row" : ""}>
      <th scope="row">{k}</th>
      <td className="n">{v}</td>
    </tr>
  );
}

export default function QualityPanel({ quality, forecastInfo }) {
  const a = quality.actual_cleaning;
  const f = quality.forecast_cleaning;
  return (
    <section aria-labelledby="dq-h">
      <h2 id="dq-h">Data transparency</h2>
      <div className="dq-grid">
        <table>
          <tbody>
            <Row k="Data source" v={SOURCE_LABEL[quality.data_source]} warn={quality.data_source === "synthetic"} />
            <Row k="Snapshot fetched" v={quality.fetched_at ? utcLabel(quality.fetched_at) : "n/a"} />
            <Row k="Actual records (valid, in period)" v={quality.actual_records_valid_in_period.toLocaleString("en-GB")} />
            <Row k="Forecast records (valid vintages, in period)" v={quality.forecast_records_valid_in_period.toLocaleString("en-GB")} />
            <Row k="Expected half-hour intervals" v={quality.expected_intervals.toLocaleString("en-GB")} />
            <Row k="Matched intervals" v={`${quality.matched_intervals.toLocaleString("en-GB")} (${pct(quality.coverage)})`} />
            <Row k="Missing intervals" v={quality.missing_intervals.toLocaleString("en-GB")} warn={quality.missing_intervals > 0} />
            <Row k=" – actual missing only" v={quality.missing_actual_only} />
            <Row k=" – no forecast available at cutoff" v={quality.missing_forecast_only} />
            <Row k=" – both missing" v={quality.missing_both} />
          </tbody>
        </table>
        <table>
          <tbody>
            <Row k="Decision cutoff (ASSUMPTION)" v={quality.cutoff.rule} warn />
            <Row k="First cutoff in period" v={utcLabel(quality.cutoff.first)} />
            <Row k="Last cutoff in period" v={utcLabel(quality.cutoff.last)} />
            <Row k="Forecast vintages excluded as too late" v={quality.forecast_vintages_excluded_after_cutoff.toLocaleString("en-GB")} />
            <Row k="Forecasts used: earliest published" v={utcLabel(forecastInfo.earliest_publish_used)} />
            <Row k="Forecasts used: latest published" v={utcLabel(forecastInfo.latest_publish_used)} />
            <Row k="Actual rows: null / invalid / duplicate" v={`${a.null_generation} / ${a.invalid_generation + a.invalid_timestamp} / ${a.duplicate_records}`} />
            <Row k="Forecast rows: null / invalid / duplicate" v={`${f.null_generation} / ${f.invalid_generation + f.invalid_timestamp} / ${f.duplicate_records}`} />
            <Row k="Conflicting duplicates (act / fc)" v={`${a.conflicting_duplicates} / ${f.conflicting_duplicates}`} warn={a.conflicting_duplicates + f.conflicting_duplicates > 0} />
          </tbody>
        </table>
      </div>
      {quality.missing_runs.length > 0 && (
        <details>
          <summary>Missing-interval ranges ({quality.missing_runs.length}{quality.missing_runs.length >= 50 ? "+" : ""})</summary>
          <ul className="runs">
            {quality.missing_runs.map((r) => (
              <li key={r.from}>{utcLabel(r.from)} → {utcLabel(r.to)} · {r.intervals} interval(s) · {r.statuses.join(", ").replace(/_/g, " ")}</li>
            ))}
          </ul>
        </details>
      )}
      <p className="note">Intervals are 30-minute settlement periods, shown in UTC. Units are MW (average over the half-hour for actuals).</p>
    </section>
  );
}
