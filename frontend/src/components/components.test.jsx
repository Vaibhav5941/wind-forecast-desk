import { render, screen, fireEvent } from "@testing-library/react";
import Banner from "./Banner.jsx";
import MetricCards from "./MetricCards.jsx";
import Controls from "./Controls.jsx";

const metrics = { n: 10, expected_intervals: 20, coverage: 0.5, mae_mw: 100, rmse_mw: 130, bias_mw: -25, nmae_pct: 4.2 };

test("non-authoritative results show a prominent warning with reasons", () => {
  render(<Banner metrics={{ authoritative: false, not_authoritative_reasons: ["Data are synthetic development fixtures, not Elexon data."] }} quality={{ data_source: "synthetic", notes: [] }} />);
  expect(screen.getByRole("alert")).toHaveTextContent(/Not authoritative/);
  expect(screen.getByRole("alert")).toHaveTextContent(/synthetic/i);
});

test("metric cards show bias with its sign and the sample size", () => {
  render(<MetricCards metrics={metrics} />);
  expect(screen.getByText("−25 MW")).toBeInTheDocument();
  expect(screen.getByText(/10 \/ 20/)).toBeInTheDocument();
  expect(screen.getAllByText(/forecast − actual/).length).toBeGreaterThan(0);
});

test("switching to fixed lead time swaps the cutoff inputs", () => {
  const cfg = { period_start: "2026-01-01", period_end: "2026-01-31", timezone: "Europe/London" };
  let val = { start: "2026-01-01", end: "2026-01-31", mode: "day_ahead", cutoff_time: "09:00", lead_days: 1, horizon_hours: 24 };
  const onChange = vi.fn((v) => { val = v; });
  const { rerender } = render(<Controls config={cfg} value={val} onChange={onChange} />);
  expect(screen.getByLabelText(/Cutoff time/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Forecast selection"), { target: { value: "horizon" } });
  expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ mode: "horizon" }));
  rerender(<Controls config={cfg} value={val} onChange={onChange} />);
  expect(screen.getByLabelText(/Hours before each interval/)).toBeInTheDocument();
  expect(screen.queryByLabelText(/Cutoff time/)).toBeNull();
});
