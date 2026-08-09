## Working agreement (read first)

1. Before writing code, produce a short plan: proposed app/module breakdown,
   the data model (as a diagram or table), and any open questions. Wait for my
   approval on the plan.
2. Build in the milestones listed at the bottom. Complete and verify one
   milestone before starting the next — don't scaffold everything at once.
3. After each milestone: run `ruff`, run the test suite, and report the real
   results. If something fails or you skipped it, say so explicitly.
4. Where I've left a decision open, pick the option you'd defend in review,
   state the assumption in one line, and keep going. Only stop and ask if
   guessing wrong would mean throwing work away.
5. Prefer boring, idiomatic Django over clever abstractions. No premature
   microservices, no custom ORM layers, no dependency I haven't approved
   unless you flag it and say why.

## Architecture (as of Milestone 1)

- **Frontend**: server-rendered Django templates + HTMX + Alpine.js + Tailwind
  (added when the first real templates land — not wired yet). DRF/SPA was
  rejected: this is a CRUD app and a separate API layer doubles the surface
  area for no benefit.
- **Auth**: `django-allauth` (dependency installed now; wired up in Milestone 2).
- **Database**: Postgres everywhere it matters — Docker Compose (dev override
  and prod) and CI — via `django-environ`'s `DATABASE_URL`. SQLite
  (`sqlite:///db.sqlite3`) is only the fallback for a quick non-Docker local
  run, so day-to-day dev without Docker never touches Postgres-specific
  behavior (row locking, etc.) — be aware of that gap when testing anything
  concurrency-sensitive (balance updates, transfers) and prefer running
  against Postgres for those.
- **Domain apps** (one per bounded context; created as their milestone lands,
  not all up front): `core` (shared abstract models/utils — exists),
  `users` (Profile), `accounts`, `categories` (shared by transactions and
  budgets — kept separate to avoid a dependency cycle between the two),
  `transactions`, `budgets`, `analytics` (aggregation only, no models),
  `audit` (append-only log).

## Directory layout

```
config/                 # Django project config (not a domain app)
  settings/
    base.py             # shared settings; DATABASES via env.db(), sqlite fallback
    dev.py              # DEBUG=True, django-debug-toolbar
    test.py             # used by pytest-django; fast password hasher
    prod.py             # DEBUG=False, SECURE_* on, requires DATABASE_URL, whitenoise manifest storage
  urls.py
  wsgi.py / asgi.py
apps/                   # domain apps live here, one per bounded context
  core/
    models.py           # TimeStampedModel (abstract base: created_at/updated_at)
    views.py            # /healthz/
tests/                  # all tests live here, mirroring apps/ — not inside each app
  core/
    test_healthz.py
manage.py
```

## Settings

- Settings are split by environment; `manage.py` defaults to
  `config.settings.dev`. Set `DJANGO_SETTINGS_MODULE` explicitly in prod/CI.
- Env vars are read via `django-environ` from process env or a local `.env`
  (see `.env.example`; never commit `.env`).
- `DATABASE_URL` unset → SQLite file at the repo root. Set it to point at
  Postgres to match Docker Compose/CI.

## Common commands

```bash
uv sync                          # install/update deps from pyproject.toml + uv.lock
uv run python manage.py runserver
uv run python manage.py migrate
uv run pytest                    # tests (coverage report printed via pytest-cov)
uv run ruff check .              # lint
uv run ruff format .             # format
pre-commit install               # once per clone
pre-commit run --all-files
```

## Conventions and gotchas

- Money is always `Decimal` via `DecimalField` — never `float`, anywhere in
  the domain layer.
- Every user-owned queryset must be filtered by the requesting user; a
  cross-user object lookup should 404, never 403 (see specs.md Security
  requirements) — this becomes relevant starting Milestone 2.
- `apps.core` is the only place for genuinely cross-cutting concerns
  (abstract base models, shared utils). Don't let it become a dumping ground
  for domain logic that belongs in a specific bounded-context app.
- Ruff's `I` ruleset replaces isort — don't add isort separately.
- Tests live under top-level `tests/`, one subpackage per app (`tests/core/`,
  `tests/accounts/`, ...) — not inside `apps/<app>/tests/`. Each test
  subpackage needs an `__init__.py` so same-named test modules across apps
  (e.g. `test_models.py`) don't collide during pytest's rootless import.
