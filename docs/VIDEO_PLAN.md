# Video plan (max 10 min, record as two parts)

I could not record or upload a video. This is a script outline to rehearse and say **in your own words**.
Only claim what you have seen on screen. If you run on live data, say so; if on synthetic data, say so.

## Before recording
- [ ] Decide the data source. Best: run `make fetch` (or `python -m app.cli fetch`) on a machine that can reach Elexon, so the app shows **cached real data**. If the fetch fails or returns odd fields, say that honestly.
- [ ] `docker compose up --build`, open http://localhost:5173, check the banner shows the source you expect.
- [ ] Close notifications, set browser zoom to 100–110%, 1080p, record with OBS / QuickTime / Loom.
- [ ] Have these open: browser, VS Code at the repo root, a terminal.

## Part 1 – Customer presentation (≤ 5:00)
| Time | Say / show |
|---|---|
| 0:00–0:45 | **The problem.** A UK supplier buys day-ahead power; wind is weather-driven, so the wind forecast sets how much other power it may need. The question is not "what is the best forecast" but "what forecast did we have *at decision time* and how good was it". |
| 0:45–1:45 | **Dashboard.** Point to: data-source banner, period summary, selection rule ("09:00 London, day before – an assumption"), latest forecast publish time used, coverage. |
| 1:45–2:45 | **Actual vs forecast chart.** Hover an interval: actual, forecast, error (forecast − actual), publish time, cutoff. Tick "Show error". Change the date range to a few days. |
| 2:45–3:45 | **Accuracy.** MAE, RMSE, bias (explain sign: + = over-forecast), sample size and coverage. Daily table: pick the worst day. Largest-errors table → click **Vintages** to show later forecasts that were *excluded*. |
| 3:45–4:30 | **How a buyer might use it.** Judge how much headroom to hold on high-error days; check whether bias is systematic; look at recent big misses before relying on a forecast. |
| 4:30–5:00 | **Limits (be explicit).** Cutoff is assumed; national-level only; one month; it does not optimise procurement or know prices/demand; metrics are only as complete as the coverage shown. |

## Part 2 – Technical walkthrough (≤ 5:00)
| Time | Say / show |
|---|---|
| 0:00–0:45 | **Architecture.** React (Vite) → `/api` → FastAPI → in-memory dataset built from Elexon (cached snapshot). Why FastAPI: typed params, auto docs at `/docs`, easy test client. Show repo tree. |
| 0:45–1:30 | **Data flow.** `elexon.py` (retries, chunking) → `cleaning.py` (null/invalid/duplicate counted, never zero-filled) → `store.py` (snapshot, provenance) → `vintage.py` → `analysis.py` → `service.py` → `main.py`. |
| 1:30–2:45 | **Vintage selection.** Open `vintage.py`: `select_vintage` uses `bisect_right` on publish times (cutoff inclusive). `DayAheadCutoff` converts London wall-clock to UTC. Show `tests/test_vintage.py` late-forecast test. |
| 2:45–3:30 | **Metrics.** `analysis.py`: error = forecast − actual, join on interval start, only matched pairs. Show the bias-sign test and the DST test (46/50-interval days). |
| 3:30–4:10 | **Run it.** Terminal: `docker compose up --build`; in another: `cd backend && pytest -q` and `cd frontend && npm test`. Read the real output. |
| 4:10–5:00 | **Assumptions, limits, next steps.** Unverified Elexon parameter names (say whether you verified them), cutoff assumption, no auth, single process cache. Next: verify live schema, confirm cutoff with a trader, add per-horizon accuracy, regional/offshore split if allowed. |

## Upload checklist
- [ ] Export MP4, trim to ≤ 10:00 total.
- [ ] YouTube Studio → Create → Upload → **Visibility: Unlisted**.
- [ ] Title without your name if anonymity is required; open the link in a private window to confirm it plays.
- [ ] Paste the URL into the README (`Demo video` line) – only after it exists.

## Questions to be ready for
- Why that cutoff? (Assumption, configurable; show the effect by changing it.)
- Why not use the latest forecast? (Hindsight – not available at decision time.)
- What does RMSE add over MAE? (Penalises large misses.)
- What happens with missing data? (Excluded and counted; coverage shown.)
