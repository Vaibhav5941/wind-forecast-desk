# Wind Forecast Desk

Wind Forecast Desk is a small data analysis app for comparing Great Britain’s national wind generation forecasts with actual generation for January 2026.

It uses data from Elexon and is intended for a UK energy trading or procurement team that needs to understand what a forecast looked like before a day-ahead purchase decision.

The app focuses on three questions:

- What was the latest forecast available at the decision cutoff?
- How different was that forecast from actual wind generation?
- Which delivery intervals had the largest errors, and are there any data-quality issues worth investigating?

This is an analysis tool only. It does not recommend purchases or model electricity prices or demand.

## Current status

| Area | Status |
|---|---|
| Backend and frontend | Built and tested locally |
| Backend tests | 66 passed |
| Frontend tests | 6 passed |
| Lint and production build | Passed |
| Live Elexon integration | Not yet verified |
| Docker image | Configuration checked; image not built or run |
| Deployment | Not deployed |
| GitHub repository | Not published |
| Demo video | Not recorded |

**Important:** The live Elexon API integration still needs to be checked. The development environment could not reach `bmrs.elexon.co.uk` because of a proxy 403 response. The API endpoints and field names used in the code are based on the author's understanding of the API and should not be treated as confirmed.

When live data cannot be loaded and no snapshot is available, the app falls back to synthetic test data. These results are labelled as non-authoritative in the UI and API. Synthetic figures must not be quoted as real Elexon results.

## Features

- Compare forecast and actual wind generation by delivery interval.
- Select a forecast using its publication time and a configurable decision cutoff.
- Review forecast errors, daily summaries and aggregate accuracy metrics.
- Switch between day-ahead and fixed-lead-time analysis.
- Inspect forecast vintages to see which forecasts were available at different times.
- Check coverage, missing values, duplicate records and conflicting duplicates.
- View missing intervals and identify periods that need further investigation.
- Use a local snapshot to avoid fetching the same data every time the UI changes.

## Tech stack

- **Frontend:** React, Vite and Vitest
- **Backend:** Python, FastAPI and pytest
- **Data handling:** Pandas-style time-series analysis and validation
- **Data source:** Elexon FUELHH and WINDFOR streams
- **Deployment setup:** Docker, Docker Compose and a prepared Render Blueprint

## Getting started

### Option 1: Run with Docker

From the project root, copy the example environment file if needed and start the services:

```bash
cp .env.example .env
docker compose up --build
```

Open the frontend at [http://localhost:5173](http://localhost:5173). The API runs on port `8000`.

Docker has not yet been used to build and run this project in the original development environment, so this setup still needs an end-to-end check.

### Option 2: Run without Docker

Open two terminals from the project root.

**Terminal 1 — Backend**

```bash
cd backend
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite development server proxies `/api` requests to the backend.

If you only need to fetch an Elexon snapshot, install the backend requirements and run the CLI command described below.

## Working with the data

### Fetching a snapshot

On a machine that can reach the Elexon API, run:

```bash
cd backend
pip install -r requirements.txt
python -m app.cli fetch
```

The expected output file is:

```text
data/snapshots/elexon_wind_2026-01.json.gz
```

The live request and response schema have not yet been verified. If the fetch fails, check the endpoint configuration and query parameter names before relying on the returned data.

### First live-data check

Before using the results for analysis, verify the following:

1. Run `python -m app.cli fetch` and confirm that records are returned.
2. Check the request parameters for the selected Elexon streams. Depending on the endpoint, date parameters may use names such as `from` and `to`, or `settlementDateFrom` and `settlementDateTo`.
3. Inspect the returned records and confirm the timestamp and generation field names.
4. Confirm that generation values represent MW and that the timestamps have the expected meaning.
5. Check how far back the WINDFOR forecast vintages are available for January delivery intervals.
6. Review the data-quality panel for coverage, null values, duplicates and conflicting records.

The configurable `FORECAST_LOOKBACK_DAYS` setting controls how far before delivery the forecast publication window begins.

## How forecast selection works

For each delivery interval, the app selects the latest forecast whose publication timestamp is at or before the decision cutoff:

`publishTime <= cutoff`

Forecasts published after the cutoff are excluded. If no eligible forecast exists for an interval, that interval is marked as missing rather than being filled with a later forecast.

The default decision cutoff is **09:00 Europe/London on the day before delivery**. This is an assumption for the analysis, not a confirmed operational rule from Elexon or the intended trading team.

The cutoff can be configured through the environment settings or the UI. The app also supports a fixed-lead-time mode, such as 24 hours before each delivery interval, and provides a vintages view for inspecting earlier forecasts.

A later cutoff may produce different accuracy results because more recent forecasts become available. Comparisons should therefore use a clearly stated cutoff.

## Metrics

All generation and error metrics are expressed in MW and calculated only from matched, valid forecast/actual pairs.

The error convention is:

`error = forecast - actual`

A positive error means generation was over-forecast; a negative error means it was under-forecast.

| Metric | Meaning |
|---|---|
| MAE | Average absolute forecast error |
| RMSE | Root mean squared error; larger errors have more influence |
| Mean bias | Average signed error |
| nMAE | MAE divided by the mean actual generation for the same matched pairs |

The app also reports the sample size and coverage, calculated as matched intervals divided by the expected number of half-hour intervals.

Results are marked as non-authoritative when synthetic data is used, no valid pairs are available, or coverage falls below the configured 95% threshold.

## Data quality and limitations

The analysis applies the following checks:

- Null, negative, non-numeric, non-finite and implausibly high generation values above 60 GW are excluded and counted. Zero generation is allowed.
- Unparseable timestamps and intervals that do not align with the expected settlement periods are rejected.
- Duplicate records are handled during cleaning. Actual duplicates use the latest publication time where available, and conflicting duplicates are flagged.
- Missing intervals are reported as contiguous ranges.
- Delivery days follow the Europe/London calendar. The code handles daylight-saving days with 46 or 50 half-hour intervals; January 2026 has 48 intervals per day.

There are also some important limitations:

- Live Elexon endpoints, parameters and response fields still need verification.
- The default decision cutoff is an assumption.
- The analysis covers national wind generation only and only January 2026.
- The app does not use electricity prices, demand or procurement decisions.
- Timestamps are displayed in UTC.
- Data is loaded into memory for each running process.
- Saved snapshots are not refreshed automatically.
- The app does not require Elexon authentication in its current design.

## API endpoints

The FastAPI backend exposes the following routes:

```text
GET /api/health
GET /api/config
GET /api/summary
GET /api/series
GET /api/metrics
GET /api/quality
GET /api/actuals
GET /api/forecasts
GET /api/vintages?target=...
```

Common query parameters include `start`, `end`, `mode`, `cutoff_time`, `lead_days` and `horizon_hours`.

Date filters are limited to January 2026. Invalid parameters return HTTP 422, upstream errors can return 502, and unavailable or unusable datasets can return 503.

FastAPI's interactive API documentation is available at `/docs` when the backend is running.

## Project structure

```text
backend/
  app/
    config.py       # Environment-based settings
    elexon.py       # HTTP client, retries and request chunking
    cleaning.py     # Validation and duplicate handling
    store.py        # Dataset and snapshot loading
    vintage.py      # Cutoff rules and forecast selection
    analysis.py     # Matching, metrics and daily summaries
    service.py      # Analysis service and parameter validation
    main.py         # FastAPI routes
    synthetic.py    # Clearly labelled development fixtures
    cli.py          # Fetch and info commands
  tests/            # Backend tests

frontend/
  src/              # React interface and frontend tests

data/
  snapshots/        # Saved data snapshots

docs/
  VIDEO_PLAN.md     # Demo video outline

Dockerfile
docker-compose.yml
render.yaml
```

## Tests and checks

Run the backend tests:

```bash
cd backend
python -m pytest -q
```

Run the frontend tests:

```bash
cd frontend
npm test
```

Check Python formatting and lint:

```bash
cd backend
ruff check .
ruff format --check .
```

Check the frontend:

```bash
cd frontend
npm run lint
npm run build
```

The reported backend test suite covers forecast vintage selection, cutoff boundaries, daylight-saving handling, interval matching, duplicates, invalid values, metric calculations, empty datasets, API validation, upstream failures and synthetic fallback behaviour.

The frontend tests cover the non-authoritative banner, error-sign display and control switching. Browser end-to-end tests have not been added.

These are the results recorded during development; rerun the commands against the current checkout to confirm them.

## Deployment

A `Dockerfile` and `render.yaml` are included, but the application has not been deployed and no public URL is available yet.

The intended deployment process is:

1. Push the project to a GitHub repository.
2. Create a Render Blueprint from that repository, using `render.yaml`, or deploy the Docker image on another compatible host.
3. Configure the environment variables and verify the `/api/health` endpoint.
4. Test the application using a known snapshot before relying on the results.

A saved snapshot can make the deployment less dependent on live Elexon requests. Before committing one to a public repository, check the applicable data-use terms.

If the frontend is hosted separately, configure `VITE_API_BASE` at build time and set the appropriate `CORS_ORIGINS` value on the backend.

## Development notes

The application was developed with assistance from Claude Code, which helped generate the backend, frontend, tests, container configuration and documentation.

The implementation and assumptions still need to be reviewed, particularly the live Elexon integration and the default forecast cutoff. The test results confirm the behaviour covered by the tests; they do not establish that the live data integration is correct.
