# MoneyMatters — Project Initialization

Act as a senior software engineer. Bootstrap a new personal budgeting web
application called **MoneyMatters**. This is a greenfield project in an empty
repository.

## Terminology (resolve the naming collision up front)

- **User** — an authenticated person (Django auth user).
- **Account** — a place money lives: cash, bank account, e-wallet, credit card.
  Use "Account" in the domain model and UI. Never use it to mean "user account";
  say "profile" or "user" for that.

## Tech stack

Required:
- Python 3.12+, Django 5.x
- `uv` for dependency and env management (`pyproject.toml`, lockfile committed)
- `ruff` for lint **and** formatting. Note: ruff's `I` ruleset replaces isort —
  enable it and don't add a separate isort dependency unless you can justify it.
- `pytest` + `pytest-django` for tests
- SQLite for local development, seeded with realistic mock data
- Docker Compose for one-command deployment

Choose and justify (one line each) before installing:
- Frontend approach: server-rendered Django templates + HTMX + Alpine.js +
  Tailwind, **or** DRF + a SPA. Default to the former unless you have a strong
  reason — it's a CRUD app and a SPA doubles the surface area.
- Charting library for the analytics dashboard.
- Auth: plain `django.contrib.auth` vs `django-allauth` (email verification,
  password reset, social login later).
- Test helpers: `factory-boy` or `model-bakery`, plus `freezegun` for the
  period-boundary tests.
- Production database in Compose. Flag the SQLite-dev/Postgres-prod drift risk
  and recommend which way to go.

Also set up: `django-environ` (or equivalent) for settings, `pre-commit` hooks
running ruff, `pytest-cov`, `whitenoise` + `gunicorn` for the container, and
`django-debug-toolbar` in dev only.

## Domain model and business rules

These are the parts that must be exactly right.

### Money
- Store amounts as `Decimal` (`DecimalField`), never `float`. Every monetary
  model field, aggregate, and API response must round-trip without precision loss.
- Every Account and Transaction carries an ISO-4217 currency code. For v1,
  restrict a user to a single currency and reject cross-currency transfers with
  a clear error — but model it so multi-currency can be added later.

### Accounts
- Full CRUD, scoped to the owning user.
- An Account has a running `balance`. Treat the transaction ledger as the source
  of truth and the stored balance as a cache: update it inside the same DB
  transaction as the ledger write (using row locking), and provide a
  `reconcile_balances` management command that recomputes from scratch and
  reports drift.
- Deleting an Account that has transactions must not silently orphan or destroy
  history. Decide between archive/soft-delete and blocking the delete — state
  which, and enforce it.

### Transactions
- Types: `EXPENSE`, `INCOME`, `TRANSFER`.
- Every write (create, edit, delete) must correctly adjust affected account
  balances. Editing a transaction's amount, date, type, or account must reverse
  the old effect and apply the new one — atomically. This is the single most
  common bug in this kind of app; write tests for it first.
- A TRANSFER references a source and a destination account, moves the amount in
  one atomic operation, and must never appear in income or expense analytics.
  Self-transfers (same account both sides) are invalid.
- Fields: amount, currency, type, date, account(s), category, note, optional
  attachment/receipt reference, created/updated timestamps.
- Categories: user-owned, with sensible system defaults seeded per new user.

### Budgets
- A user sets a budget per category (or overall) with scope
  `SEMI_MONTHLY` | `MONTHLY` | `ANNUAL`.
- **Historical immutability:** editing a budget must not retroactively change
  reports for periods that have already closed. Implement this by separating the
  recurring budget *definition* from the materialized *budget period* records
  that store the amount in force for that period. Editing the definition affects
  the current and future periods only. Cover this with an explicit test:
  "editing a July budget leaves the June report byte-identical."
- Define semi-monthly precisely: 1st–15th and 16th–end-of-month. Handle 28/29/30/31-day
  months and leap years.
- The dashboard shows, for the active period: budgeted, spent, remaining, and
  percent used — per category and in total. Overspend is shown as a negative
  remaining, not clamped to zero.

### Analytics
- Filter by arbitrary date range, with month/quarter/year presets.
- Minimum set: expense by category over time, income vs expense trend, net cash
  flow, top spending categories, per-account balance history, budget vs actual.
- Aggregation happens in the database (`annotate`/`aggregate`), not in Python
  loops over querysets.

### Account & data deletion
- Self-service **delete my data**: export first (JSON or CSV of accounts,
  transactions, budgets), then a confirmed, irreversible purge.
- Self-service **delete my profile**: soft-delete with a grace period, then hard
  purge via a management command. Document the retention window in CLAUDE.md.
- Deletion must not leave orphaned rows in any related table.

## Admin features

- Django admin, properly configured (list displays, filters, search, read-only
  computed fields) — not the bare default registration.
- Staff-only portal for user management: view/suspend/reactivate users, inspect
  a user's accounts and transactions read-only, view system-wide stats.
- Admins must **not** be able to silently alter a user's financial records.
  Anything that mutates user data is logged to an append-only audit trail
  (who, what, when, before/after).

## Security requirements (non-negotiable)

- Every queryset filtered by the requesting user. Add a test that user A gets a
  404 — not a 403 — on every one of user B's object URLs.
- CSRF on all mutations, `SECURE_*` settings on in production, secrets from env
  vars only, `DEBUG=False` default, no secrets or `.env` committed.
- Rate-limit login and password reset.

## Deliverables

1. Working Django project, migrations included.
2. `CLAUDE.md` at the repo root: architecture overview, domain model and the
   business rules above, directory layout, common commands (setup, run, test,
   lint, seed, reconcile), conventions and gotchas, and what *not* to do.
   Write it for an engineer joining cold — not as marketing copy.
3. `docker-compose.yml` + `Dockerfile` — `docker compose up` yields a running,
   migrated, seeded app. Include a separate dev override if useful.
4. `README.md`: quickstart, env vars, deployment notes.
5. Seed command (`python manage.py seed_demo`) generating ~12 months of
   realistic mock data across multiple accounts, categories, and budgets —
   enough that the analytics screens look real.
6. Tests: pytest, with coverage on all balance-mutation paths, budget period
   boundaries, historical budget immutability, transfer atomicity, and
   cross-user access. Target ≥85% coverage on domain logic; report actual.
7. `.gitignore`, `.env.example`, pre-commit config, and a CI config
   (GitHub Actions) running lint + tests.

## Milestones

1. Scaffold: uv project, Django skeleton, settings split, ruff, pytest, CI,
   pre-commit. Verify: empty test suite runs green, `ruff check` is clean.
2. Auth + users + profile.
3. Accounts + categories CRUD, with balance invariants and their tests.
4. Transactions CRUD including transfers, with the reverse-and-reapply edit
   logic and its tests.
5. Budgets with period materialization and historical immutability tests.
6. Dashboard + analytics.
7. Admin portal + audit log.
8. Data export, account deletion, data purge.
9. Docker Compose, seed data, CLAUDE.md, README.
10. Social login (Google/Facebook) via `django-allauth`'s `socialaccount` app,
    on top of the email/password auth built in Milestone 2.

Start with the plan.
