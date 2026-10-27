import { useEffect, useMemo, useState } from "react";
import { apiGet } from "./api.js";
import Banner from "./components/Banner.jsx";
import Controls from "./components/Controls.jsx";
import ForecastChart from "./components/ForecastChart.jsx";
import MetricCards from "./components/MetricCards.jsx";
import QualityPanel from "./components/QualityPanel.jsx";
import { DailyTable, TopErrors } from "./components/Tables.jsx";
import VintageDialog from "./components/VintageDialog.jsx";
import { utcLabel } from "./format.js";

function useApi(path, params, enabled = true) {
  const [state, setState] = useState({ loading: enabled });
  const key = JSON.stringify([path, params, enabled]);
  useEffect(() => {
    if (!enabled) return undefined;
    let live = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    apiGet(path, params)
      .then((data) => live && setState({ data, loading: false }))
      .catch((error) => live && setState({ error: error.message, loading: false }));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

export default function App() {
  const cfg = useApi("/api/config", {});
  const [ctl, setCtl] = useState(null);
  const [inspect, setInspect] = useState(null);

  useEffect(() => {
    if (cfg.data && !ctl) {
      setCtl({ start: cfg.data.period_start, end: cfg.data.period_end, mode: "day_ahead",
        cutoff_time: cfg.data.default_cutoff_time, lead_days: cfg.data.default_lead_days, horizon_hours: 24 });
    }
  }, [cfg.data, ctl]);

  // Only send parameters relevant to the chosen mode; ignore half-typed values.
  const params = useMemo(() => {
    if (!ctl) return null;
    const p = { start: ctl.start, end: ctl.end, mode: ctl.mode };
    if (ctl.mode === "day_ahead") { p.cutoff_time = ctl.cutoff_time; p.lead_days = ctl.lead_days; }
    else p.horizon_hours = ctl.horizon_hours;
    return p;
  }, [ctl]);

  const summary = useApi("/api/summary", params, !!params);
  const series = useApi("/api/series", params, !!params);

  if (cfg.error) return <Shell><p className="error" role="alert">{cfg.error}</p></Shell>;
  if (!ctl) return <Shell><p>Loading…</p></Shell>;

  const s = summary.data;
  return (
    <Shell>
      <Controls config={cfg.data} value={ctl} onChange={setCtl} />
      {(summary.error || series.error) && <p className="error" role="alert">{summary.error || series.error}</p>}
      {summary.loading && !s && <p>Loading analysis…</p>}
      {s && (
        <div className={summary.loading ? "stale" : ""}>
          <Banner metrics={s.metrics} quality={s.quality} />
          <section aria-labelledby="sum-h">
            <h2 id="sum-h">Period summary</h2>
            <p className="note">Selection rule: {s.quality.cutoff.rule}. Latest forecast used was published {utcLabel(s.forecast_info.latest_publish_used)}.</p>
            <ul className="summary">{s.summary.map((t) => <li key={t}>{t}</li>)}</ul>
          </section>
          {s.metrics.n === 0 ? (
            <p className="empty">No matched forecast/actual intervals for this selection. Check the data-transparency panel below.</p>
          ) : (
            <MetricCards metrics={s.metrics} />
          )}
          {series.data && <ForecastChart points={series.data.points} />}
          <div className="two-col">
            <DailyTable daily={s.daily} />
            <TopErrors rows={s.top_errors} onInspect={setInspect} />
          </div>
          <QualityPanel quality={s.quality} forecastInfo={s.forecast_info} />
        </div>
      )}
      {inspect && <VintageDialog target={inspect} params={params} onClose={() => setInspect(null)} />}
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="app">
      <header>
        <h1>Wind Forecast Desk</h1>
        <p>GB national wind: decision-time forecast vs actual · Elexon FUELHH &amp; WINDFOR · January 2026</p>
      </header>
      <main>{children}</main>
      <footer>Error = forecast − actual. Decision cutoff is an assumption, not an Elexon-defined value. Analysis tool only; it does not optimise procurement.</footer>
    </div>
  );
}
