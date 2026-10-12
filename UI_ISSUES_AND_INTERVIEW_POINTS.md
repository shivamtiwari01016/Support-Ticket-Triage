# UI Issues, Pre-Deploy Checklist, and Interview Stand-Out Points

Scope: the React frontend in `frontend/src` and how to make the demo look professional before deploying and memorable in a data-science / ML-engineering interview. References use `file:line` against the current repo.

> Note: the backend is not runnable as-is (no `migrations/` folder for Alembic, CSV lives in `dataset/` not `data/raw/`, no `models/` artifact, `cryptography` missing from `.venv`). Fix those before a live demo — see the last section.

---

## 1. UI issues (current)

### 1.1 Two different design systems stitched together (the #1 tell)
- `frontend/src/index.css:3-33` defines a **light** theme with custom tokens: `--canvas:#f2f5f2`, `--surface:#fff`, `--teal:#147d72`, `--amber`, `--coral`, etc.
- `frontend/src/App.css:118-165` is an **appended "Model evaluation metrics panel" block** that assumes a **dark** theme and Tailwind default colors:
  - `var(--border-subtle, rgba(255,255,255,0.08))`, `var(--surface-raised, rgba(255,255,255,0.03))` — neither token is defined, so the fallbacks are used
  - `linear-gradient(90deg, #2dd4bf, #38bdf8)`, `#34d399`, `#f87171`
- Those classes are rendered on the light theme (`Dashboard.jsx:116-120` uses `.metric-cell`, `.metric-bar__fill`), so the panel looks bolted on and low-contrast.

### 1.2 Half-minified, half-pretty CSS
- `App.css` lines 1–116 are minified (many selectors per line; e.g. `App.css:84`, `:96-99`).
- Lines 118–165 are one-property-per-line. Two authors/generations. Run Prettier/`stylelint` to normalize.

### 1.3 Landing-page tropes with little meaning
- Decorative numbered placeholders: `01 / INPUT` (`TicketAnalyzer.jsx:67`), bare `02` (`:101`), `01 / 03` (`Dashboard.jsx:159`).
- Eyebrow micro-caps on nearly every panel (`Dashboard.jsx:52,91,143,158`; `TicketAnalyzer.jsx:50,64,85,102`; `ModelInfo.jsx:40,85`).
- Decorative `status-pulse` dot (`Dashboard.jsx:57`), mono micro-labels everywhere.
- These add no information; they are the clearest "generated to look designed" signal.

### 1.4 Runtime font fetch
- `index.css:1` `@import` of Google Fonts (`DM Sans`, `IBM Plex Mono`) triggers a network request and can flash/FOUT. Self-host or drop it.

### 1.5 Weak loading / empty / error states
- Loading is text + spinner (`TicketAnalyzer.jsx:82-88`, `RecentTickets.jsx:26`, Dashboard metric/category panels `:104,150`), not skeletons.
- No React error boundary in `App.jsx`, so a render error blanks the whole app.

### 1.6 Dead code and defensive clutter
- `getTicket()` (`api.js:125`) is exported but never imported — there is **no ticket detail page** at all.
- `normalizeUrgency()` handles an object `{score}` shape the backend never returns (`api.js:31-34`).
- `normalizeTicket()` emits duplicate alias fields — `id`/`ticketId`, `urgency`/`score`, `urgencyLevel`/`level` (`api.js:58-68`).
- `frontend/src/assets/hero.png` is unused.

### 1.7 Three inconsistent urgency thresholds
- `utils/urgency.js:8`: Low `<0.34`, Medium `<0.67`.
- `api.js:56`: Low `<0.33`, Medium `<0.66`.
- Backend `urgency.py:30`: Low `<35`, Medium `<70` (0–100 scale).
- The same score can display a different level depending on which path computed it.

### 1.8 Missing table UX
- `RecentTickets` (`RecentTickets.jsx`) is a fixed "latest 10" table — no search, no filter (category/urgency/status), no sort, no pagination. Backend only supports `limit`.

### 1.9 No status workflow, no overrides
- `TicketStatus = "open" | "in_progress" | "resolved"` exists (`schemas.py:9`) but nothing ever sets a status other than `open`; no operator override of the predicted category.

### 1.10 Accessibility gaps
- Good: `:focus-visible` outline (`index.css:40`), labelled inputs, `aria-live` result region.
- Gaps: mobile sidebar (`App.css:108-115`) has no focus trap / `aria-expanded` / Esc handling; charts have `role="img"` but the metric bars have no text alternative; motion is not gated by `prefers-reduced-motion`.

### 1.11 Privacy: the ticket list is global
- `GET /tickets` returns every user's ticket text to every user (`RecentTickets` shows full text). On a public URL this is a PII leak.

### 1.12 Repo hygiene affecting the UI
- `frontend/dist/` (stale build) is committed even though `frontend/.gitignore` exists.
- `frontend/.oxlintrc.json` configures `oxlint`, which is not installed or run (dead config).

---

## 2. Before you deploy: UI checklist

1. **Unify the design language.** Delete the dark-theme block in `App.css:118-165` and restyle `.metric-cell` / `.metric-bar__fill` with the existing tokens:
   ```css
   .metric-cell { border: 1px solid var(--border); background: var(--surface-soft); }
   .metric-bar { background: var(--border); }
   .metric-bar__fill { background: var(--teal); }
   .delta-up { color: var(--success); }
   .delta-down { color: var(--danger); }
   ```
2. **Format the CSS consistently** (Prettier) and remove decorative numbering/eyebrows that carry no meaning.
3. **Add an error boundary** around `<Routes>` in `App.jsx`.
4. **Real states**: skeleton loaders, empty states with a next action, inline retry (keep the typed text — `TicketAnalyzer` already preserves it).
5. **Fix the urgency thresholds** to a single source shared conceptually with the backend, or derive the level from the backend value only.
6. **Privacy**: scope tickets to a session/demo dataset, anonymize, or disable writes on the public demo; add a persistent "demo, no real data" banner (there's already a caveat in `Dashboard.jsx:81-86` and `ModelInfo.jsx:47-55`).
7. **Self-host or remove** the Google Fonts import (`index.css:1`).
8. **Remove unused artifacts**: committed `frontend/dist/`, `src/assets/hero.png`, or actually wire oxlint.
9. **A11y pass**: focus trap + Esc for the mobile menu, `prefers-reduced-motion`, text alternatives for bars; run Lighthouse + axe.
10. **SPA fallback + CORS**: host must rewrite unknown paths to `index.html` (`BrowserRouter`), and add the production origin to `TICKET_TRIAGE_CORS_ORIGINS`.

---

## 3. Interview stand-out points (ranked)

1. **Actually deliver "explainable".** The app markets explainable NLP (`Dashboard.jsx:54`) but shows no explanation. Add a panel with:
   - per-class `predict_proba` (confidence for all four categories),
   - the **top TF-IDF terms × LogisticRegression coefficients** that drove the decision,
   - those tokens **highlighted in the ticket text**.
   Backing: `model.py` is a `Pipeline(TfidfVectorizer, LogisticRegression)`, so `predict_proba` and `named_steps["classifier"].coef_` / `named_steps["tfidf"].get_feature_names_out()` are directly available.
2. **Confidence + abstain.** Show confidence and a "needs human review" state below a threshold — a mature ML-engineering signal (the model is currently below the majority baseline).
3. **Human-in-the-loop feedback.** Let an operator override the predicted category; persist the correction (+ original) in the `predictions` table and show "X% of low-confidence predictions were overridden." This creates a real active-learning story.
4. **Ticket detail page + status workflow.** `getTicket()` already exists unused (`api.js:125`) and the `predictions` table already supports history. Add `PATCH /tickets/{id}` and render prediction history — a complete CRUD/workflow story.
5. **Model page that proves rigor.** Visualize the confusion matrix (already stored in the training metrics), show baseline-vs-model, and a short "why TF-IDF + LR over a transformer" tradeoff table.
6. **Table UX.** Search, filter by category/urgency/status, sort, and cursor pagination.
7. **Tests + CI.** Vitest + React Testing Library for the SPA and one Playwright E2E happy path; empty frontend test coverage is the most visible gap in the project.
8. **Reproducible demo data.** A seed script so the dashboard looks populated on first load.
9. **Observability.** Sentry + a request ID in structured logs.

### How to present it (what interviewers actually score)
- README with a **screenshot/GIF**, the architecture diagram, a metrics table (accuracy vs majority baseline), and an honest **Limitations / what I'd do next** section.
- A 2–3 minute Loom: problem → pipeline → explainability demo → one concrete tradeoff decision.
- Be ready for: *"Why is accuracy below the baseline, and what would you change?"* (proxy labels, near-duplicate leakage, cross-validation, better labels). A confident, honest answer beats a better number.

---

## 4. Quick wins vs bigger bets

| Effort | Item |
| --- | --- |
| Quick | Unify CSS tokens + reformat; remove tropes; add error boundary; fix thresholds; add ticket detail route using `getTicket` |
| Medium | Confidence + explainability panel (top terms + conflicts); skeleton loaders; filters/search/sort/pagination |
| Bigger | Human-in-the-loop overrides; status workflow + history; confusion-matrix viz; frontend tests + CI; seed data |

---

## 5. Deployment blockers that also break the demo

These are backend/setup issues, but they block any live UI demo:

- **No `migrations/` folder** while `alembic.ini` sets `script_location = migrations` → `alembic.util.exc.CommandError: Path doesn't exist: migrations`. Breaks app startup in development (`api.py:117-118`) and `tests/test_database.py`.
- **Data path mismatch**: code/README use `data/raw/customer_support_tickets.csv`; the CSV is at `dataset/customer_support_tickets.csv` (`train.py:98`). Training with defaults fails.
- **No `models/` dir/artifact** (`config.py:19-20`, `api.py:81-89`); must train first.
- **`.venv` ≠ `requirements.txt`**: the file is a good pinned list, but the venv has newer versions and **`cryptography` is not installed**, which PyMySQL needs for MySQL 8 `caching_sha2_password`.
- Commit a real `frontend/dist` build; don't ship the stale one.
