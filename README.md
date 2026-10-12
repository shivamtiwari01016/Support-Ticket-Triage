# Support Ticket Triage and Auto-Categorization

An explainable NLP baseline that classifies a support ticket as Billing, Technical Support, Account, or General, then derives a separate urgency score from sentiment. The category model is TF-IDF plus class-weighted Logistic Regression; the API is FastAPI and the frontend is a React dashboard for local demo usage.

## Project overview

This repository demonstrates an end-to-end support ticket triage workflow with:

- a trained NLP classifier for category prediction
- a VADER-based urgency heuristic
- a FastAPI backend with persistence in MySQL
- a React frontend for analyzing tickets and reviewing recent history
- a model evaluation artifact and supporting project documentation

## Documentation

- [Engineering roadmap](BIG_COMPANY_ROADMAP.md)
- [UI issues and interview notes](UI_ISSUES_AND_INTERVIEW_POINTS.md)

## Dataset and EDA

The project uses the Kaggle [Customer Support Ticket Dataset](https://www.kaggle.com/datasets/suraj520/customer-support-ticket-dataset). The CSV is stored at `dataset/customer_support_tickets.csv` and is used for model training and evaluation.

The checked CSV export contains 8,469 rows and 17 columns. It has five `Ticket Type` labels, not native support queues. The mapping used here is explicit: Billing inquiry and Refund request become Billing; Technical issue becomes Technical Support; Cancellation request becomes Account; Product inquiry becomes General. This produces counts of Billing 3,386, Technical Support 1,747, Account 1,695, and General 1,641. These are inferred training labels, not ground-truth queue assignments. The supplied `Ticket Priority` is examined in EDA but is not used as a target for the sentiment heuristic.

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

Create a local environment file from [.env.example](.env.example) and update your database credentials before starting the app.

The training CSV is included in `dataset/`. The trained model artifact is generated locally and ignored by Git.

## Database Setup

MySQL stores runtime tickets and prediction history only. It does not replace the Kaggle CSV and does not store the trained classifier. The training path remains `CSV -> model artifact`; runtime is `ticket -> FastAPI inference -> MySQL -> response`. The app does not bulk-import the Kaggle rows.

Important security note:
- default CORS is locked to the local Vite origins
- protected API routes require an API key by default
- keep `.env` local and never commit credentials

1. Install and start MySQL 8 or newer.
2. Create the application database:

```sql
CREATE DATABASE support_ticket_triage CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

3. Copy `.env.example` to `.env` and set the local MySQL credentials in `DATABASE_URL`. Keep the password out of source control; URL-encode reserved characters in it. `MODEL_DIR` defaults to `models`, `SPACY_MODEL` to `en_core_web_sm`, and `MODEL_VERSION` to `v1`.
4. Install runtime dependencies with `python -m pip install -r requirements.txt`, or development tools with `python -m pip install -e ".[dev]"`.
5. Train the model if `models/ticket_triage.joblib` is not present. Development startup applies checked-in Alembic revisions automatically. For `ENVIRONMENT=testing` or `production`, run `python -m alembic upgrade head` before starting FastAPI. Startup verifies MySQL, schema revision, model artifact, spaCy and VADER; it fails visibly if a dependency is unavailable and never falls back to SQLite.

Each ticket has an internal auto-incrementing `id` for database relationships and a separate generated `ticket_id` (for example `TKT-...`) for API responses and display. Each inference is a child row in `predictions`, linked by a foreign key, so later re-runs can retain prediction history. One transaction writes the ticket and its first prediction; a failure rolls both back.

This is a coursework/demo database. Ticket text can contain sensitive customer information; do not populate it with confidential or production customer data.

## Train and Evaluate

```powershell
python -m ticket_triage.train
```

Training defaults to `dataset/customer_support_tickets.csv`, uses an 80/20 stratified train/test split with a fixed random seed, and writes `models/ticket_triage.joblib` plus `models/evaluation.json`. The evaluation includes accuracy, weighted and macro precision/recall/F1, per-category scores, a confusion matrix, and a majority-class baseline. Logistic Regression uses `class_weight="balanced"`; stratification preserves each class's share in both partitions.

On this data with `random_state=42`, the measured holdout accuracy is 27.3% and macro F1 is 26.2%, versus a 40.0% majority-class accuracy baseline. The learned text signal is not reliable enough for automatic routing. This is consistent with the export's `Ticket Type` labels being proxies rather than the requested queue labels; use the API as a demonstration only, and replace these proxy labels with human-verified routing outcomes before relying on predictions.

## Run the API

Start after training:

```powershell
python -m uvicorn ticket_triage.api:app --host 127.0.0.1 --port 8000
```

The API requires the configured MySQL database and trained model. It allows only the local Vite origins listed in `TICKET_TRIAGE_CORS_ORIGINS`. Protected routes use an optional demo API key when `TICKET_TRIAGE_API_KEY` is set; in development it is safe to leave unset unless you want a gateway check. Send `POST /api/v1/predictions`:

```powershell
$body = @{ text = "I was charged twice and need help resolving this billing issue." } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/predictions -Method Post -ContentType "application/json" -Body $body
```

Response shape:

```json
{
  "ticket_id": "TKT-8F29A1B4C203",
  "text": "I was charged twice and need help resolving this billing issue.",
  "status": "open",
  "category": "General",
  "assigned_team": "Customer Support",
  "urgency": 0.79,
  "urgency_level": "High",
  "created_at": "2026-09-28T10:30:00"
}
```

This illustrates the response shape; ticket IDs and prediction values are generated at runtime. `assigned_team` follows a deterministic category-to-team mapping and is not an ML output. This dataset's evaluation is below its majority baseline, so predictions require operator review. Urgency is returned on a 0–1 scale. The OpenAPI UI is at `http://127.0.0.1:8000/docs`.

Available runtime and model endpoints:

- `GET /api/v1/health`: reports API, MySQL, model and NLP readiness; returns 503 if MySQL is unavailable.
- `POST /api/v1/predictions`: infer, assign a team, then save the ticket and prediction in one transaction.
- `GET /api/v1/tickets?limit=20`: recent saved tickets, with `limit` constrained to 1–100.
- `GET /api/v1/tickets/{ticket_id}`: one saved ticket, or 404.
- `GET /api/v1/statistics`: database-derived ticket count, mean urgency and category counts.
- `GET /api/v1/metrics`: actual weighted/macro holdout metrics read from `models/evaluation.json`; it is not computed from live tickets.

Unversioned `/health`, `/predict`, `/tickets`, `/statistics`, and `/metrics` routes remain hidden compatibility aliases. New clients should use `/api/v1`.

## Continuous Integration

CI provisions an isolated MySQL 8 service, applies Alembic migrations, runs the backend test suite, and builds the frontend. The optional local MySQL test requires `MYSQL_TEST_DATABASE_URL` to point to a dedicated loopback database whose name ends in `_test`; it is skipped otherwise.

Dependency update checks are configured in [.github/dependabot.yml](.github/dependabot.yml), and local hooks are configured in [.pre-commit-config.yaml](.pre-commit-config.yaml).

## Pipeline and Design Rationale

1. `data.py` combines the subject and description and normalizes the target labels. Customer names, emails, and unrelated columns are not model inputs.
2. `preprocessing.py` removes URLs and email addresses, non-ASCII artifacts, punctuation, standalone numbers, and repeated whitespace. spaCy tokenization is followed by ASCII/Latin-script validation, English stop-word removal, and lemmatization. Lemmatization returns readable vocabulary forms (for example, `charged` to `charge`) rather than chopping words into less interpretable stems.
3. The spaCy English model supplies POS tags and noun chunks. Noun phrases are emitted as explicit features. spaCy NER extracts DATE, MONEY, and ORG entities from the original text before numeric cleanup; the classifier uses entity-type markers so dates/amounts are not lost as a signal and organization names do not create a large, sparse vocabulary.
4. `TfidfVectorizer` weights terms by their importance in a ticket relative to the corpus. It uses unigrams and bigrams, allowing phrases such as `billing issue` to contribute alongside individual words. TF-IDF is sparse and inspectable, unlike dense transformer representations.
5. Logistic Regression learns weighted category evidence from those features. Its class coefficients and probabilities are inspectable, and `class_weight="balanced"` reduces the effect of the mapped class-count differences without hiding them.
6. Urgency is separate from the classifier. VADER returns compound sentiment in [-1, 1]; the score is `round((1 - compound) * 50)`, so more negative text yields higher urgency. Scores 70-100 are High, 45-69 Medium, and 0-44 Low. This is a transparent baseline heuristic, not a trained priority prediction or a calibrated SLA estimate.

## Project Layout

- `src/ticket_triage/data.py`: CSV schema handling and category mapping
- `src/ticket_triage/preprocessing.py`: cleaning, script validation, lemmatization, noun phrases, and NER
- `src/ticket_triage/model.py`: TF-IDF and Logistic Regression pipeline
- `src/ticket_triage/train.py`: stratified training, evaluation, and serialization
- `src/ticket_triage/urgency.py`: VADER urgency scoring
- `src/ticket_triage/api.py`: FastAPI endpoints
- `src/ticket_triage/database.py`: MySQL engine and request-scoped sessions
- `src/ticket_triage/models.py`: relational ticket and prediction tables
- `src/ticket_triage/schemas.py`: Pydantic API contracts
- `src/ticket_triage/repositories/ticket_repository.py`: transactional persistence and database aggregates
- `src/ticket_triage/services/prediction_service.py`: inference, urgency, routing and persistence workflow
- `src/ticket_triage/services/ticket_service.py`: ticket response mapping and read workflows
- `src/ticket_triage/services/routing_service.py`: deterministic category-to-team mapping
- `src/ticket_triage/config.py`: `.env` configuration and model paths
- `migrations/`: Alembic environment and schema revisions
- `.env.example`: local MySQL configuration template (copy to ignored `.env`)
- `tests/test_pipeline.py`: focused unit tests
- `tests/test_database.py`, `tests/test_api_persistence.py`: isolated DB/API tests
- `tests/test_mysql_integration.py`: optional MySQL integration test; runs in backend CI
- `.github/workflows/`: backend MySQL/test and frontend build CI
- `Makefile`: common setup, training, API, test, lint, and frontend commands
- `Dockerfile` and `docker-compose.yml`: containerized local API setup
- `BIG_COMPANY_ROADMAP.md`: planned engineering improvements

Run tests with `python -m pytest`. Because the category labels are inferred from `Ticket Type` and the dataset contains templated examples, evaluation scores describe this dataset and mapping only; they should not be presented as production routing performance. A production system should be trained and evaluated on tickets with human-verified destination queues and urgency outcomes.
