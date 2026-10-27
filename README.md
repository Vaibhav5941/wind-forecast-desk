# Wind Forecast Desk

A small analysis portal for exploring **GB national wind forecasts vs actuals (January 2026)** from Elexon, built for a UK energy trading/procurement team that buys on the day-ahead market. It answers three questions:

1. What wind forecast was available when the purchase decision had to be made?
2. How far off was it compared with actual wind generation?
3. Where and when were the errors largest, and what should be checked before relying on it?

It is an **analysis tool**. It does not optimise procurement and knows nothing about prices or demand.

## Status – read this first

| Item | State |
|---|---|
| Backend + frontend | Built and run locally; screenshot-checked in a browser |
| Backend tests | 66 passed (pytest) |
| Frontend tests / lint / build | 6 passed (vitest) · ESLint clean · `vite build` OK |
| **Live Elexon data** | **NOT verified.** The build environment could not reach `bmrs.elexon.co.uk` (proxy 403) and the docs pages could not be fetched. Endpoint paths, query parameter names and field names follow the author's understanding of the Insights API. **Check them on first live run** (see "First live run"). |
| Data shown when run offline | **Synthetic fixtures**, clearly labelled in the UI and API. No figures from this repo should be quoted as real Elexon results. |
| Docker | Config written and `docker compose config` validates. **Images were not built or run** (no Docker daemon in the build environment). |
| Deployment | **Not deployed.** `render.yaml` and steps below are prepared. No public URL exists. |
| GitHub | Not pushed. No repository URL exists yet. |
| Demo video | Not recorded. See `docs/VIDEO_PLAN.md`. |

## Quick start

```bash
cp .env.example .env            # optional; defaults work
docker compose up --build       # API :8000, UI :5173
# open http://localhost:5173
```

With no snapshot and no network access to Elexon, `DATA_MODE=auto` falls back to **synthetic** data and the UI shows a "Not authoritative" banner. To use real data, fetch a snapshot from a machine that can reach Elexon:

```bash
cd backend && pip install -r requirements.txt
python -m app.cli fetch         # writes data/snapshots/elexon_wind_2026-01.json.gz
```

Without Docker:

```bash
cd backend && pip install -r requirements-dev.txt && uvicorn app.main:app --reload     # :8000
cd frontend && npm install && npm run dev                                              # :5173, proxies /api
```

### First live run (what to verify)
1. `python -m app.cli fetch` – does it return rows? If the API rejects the parameters, adjust `ELEXON_FROM_PARAM` / `ELEXON_TO_PARAM` (e.g. `from`/`to`, or `settlementDateFrom`/`settlementDateTo` for FUELHH) in `.env`.
2. Open the snapshot and confirm field names (`startTime`, `publishTime`, `generation`, `fuelType`) and that `generation` is MW.
3. Check how far back WINDFOR vintages go for January delivery days. `FORECAST_LOOKBACK_DAYS` (default 7) controls how early the publish window starts.
4. Check the data-transparency panel: coverage, nulls, duplicates, conflicting duplicates.

## Tests

```bash
cd backend && python -m pytest -q      # 66 tests
cd frontend && npm test                # 6 tests
cd backend && ruff check . && ruff format --check .
cd frontend && npm run lint && npm run build
```

Backend tests cover: vintage selection by publish time, exclusion of late forecasts (inclusive cutoff), DST-aware cutoffs, matching by interval, duplicates (exact and conflicting), null/invalid values, metrics on valid matched pairs only, bias sign, empty datasets, parameter validation (422), upstream errors/retries (502/503), synthetic fallback and snapshot handling, and the API responses. Frontend tests cover the non-authoritative banner, sign display, and control switching. There are no browser end-to-end tests in the repo.

## Architecture

```
React (Vite)  --/api-->  FastAPI  -->  in-memory Dataset  <--  snapshot (.json.gz) <-- Elexon (FUELHH, WINDFOR)
```

- **FastAPI** over Flask: declared/validated query parameters, automatic `/docs`, simple test client.
- The dataset is loaded once (snapshot → else live fetch + snapshot → else labelled synthetic) and held in memory, so chart redraws and filter changes never call Elexon.
- Actuals and forecasts are separate types and are only joined in `analysis.build_rows` on delivery-interval start.

```
backend/app/
  config.py    env-driven settings          elexon.py   HTTP client (retry, chunking)
  cleaning.py  validation, de-duplication   store.py    snapshot / live / synthetic loading
  vintage.py   cutoff rules, vintage pick   analysis.py matching, metrics, daily, narrative
  service.py   param validation, one run    main.py     FastAPI routes (+ optional static serving)
  synthetic.py labelled dev fixtures        cli.py      `fetch` / `info`
backend/tests/   pytest suite               frontend/src/   React UI + vitest tests
Dockerfile (single image, deployment)  docker-compose.yml (dev)  render.yaml
```

### API
`GET /api/health · /api/config · /api/summary · /api/series · /api/metrics · /api/quality · /api/actuals · /api/forecasts · /api/vintages?target=…`
Common query parameters: `start`, `end` (YYYY-MM-DD, within January 2026), `mode=day_ahead|horizon`, `cutoff_time=HH:MM`, `lead_days=0..7`, `horizon_hours`. Invalid values return 422; upstream failures 502; no usable data 503.

## Data sources and assumptions

- **Actuals:** Elexon `FUELHH` stream, records with `fuelType = WIND`; fields `startTime`, `generation`. 
- **Forecasts:** Elexon `WINDFOR` stream; fields `startTime`, `publishTime`, `generation`.
- Treated as MW per half-hour settlement period; timestamps ISO-8601, normalised to UTC (naive values are assumed UTC and counted). **Unverified – see status table.**
- Only these two national series are used.

## Forecast vintage and decision cutoff

For each delivery interval the app uses the **latest forecast with `publishTime ≤ cutoff`** (inclusive). Forecasts published later are excluded and counted. If none exists, the interval is "missing forecast" – never filled.

**Assumed cutoff: 09:00 Europe/London on the day before delivery** (so all intervals of a delivery day share one cutoff). This is an **assumption**: the assignment does not give the operational cutoff and I could not confirm one from documentation. It is configurable (`CUTOFF_TIME`, `CUTOFF_LEAD_DAYS`, or in the UI). A later cutoff can only add newer forecasts, which usually look more accurate; an earlier one the reverse. A second mode, **fixed lead time** (e.g. 24 h before each interval), and the **Vintages** dialog let users inspect earlier forecasts.

## Metrics (all in MW, matched valid pairs only)

`error = forecast − actual` (positive = over-forecast).
**MAE** = mean(|error|) · **RMSE** = √mean(error²) · **Mean bias** = mean(error) · **nMAE** = MAE ÷ mean(actual) over the same pairs (undefined if mean actual is 0).
Sample size and coverage (`matched ÷ expected half-hours`) are shown beside the metrics. Results are flagged **not authoritative** when data are synthetic, there are no matched pairs, or coverage is below 95 % (`MIN_AUTHORITATIVE_COVERAGE`).

## Data-quality handling and limitations

- Null, negative, non-numeric, NaN/inf or > 60 GW generation values are excluded and counted – never set to zero. Zero is accepted as valid.
- Misaligned or unparseable timestamps are rejected; duplicates are collapsed (actuals: latest `publishTime` wins) and conflicting duplicates are flagged.
- Delivery days are London local days; DST days have 46/50 intervals (tested). January has none.
- Missing intervals are listed as contiguous ranges.
- Limitations: unverified live schema; assumed cutoff; national level only; one month; no authentication; in-memory cache per process; times shown in UTC; a snapshot is not refreshed automatically.

## Deployment (prepared, not done)

The root `Dockerfile` builds the UI and serves it with the API from one container (same origin, so no CORS setup). Commit a snapshot in `data/snapshots/` (public Elexon data – check licence terms) so the deployed app does not depend on live calls.
1. Push to a public GitHub repo with an anonymous name (`git init`, commit, `gh repo create <name> --public --source . --push`).
2. Render → New → Blueprint → select the repo (uses `render.yaml`), or any Docker host. Health check: `/api/health`.
3. If hosting the UI separately (e.g. Vercel), set `VITE_API_BASE` at build time and add the UI origin to `CORS_ORIGINS` on the API.
Public URL: **none yet.**

## AI assistance
Built with Claude (Anthropic) via Claude Code: it wrote the backend, frontend, tests, Docker and documentation from the brief, ran the tests/lint/build reported above, and drafted the video plan. The author must review the assumptions (especially the cutoff and Elexon parameters) and present the work in their own words.
