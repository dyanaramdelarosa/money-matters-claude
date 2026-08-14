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
11. Index page: `/` routes anonymous visitors to the login page and
    authenticated users to the dashboard. Built after Milestone 6, since it
    needs the dashboard to exist as its logged-in target.
12. Custom 404 page: branded, on-theme `templates/404.html` (Tailwind-styled,
    extends `base.html`) instead of Django's default debug/plain 404, shown
    whenever `DEBUG=False` — including the cross-user-object lookups that are
    already 404ing by design (see "Conventions and gotchas" in CLAUDE.md).

## Decisions made during implementation

The items this spec left open ("choose and justify", "state which and enforce", etc.)
were resolved via an interview at the start of each milestone. Recorded here for
reference; full rationale for each lives in `CLAUDE.md`.

### Milestone 1 (Scaffold)
- Frontend: Django templates + HTMX + Alpine.js + Tailwind (server-rendered), compiled
  via `django-tailwind-cli` (pip-only standalone binary — no Node/npm toolchain).
- Auth: `django-allauth`.
- Production database in Compose: Postgres everywhere it matters (Docker Compose dev
  override + prod, and CI) via `DATABASE_URL`. SQLite remains only the fallback for a
  quick non-Docker local run — this is the resolution of the SQLite-dev/Postgres-prod
  drift-risk flag.
- Test helpers: `factory-boy` + `freezegun`.
- Domain app breakdown: `core`, `users`, `accounts`, `categories`, `transactions`,
  `budgets`, `analytics`, `audit` — one Django app per bounded context.
- Charting library: not yet decided — deferred to Milestone 6, when the analytics
  dashboard is actually built.

### Milestone 2 (Auth + users + profile)
- Social login (Google/Facebook) is wanted, but built as a separate, later milestone
  (see Milestone 10 above) rather than alongside plain email/password auth.
- Email verification: none required to log in (`ACCOUNT_EMAIL_VERIFICATION = "none"`).
- Login identifier: email only, no separate username field.
- Base currency: chosen by the user at signup, stored on `Profile` — this is what the
  Money section's "restrict a user to a single currency" is enforced against.

### Milestone 3 (Accounts + categories CRUD)
- Account/Category deletion: archive/soft-delete (`is_archived` + `archived_at`), not
  blocking delete — this is the resolution of the Accounts section's "decide... state
  which" instruction. Applied consistently to both Accounts and Categories.
- Account type: fixed choices — `CASH`, `BANK`, `E_WALLET`, `CREDIT_CARD`, `OTHER`.
- Category kind: split into `EXPENSE` / `INCOME` from the start, ahead of when it's
  strictly needed — sets up Milestone 4's transaction-category validation and the
  Analytics section's per-kind reporting without a later migration/backfill.
- UI for this milestone: plain full-page Django CRUD, no HTMX yet. HTMX usage is
  expected to start once there's a clearer payoff (e.g. Transactions or the dashboard).
- Post-milestone fix: the `unique(user, name)` constraint on both Account and Category
  was scoped to active rows only (`condition=Q(is_archived=False)`), since a global
  constraint blocked reusing a name after archiving — e.g. archiving "Wallet" then
  creating a new "Wallet" raised `IntegrityError`. Archived rows keep their original
  name for history; only active rows must be unique per user.
- Post-milestone fix: that DB constraint alone still let name conflicts crash with a raw
  `IntegrityError` (Django's automatic unique-constraint form validation skips fields
  excluded from the form, and `user` isn't a form field). Added explicit `clean_name()`
  validation (`apps.core.forms.UniqueActiveNameFormMixin`) so a conflict is a normal form
  error, surfaced via an Alpine.js modal (`templates/partials/form_errors_modal.html`)
  rather than a crash or a silent inline-only error.

### Milestone 4 (Transactions CRUD including transfers)
- Receipt/attachment field: a text/URL reference (`CharField`), not a real file upload —
  this is the resolution of the Transactions section's "optional attachment/receipt
  reference" field. No storage backend or `MEDIA_ROOT`/`MEDIA_URL` needed yet; upgrading
  to real uploads later is additive, not a rework.
- Overdraft: allowed everywhere, no balance floor enforced by the app — matches how a
  `CREDIT_CARD` account naturally works; the spec doesn't ask for one.
- Transfer schema: one `Transaction` row per transfer (`account` = source,
  `transfer_to_account` = destination, nullable/TRANSFER-only), not two linked rows —
  this is the resolution of the Transactions section's "A TRANSFER references a source
  and a destination account, moves the amount in one atomic operation" requirement.
- Balance-effect logic (the reverse-and-reapply edit path the spec calls out as "the
  single most common bug in this kind of app") lives in `apps/transactions/services.py`,
  not in `Transaction.save()` — so a plain `.save()` (admin, shell, fixtures) can never
  silently skip balance adjustment. Every individual delta reuses `Account.adjust_balance()`
  (built in Milestone 3), applied in a consistent `account.pk` order to avoid
  lock-ordering deadlocks on a transfer's two accounts.
- `reconcile_balances` — deferred from Milestone 3 since there was nothing to reconcile
  against yet — lands in `apps.transactions` (not `apps.accounts`), since recomputing
  needs the full ledger; `transactions` already depends on `accounts` via FK, so this
  doesn't introduce a new dependency direction. Reports drift via DB aggregation, `--fix`
  to correct.
- Transaction deletion: hard delete, not archive/soft-delete — unlike Account/Category,
  nothing references a Transaction by FK, so nothing can be orphaned, and the spec lists
  delete as a normal write needing correct balance reversal. A confirm page guards the
  irreversible action.
- Category is required and kind-matched (`category.kind == type`) for EXPENSE/INCOME,
  forbidden for TRANSFER — this is exactly what Milestone 3 split `Category.kind` early
  for. Enforced in `Transaction.clean()`.
- Transaction admin is read-only this milestone — a writable default admin would let a
  mutation bypass the service layer and silently desync the balance cache; a
  mutation-safe, audit-logged admin path is Milestone 7's job.
- UI stays plain CRUD like Milestone 3, but the create/edit form uses Alpine.js
  (type-conditional fields: hide the destination-account field unless TRANSFER, swap
  between EXPENSE-kind and INCOME-kind category dropdowns) — HTMX stays deferred to
  wherever the payoff is clearest, still expected to be the Milestone 6 dashboard.
- Post-milestone addition: two account-balance corrections the milestone didn't cover —
  correcting the *current* balance (e.g. unlogged spending) and correcting the *opening*
  balance. These needed different handling: a current-balance correction is a real event,
  so it's a new `TransactionType.ADJUSTMENT` (single-account, signed `amount`, no
  category) that flows through the existing `services.create_transaction`/
  `delete_transaction` pipeline — this is what keeps `reconcile_balances` from silently
  reverting it as drift. An opening-balance correction is not an event, just a fix to the
  ledger's baseline, so `Account.set_opening_balance()` shifts `balance` by the same delta
  directly and deliberately creates no Transaction, to avoid double-counting against
  `reconcile_balances`. `amount`'s `MinValueValidator` moved off the field and into
  `Transaction.clean()` (branching on type) to allow `ADJUSTMENT`'s signed value.
  `ADJUSTMENT` is excluded from the general transaction form's type choices and can't be
  edited once created (only deleted, which correctly reverses it) — it's only produced via
  the dedicated "Correct balance" flow, which lives as an additional section on the
  account edit page (not the detail page — moved there so every account-level mutation is
  in one place).
- Post-milestone addition: simple filters on the Transactions list page (date range,
  type, account, category), reconsidering the milestone's original "no filter UI, that's
  Analytics' (Milestone 6) job" call. Scoped narrowly to the ledger's own structured
  fields via `TransactionFilterForm`, applied to `TransactionListView.get_queryset()` off
  `request.GET` — not the arbitrary-date-range-with-presets/charting/aggregation work
  Milestone 6 still owns. Filter dropdowns use `.active()`, same as the create/edit form
  (revised post-launch — archived rows were initially left in on purpose so historical
  transactions stayed filterable, but that made archived items read as clutter; filtering
  by an archived row's id directly now fails validation like a cross-user id does), and
  the account filter matches either leg of a transfer.

### Milestone 5 (Budgets with period materialization and historical immutability)
- Period materialization: lazy, on read — a `BudgetPeriod` snapshot is created the first
  time that period is actually needed (viewing the budget list), not on any schedule. This
  is the resolution of the Budgets section's "separate the recurring budget definition from
  the materialized budget period records" instruction; a scheduled/eager job was considered
  and rejected since the project has no task scheduler (no Celery, no django-crontab) and
  nothing else here runs background jobs. If a definition is never edited, the next period's
  materialization snapshots the same amount again — this is what gives "no changes made,
  reuse the same budget" for free, matching how the feature was originally described.
- Editing a budget's amount: the current, still-open period updates immediately; only
  periods that have already closed (`period_end < today`) are frozen forever. This is the
  resolution of "editing the definition affects the current and future periods only" —
  `update_definition_amount()`'s `period_end__gte=today` filter is both the "current updates
  live" behavior and the entire historical-immutability guarantee in one line. Covered by
  `tests/budgets/test_services.py`'s freezegun-based tests, including the spec's own example
  ("editing a July budget leaves the June report byte-identical").
- Milestone 5's UI includes spent-so-far/remaining/percent-used per budget on the list page,
  pulled forward from Milestone 6 (the spec lists these figures under Dashboard + analytics)
  since it's a single DB-aggregate query per row, not the arbitrary-date-range/preset/
  charting work that milestone still owns.
- "Overall" budget (the spec's "per category (or overall)"): `BudgetDefinition.category`
  nullable, null meaning every expense category. A plain `UniqueConstraint(["user",
  "category", "scope"])` would silently miss duplicate active Overall budgets (`NULL !=
  NULL` in SQL), so it's split into two conditional constraints — one scoped
  `category__isnull=False`, one scoped `category__isnull=True`.
- Budgets can only be set on `EXPENSE`-kind categories, enforced in `BudgetDefinition.clean()`
  — the spec's budget tracking is about spending, and an income category budget has no
  defined meaning here.
- Only `amount` is editable on an existing `BudgetDefinition` (`category`/`scope` are not) —
  same restriction `Account.opening_balance`/`AccountEditForm` established: changing what a
  budget covers is a create-a-new-one action, not an edit.
- `BudgetDefinition`/`BudgetPeriod` deletion: archive/soft-delete on the definition (same
  pattern as Account/Category), never a hard delete — `BudgetPeriod` rows must survive for
  history. Admin for both models is fully read-only, same rationale as `TransactionAdmin`.

Start with the plan.
