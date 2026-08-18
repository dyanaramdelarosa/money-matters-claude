# MoneyMatters

A personal budgeting web application. See `specs.md` for the full product spec and
`CLAUDE.md` for architecture, domain rules, and conventions.

> This README covers Milestones 1-6 (scaffold, auth, accounts/categories CRUD,
> transactions CRUD including transfers, budgets with period materialization, dashboard +
> analytics) plus the post-Milestone-4 additions listed below. Docker Compose, seed data,
> and full deployment notes land in a later milestone (see `specs.md` Milestones list).

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
uv run python manage.py migrate
uv run python manage.py tailwind build
uv run python manage.py runserver
```

Visit `http://127.0.0.1:8000/auth/signup/` to create a user (pick an email,
password, and base currency — there's no `createsuperuser`-provisioned default
account). You'll land on `/profile/` after signing up; a starter set of expense/income
categories is seeded automatically. Password-reset emails print to the terminal in dev
(console email backend) instead of actually sending.

From there:
- `/accounts/` — manage Accounts (cash/bank/credit card/etc, one currency per user).
  Editing an account also exposes "Correct Current Balance" (logs a Balance Correction
  transaction) and "Edit Opening Balance" (shifts the balance directly, no transaction)
  as extra sections on the same page.
- `/categories/` — manage expense/income categories.
- `/transactions/` — the ledger: create expenses, income, transfers between your own
  accounts, and filter the list by date range, type, account, or category.
- `/budgets/` — set a budget per category (or leave the category blank for "Overall"),
  scoped semi-monthly, monthly, or annually. The list shows each budget's current-period
  spent/remaining/percent-used; editing the amount only affects the current and future
  periods, never an already-closed one.
- `/dashboard/` — expense by category over time, income vs expense trend, net cash flow,
  top spending categories, per-account balance history, and budget vs actual, all filterable
  by an arbitrary date range or a Month/Quarter/Year preset. Each chart is its own
  independent HTMX-loaded card.

Visit `http://127.0.0.1:8000/healthz/` — should return `{"status": "ok"}`.

By default, without a `DATABASE_URL` set, the app uses a local SQLite file
(`db.sqlite3`). Set `DATABASE_URL` to point at Postgres (used in Docker Compose and CI)
once it's available.

## Environment variables

See `.env.example`. Key variables:

| Variable | Purpose | Default |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Which settings module to load | `config.settings.dev` |
| `DJANGO_SECRET_KEY` | Django secret key | insecure dev placeholder |
| `DJANGO_DEBUG` | Debug mode | `False` (base), `True` in dev |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `[]` (required in prod) |
| `DATABASE_URL` | `django-environ` DB URL | `sqlite:///db.sqlite3` |

## Common commands

```bash
uv run pytest                    # run tests
uv run ruff check .              # lint
uv run ruff format .             # format
uv run python manage.py tailwind build   # compile Tailwind CSS after template/class changes
uv run python manage.py reconcile_balances       # report any drift between accounts'
                                                  # cached balance and their transaction history
uv run python manage.py reconcile_balances --fix # ...and correct it
pre-commit install               # install git hooks once per clone
pre-commit run --all-files       # run all hooks manually
```

## Deployment

Docker Compose setup lands in a later milestone (see `specs.md` Milestones list).
