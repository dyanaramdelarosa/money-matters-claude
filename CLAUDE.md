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

## Architecture (as of Milestone 2)

- **Frontend**: server-rendered Django templates + HTMX + Alpine.js + Tailwind.
  DRF/SPA was rejected: this is a CRUD app and a separate API layer doubles
  the surface area for no benefit. Tailwind is compiled via `django-tailwind-cli`
  (standalone binary, no Node/npm) — see "Tailwind" below. HTMX isn't
  functionally wired in yet (no middleware, no partial-update views); auth
  pages are plain full-page POST/redirect. First real HTMX usage is planned
  for Milestone 3 (Accounts CRUD), where inline partial updates pay off.
- **Auth**: `django-allauth`, email/password only, no username field
  (`ACCOUNT_LOGIN_METHODS = {"email"}`). No email verification required
  (`ACCOUNT_EMAIL_VERIFICATION = "none"`) — there's no transactional email
  infra yet and this is presently single/trusted-user software; revisit if
  that changes. Password reset still sends real email (separate flow from
  verification) — console backend in dev, `EMAIL_URL` env var in prod (see
  `config/settings/prod.py`). Rate limiting on login/signup/password-reset
  uses allauth's secure-by-default `ACCOUNT_RATE_LIMITS`, left at defaults —
  backed by Django's cache framework, which defaults to per-process
  `LocMemCache`. That's fine for a single dev/gunicorn-worker deployment, but
  limits won't be shared across multiple prod workers until a shared cache
  (e.g. Redis) is introduced for other reasons. No custom user model — Django's
  stock `auth.User` + a `users.Profile` (OneToOne) per the spec's terminology
  section; allauth auto-populates the unused `username` column from email.
  **Social login (Google/Facebook) is wanted but deferred to Milestone 10** —
  allauth's `socialaccount` add-on layers on top of this without rework.
- **Currency**: each user picks a `base_currency` at signup, stored on
  `Profile`, validated against a shared `CURRENCY_CHOICES` list in
  `apps.core.currencies` (hand-maintained ISO-4217 subset, no dependency) —
  reused by Accounts/Transactions from Milestone 3 onward to enforce the
  spec's "single currency per user" rule.
- **Database**: Postgres everywhere it matters — Docker Compose (dev override
  and prod) and CI — via `django-environ`'s `DATABASE_URL`. SQLite
  (`sqlite:///db.sqlite3`) is only the fallback for a quick non-Docker local
  run, so day-to-day dev without Docker never touches Postgres-specific
  behavior (row locking, etc.) — be aware of that gap when testing anything
  concurrency-sensitive (balance updates, transfers) and prefer running
  against Postgres for those.
- **Domain apps** (one per bounded context; created as their milestone lands,
  not all up front): `core` (shared abstract models/utils — exists),
  `users` (Profile — exists), `accounts`, `categories` (shared by transactions
  and budgets — kept separate to avoid a dependency cycle between the two),
  `transactions`, `budgets`, `analytics` (aggregation only, no models),
  `audit` (append-only log).

## Tailwind

- `django-tailwind-cli` downloads a standalone Tailwind v4 binary (no Node/npm)
  into `.django_tailwind_cli/` (gitignored) and compiles
  `theme/source.css` (committed — this is where custom `@layer base` rules
  live, e.g. default input/label styling so allauth's default `form.as_p()`
  rendering looks reasonable without per-widget class injection) into
  `assets/css/tailwind.css` (gitignored, regenerated on build).
- Run `uv run python manage.py tailwind build` after changing `theme/source.css`
  or any template's class names, or `uv run python manage.py tailwind watch`
  while developing. The compiled CSS must exist before `runserver`/tests hit a
  page that renders `{% tailwind_css %}` — CI/Docker will need a build step
  added when they're set up (Milestone 9).
- allauth's account pages (login, signup, password reset, ...) are restyled by
  overriding `templates/allauth/layouts/base.html` (delegates straight to the
  project's `templates/base.html`) and a handful of
  `templates/allauth/elements/*.html` (h1, p, alert, button, hr, button_group,
  panel) — allauth's newer template pack renders through these small
  "element" partials, so overriding them once styles every account page
  consistently instead of restyling each page template individually.

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
    currencies.py        # shared CURRENCY_CHOICES (ISO-4217 subset)
    views.py             # /healthz/
  users/
    models.py            # Profile (OneToOne to auth.User, base_currency)
    forms.py              # SignupForm — adds base_currency, creates Profile
    views.py              # ProfileView (own profile only)
templates/               # project-level templates, shared across apps
  base.html               # site skeleton: tailwind_css tag, Alpine CDN, nav
  allauth/                # overrides allauth's own template pack — see "Tailwind"
    layouts/base.html
    elements/*.html
theme/
  source.css              # Tailwind input (committed); compiles to assets/css/tailwind.css
tests/                  # all tests live here, mirroring apps/ — not inside each app
  core/
    test_healthz.py
  users/
    test_models.py, test_signup.py, test_login_logout.py, test_profile_view.py
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
uv run python manage.py tailwind build   # compile Tailwind CSS (rerun after template/class changes)
uv run python manage.py tailwind watch   # rebuild on file change, for local dev
pre-commit install               # once per clone
pre-commit run --all-files
```

## Conventions and gotchas

- Money is always `Decimal` via `DecimalField` — never `float`, anywhere in
  the domain layer.
- Every user-owned queryset must be filtered by the requesting user; a
  cross-user object lookup should 404, never 403 (see specs.md Security
  requirements) — this becomes relevant starting Milestone 3. (`ProfileView`
  in Milestone 2 has no `<pk>` in its URL — it's always "my profile" — so
  there's no cross-user object-access surface to test yet; Accounts' list/
  detail-by-pk views are the first real case.)
- `apps.core` is the only place for genuinely cross-cutting concerns
  (abstract base models, shared utils). Don't let it become a dumping ground
  for domain logic that belongs in a specific bounded-context app.
- Ruff's `I` ruleset replaces isort — don't add isort separately.
- Tests live under top-level `tests/`, one subpackage per app (`tests/core/`,
  `tests/accounts/`, ...) — not inside `apps/<app>/tests/`. Each test
  subpackage needs an `__init__.py` so same-named test modules across apps
  (e.g. `test_models.py`) don't collide during pytest's rootless import.

## Roadmap addendum

- **Milestone 10: Social login (Google/Facebook)**, via allauth's
  `socialaccount` app (also recorded in `specs.md`'s Milestones list).
  Deferred out of Milestone 2 (plain email/password) — it's additive on top
  of the classic auth flow, not a rework.
