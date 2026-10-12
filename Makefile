PYTHON ?= python

.PHONY: setup train api test lint frontend-dev frontend-build

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m alembic upgrade head

train:
	$(PYTHON) -m ticket_triage.train

api:
	$(PYTHON) -m uvicorn ticket_triage.api:app --host 127.0.0.1 --port 8000

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src tests

frontend-dev:
	cd frontend && npm install && npm run dev -- --host 127.0.0.1 --port 5173

frontend-build:
	cd frontend && npm install && npm run build
