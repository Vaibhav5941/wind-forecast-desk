# Progress

## Done
- FastAPI backend (cleaning, vintage selection, matching, metrics, snapshot/synthetic store, API)
- React/Vite UI (controls, banner, metrics, chart, daily + top-error tables, data transparency, vintage dialog)
- Tests: backend 66, frontend 6 (see README for the exact commands)
- Dockerfile (single image), docker-compose.yml (dev), render.yaml, .env.example, Makefile
- README, docs/VIDEO_PLAN.md

## Not done / needs the author
1. **Live Elexon verification** – the sandbox could not reach Elexon. Run `python -m app.cli fetch` where it can, confirm parameter/field names, commit the snapshot.
2. **Docker images** not built or run (no daemon in the sandbox). Run `docker compose up --build`.
3. **Cutoff assumption** (09:00 London, previous day) – confirm or change.
4. GitHub push, deployment, video recording/upload.

## Next steps
Fetch snapshot -> run app -> check coverage/quality panel -> record video -> push -> deploy.
