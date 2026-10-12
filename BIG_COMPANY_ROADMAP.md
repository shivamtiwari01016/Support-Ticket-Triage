# Roadmap: Taking This Project to Big-Company Level

Goal: turn the Support Ticket Triage demo into a project you can defend in a senior/ML-engineering interview at a large company. Big companies do not score UI polish — they score **rigor, reproducibility, testing, deployment, security, and a clear tradeoff story.**

How to use this file: work top to bottom. Each task has **Why** (the interview point), **How** (concrete for this repo), and **Done when** (the bar). Phases 0–2 are non-negotiable; 3–6 are what separate "good portfolio" from "hired."

Legend: `[ ]` = todo.

---

## Phase 0 — Make it exist and run reproducibly (BLOCKER)

### 0.1 Create the missing Alembic migration folder
- Why: `alembic.ini` sets `script_location = migrations`, but the folder is missing. App startup in development (`api.py:117` → `upgrade_schema`) and `tests/test_database.py:49` both fail.
- How:
  ```powershell
  python -m alembic init migrations        # creates migrations/ (env.py, script.py.mako, versions/)
  # point migrations/env.py at the models metadata:
  #   from ticket_triage.models import Base
  #   target_metadata = Base.metadata
  #   (and set config.set_main_option("sqlalchemy.url", ...) from DATABASE_URL)
  python -m alembic revision --autogenerate -m "initial tickets and predictions"
  python -m alembic upgrade head
  ```
  Keep `alembic.ini` `script_location = migrations` and commit the `versions/` revision.
- Done when: `python -m pytest tests/test_database.py -q` passes and `python -c "from alembic...; ScriptDirectory...get_current_head()"` returns a revision (no `Path doesn't exist`).

### 0.2 Fix the data path
- Why: code/README read `data/raw/customer_support_tickets.csv` (`train.py:98`), but the CSV is at `dataset/customer_support_tickets.csv`.
- How: pick one canonical location and make everything agree.
  - Move to `data/raw/customer_support_tickets.csv` (matches `.gitignore` and README), or
  - Keep `dataset/` and update `train.py:98`, the README, and `data.py` references.
- Done when: `python -m ticket_triage.train` runs with no args.

### 0.3 Produce the model artifact
- Why: `config.py:19-20` and `api.py:81-89` require `models/ticket_triage.joblib` + `models/evaluation.json`.
- How: after 0.2, run training; confirm `models/` is created. Add a `make train` target.
- Done when: `GET /api/v1/health` returns `"model": "loaded"`.

### 0.4 Install and pin what's actually used
- Why: `.venv` doesn't match `requirements.txt` (e.g. SQLAlchemy 2.1.1 vs pinned 2.0.41) and `cryptography` is missing — PyMySQL needs it for MySQL 8 `caching_sha2_password`.
- How: adopt a lock workflow and stop hand-maintaining two sources of truth:
  ```powershell
  pip install uv
  uv pip install -r requirements.txt
  # or generate a lockfile:
  uv pip compile pyproject.toml -o requirements.lock
  ```
  Ensure `cryptography` is installed and importable.
- Done when: `python -c "import cryptography, sqlalchemy, sklearn; print('ok')"` and `requirements.lock` is committed.

### 0.5 One-command local run
- Why: "it runs in one command" is the first thing an interviewer tries.
- How: a `Makefile` / `justfile` (and later Docker):
  ```
  setup:   python -m pip install -r requirements.txt; python -m alembic upgrade head
  train:   python -m ticket_triage.train
  api:     python -m uvicorn ticket_triage.api:app --port 8000
  test:    python -m pytest -q
  lint:    python -m ruff check src tests
  ```
- Done when: `make setup && make train && make api` brings the API up cleanly.

---

## Phase 1 — ML rigor (this is where ML interviews are won/lost)

### 1.1 Replace the single split with stratified k-fold CV
- Why: one 80/20 split can't distinguish signal from luck; interviewers ask "how stable is this?"
- How: extend `train.py` to run `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`, report mean ± std for accuracy/F1 alongside the holdout, and keep `evaluation.json` as the deployment snapshot.
  ```python
  from sklearn.model_selection import cross_val_score, StratifiedKFold
  cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
  scores = cross_val_score(build_classifier(), texts, labels, cv=cv, scoring="f1_macro")
  ```
- Done when: `evaluation.json` contains `cv_macro_f1_mean`, `cv_macro_f1_std`, per-fold scores.

### 1.2 Kill leakage (dedupe + group-aware split)
- Why: the dataset is templated; random splits leak near-duplicates across train/test and inflate scores — or here, mask the real problem.
- How: normalize text, drop exact/near duplicates (e.g. hash of `clean_text`), and/or use `GroupKFold` grouped by a template signature. Document how many rows were dropped.
- Done when: README states duplicate handling and the split strategy with numbers.

### 1.3 Beat the baseline or explain it properly
- Why: accuracy 25.9% < 40% majority baseline is the first attack. Being below baseline is *acceptable* if you can prove you understand why and show a path to fix it.
- How:
  - Report **per-class** precision/recall/F1 and a confusion matrix (already computed in `train.py:79`).
  - Add an **ablation**: TF-IDF alone vs + noun-phrase features vs + NER features vs + urgency.
  - Try one stronger model (linear SVM or a small transformer / `setfit`) and report the delta. Keep Logistic Regression as the explainable default.
  - Add confidence/abstain: only route when `max(predict_proba) >= threshold`; otherwise mark "needs human review."
- Done when: a table in the README compares baseline / LR / stronger model with numbers and a one-line reason for the choice.

### 1.4 Evaluation confidence
- Why: point estimates without uncertainty look naive at senior level.
- How: add bootstrap confidence intervals for accuracy/F1; report class support.
- Done when: `evaluation.json` includes CI bounds (e.g. `accuracy_ci95`).

### 1.5 Experiment tracking
- Why: reproducibility and "how did you get here?"
- How: log params/metrics/artifacts with MLflow (local file store is fine) or a simple `experiments/<timestamp>.json`.
- Done when: each training run is recorded with params, metrics, git SHA.

---

## Phase 2 — Engineering quality: tests, lint, CI

### 2.1 Test coverage where it's missing
- Why: no frontend tests and skipped MySQL integration tests are the most visible gaps.
- How:
  - Backend: raise coverage on `api.py` (auth 401, pagination, rate limit), `services/`, `repositories/`. Add `pytest-cov` with a minimum threshold.
  - Frontend: add Vitest + React Testing Library for `api.js` (error mapping, normalization), `PredictionCard`, `TicketAnalyzer` flow.
  - Add one Playwright E2E: type a ticket → analyze → see prediction → open detail.
- Done when: `pytest --cov` ≥ 80% backend, frontend has a `test` script that passes, one E2E green.

### 2.2 CI that actually runs
- Why: a repo with no green CI reads as unfinished.
- How: `.github/workflows/ci.yml`:
  ```yaml
  name: ci
  on: [push, pull_request]
  jobs:
    backend:
      runs-on: ubuntu-latest
      services:
        mysql:
          image: mysql:8.4
          env:
            MYSQL_ROOT_PASSWORD: root
            MYSQL_DATABASE: support_ticket_triage_test
          ports: ["3306:3306"]
          options: >-
            --health-cmd="mysqladmin ping -proot"
            --health-interval=10s --health-timeout=5s --health-retries=5
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: "3.12" }
        - run: pip install -r requirements.txt
        - run: python -m alembic upgrade head
          env: { DATABASE_URL: "mysql+pymysql://root:root@127.0.0.1:3306/support_ticket_triage_test" }
        - run: python -m ruff check src tests
        - run: python -m pytest -q
          env:
            MYSQL_TEST_DATABASE_URL: "mysql+pymysql://root:root@127.0.0.1:3306/support_ticket_triage_test"
    frontend:
      runs-on: ubuntu-latest
      defaults: { run: { working-directory: frontend } }
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with: { node-version: "20" }
        - run: npm ci
        - run: npm run lint
        - run: npm test -- --run
        - run: npm run build
  ```
  Add Dependabot and CodeQL.
- Done when: a status badge is green on the README and the MySQL integration test runs (no longer skipped).

### 2.3 Containerize
- Why: reproducibility across machines; expected at big companies.
- How: `Dockerfile` (multi-stage: build deps → slim runtime), `docker-compose.yml` with `mysql`, `api`, `web`. Use `/health` as the healthcheck. Bake `en_core_web_sm` into the image at build time.
  ```yaml
  services:
    db:  { image: mysql:8.4, environment: [MYSQL_ROOT_PASSWORD=root, MYSQL_DATABASE=support_ticket_triage], ports: ["3306:3306"], healthcheck: { test: ["CMD","mysqladmin","ping","-proot"], interval: 10s } }
    api: { build: ., command: "uvicorn ticket_triage.api:app --host 0.0.0.0", environment: [DATABASE_URL=mysql+pymysql://root:root@db:3306/support_ticket_triage], depends_on: { db: { condition: service_healthy } }, ports: ["8000:8000"] }
    web: { build: ./frontend, ports: ["5173:80"] }
  ```
- Done when: `docker compose up` gives a working stack from a clean checkout.

### 2.4 Packaging and hygiene
- Why: small signs of care.
- How: `pre-commit install` (config exists), add `py.typed`, remove committed `frontend/dist/`, remove/ wire `frontend/.oxlintrc.json`, delete unused `src/assets/hero.png`.
- Done when: `pre-commit run --all-files` passes.

---

## Phase 3 — Security & privacy

### 3.1 Stop shipping a secret to the browser
- Why: `VITE_API_KEY` (`api.js:8`) is inlined into the public bundle.
- How: put the secret server-side — a BFF/reverse proxy that authenticates the SPA with a session cookie — or implement real user auth (OAuth2/OIDC/JWT via FastAPI).
- Done when: no secret in `frontend/dist`; the browser holds only a short-lived session.

### 3.2 Real auth on the API
- Why: `APIKeyHeader` is fine for a demo but not enterprise.
- How: add FastAPI OAuth2/JWT (`python-jose` + `passlib`), roles (operator/admin), and per-route scopes. Keep the API key only for machine-to-machine in dev.
- Done when: Swagger has a working `securitySchemes`, and 401/403 have tests.

### 3.3 Fix ticket privacy
- Why: `GET /tickets` returns everyone's ticket text.
- How: scope tickets to the authenticated user/tenant, anonymize/redact PII at ingest, or make the public demo read-only with seeded data.
- Done when: an anonymous/public user cannot read another's ticket.

### 3.4 Rate limiting + size caps
- Why: spaCy inference is expensive and DoS-able.
- How: `slowapi` (or a reverse-proxy limit) on `/predictions`, plus a max body size.
- Done when: a burst test returns 429 with a clear message.

### 3.5 Supply chain
- Why: big companies audit dependencies.
- How: `pip-audit` in CI, Dependabot alerts, pinned lockfile, base-image scanning (Trivy).
- Done when: CI fails on known high-severity CVEs.

---

## Phase 4 — Deployment & operations

### 4.1 Deploy it somewhere public
- Why: a live link in the README is worth 1000 words.
- How: any of Render / Fly.io / Railway / AWS ECS (+ RDS MySQL) / a small VPS. Serve the SPA static build behind Nginx with **SPA fallback** (rewrite unknown paths to `index.html`) and proxy `/api` to the API.
- Done when: `https://<your-demo>` loads, `/docs` works, and you can analyze a ticket.

### 4.2 Migrations at deploy time
- Why: dev auto-upgrade (`api.py:117`) must not run in prod.
- How: run `alembic upgrade head` as a release step / init job; keep `ENVIRONMENT=production` so the app refuses missing secrets (`config.py:26`).
- Done when: prod boot does not mutate schema and fails loudly if the revision is stale.

### 4.3 Observability
- Why: "how do you know it's healthy?"
- How: structured JSON logs with a request ID, Sentry for errors, a `/metrics` Prometheus endpoint + dashboards for latency/error rate/prediction distribution. Cache the health check (it re-reads migrations each call — `database.py:41-51`).
- Done when: you can demo a dashboard and trace one request end-to-end.

### 4.4 Performance
- Why: synchronous per-request spaCy is the bottleneck.
- How: batch inference, cache the loaded model, consider a task queue for heavy work, load-test with `locust`/`k6` and publish p50/p95/p99.
- Done when: README shows a latency/throughput table under load.

---

## Phase 5 — Product differentiators (what makes it memorable)

### 5.1 Deliver the explainability you advertise
- Why: the app says "explainable" but shows no explanation. This is the single best differentiator.
- How: expose per-class `predict_proba` and top contributing features (TF-IDF value × `classifier.coef_`), highlight those tokens in the ticket text. Add an endpoint `POST /api/v1/predictions?explain=true` or a dedicated `explanation` block.
- Done when: the UI shows confidence for all four categories + the words that drove the decision.

### 5.2 Confidence + abstain/human-in-the-loop
- Why: mature ML systems know when not to decide.
- How: below a confidence threshold, mark "needs review"; let an operator override; persist the override and original in `predictions`; surface override rate.
- Done when: dashboard shows "% of low-confidence predictions overridden."

### 5.3 Ticket detail + status workflow
- Why: completes the CRUD/workflow story.
- How: wire the unused `getTicket()` (`api.js:125`) into a `/tickets/:id` route; add `PATCH /tickets/{id}` for status; render prediction history.
- Done when: you can open a ticket, change status, and see history.

### 5.4 Model dashboard
- Why: shows you evaluate like an engineer.
- How: confusion-matrix heatmap, baseline-vs-model bar, ablation table, CV distribution, CI bounds — all from `evaluation.json`.
- Done when: the Model page renders real evaluation visuals.

### 5.5 Table UX + demo seed
- Why: empty dashboards look unfinished.
- How: search/filter/sort/cursor pagination; a `seed.py` to populate realistic tickets.
- Done when: the dashboard is populated on first load and the table is usable.

---

## Phase 6 — Presentation (the interview itself)

- `[ ]` README with: one-line pitch, architecture diagram, **screenshot/GIF**, metrics table (baseline vs model), setup in one command, limitations & next steps.
- `[ ]` A 3-minute demo video (Loom): problem → pipeline → explainability → one tradeoff decision.
- `[ ]` A short "Design decisions" doc (or ADRs) with the *why* behind TF-IDF + LR, MySQL, the urgency heuristic, and the label proxy caveat.
- `[ ]` Rehearse the top questions:
  - Why is accuracy below the baseline, and what would you change?
  - How do you handle class imbalance and leakage?
  - How would this scale to 1M tickets/day?
  - How do you monitor model drift in production?
  - What's your rollback plan for a bad model?

---

## Scorecard: where you are vs. target

| Area | Now | Big-company bar |
| --- | --- | --- |
| Runs end-to-end | No (no migrations, paths, artifact) | One command / `docker compose up` |
| Reproducibility | Drifting venv, no lockfile | Locked deps + container |
| ML evaluation | Single split, below baseline | k-fold CV, leakage control, CI, ablation |
| Tests | Backend partial, frontend none, MySQL skipped | Backend+frontend+E2E, coverage gate |
| CI/CD | None | Lint+test+build+audit green |
| Security | Key in bundle, open ticket list | Real auth, scoped data, rate limits |
| Deployment | Local only | Public URL + migrations in release |
| Observability | Logs only | Metrics, tracing, alerting |
| Explainability | Claimed, not shown | probabilities + term contributions in UI |

---

## Suggested order (first two weeks)

1. Phase 0 (0.1–0.5) — get it running and locked. **This unblocks everything.**
2. Phase 1.1–1.3 — CV, dedupe, honest baseline comparison.
3. Phase 2.2–2.3 — CI + `docker compose up`.
4. Phase 5.1–5.2 — explainability + confidence (the differentiator).
5. Phase 3.1–3.3 — security/privacy.
6. Phase 4.1 — public deploy.
7. Phase 6 — package the story.

If you can walk an interviewer through Phases 0–2 and 5.1, you are already above most candidates.
