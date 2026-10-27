export default function Controls({ config, value, onChange }) {
  const set = (patch) => onChange({ ...value, ...patch });
  return (
    <form className="controls" onSubmit={(e) => e.preventDefault()} aria-label="Analysis controls">
      <label>
        From
        <input type="date" value={value.start} min={config.period_start} max={config.period_end}
          onChange={(e) => set({ start: e.target.value })} />
      </label>
      <label>
        To
        <input type="date" value={value.end} min={config.period_start} max={config.period_end}
          onChange={(e) => set({ end: e.target.value })} />
      </label>
      <label>
        Forecast selection
        <select value={value.mode} onChange={(e) => set({ mode: e.target.value })}>
          <option value="day_ahead">Day-ahead cutoff (assumed)</option>
          <option value="horizon">Fixed lead time</option>
        </select>
      </label>
      {value.mode === "day_ahead" ? (
        <>
          <label>
            Cutoff time ({config.timezone})
            <input type="time" value={value.cutoff_time} onChange={(e) => set({ cutoff_time: e.target.value })} />
          </label>
          <label>
            Days before delivery
            <input type="number" min="0" max="7" value={value.lead_days}
              onChange={(e) => set({ lead_days: e.target.value })} />
          </label>
        </>
      ) : (
        <label>
          Hours before each interval
          <input type="number" min="0" max="336" step="1" value={value.horizon_hours}
            onChange={(e) => set({ horizon_hours: e.target.value })} />
        </label>
      )}
    </form>
  );
}
