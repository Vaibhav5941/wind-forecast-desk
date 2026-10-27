.PHONY: test lint build fetch
test:
	cd backend && python -m pytest -q
	cd frontend && npm test
lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npm run lint
build:
	cd frontend && npm run build
fetch:
	cd backend && python -m app.cli fetch
