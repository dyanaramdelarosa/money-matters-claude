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
6. Keep documentation in lockstep with the code, not as a batch step at the
   end. When a milestone changes or resolves something `specs.md` left open,
   update `specs.md`'s "Decisions made during implementation" section as part
   of that milestone's work. Same for `CLAUDE.md` (architecture, directory
   layout, conventions) and `README.md` — update them as changes land, not
   retroactively.

## Architecture (as of Milestone 4)

- **Frontend**: server-rendered Django templates + HTMX + Alpine.js + Tailwind.
  DRF/SPA was rejected: this is a CRUD app and a separate API layer doubles
  the surface area for no benefit. Tailwind is compiled via `django-tailwind-cli`
  (standalone binary, no Node/npm) — see "Tailwind" below. HTMX still isn't
  functionally wired in (no middleware, no partial-update views) — Accounts/
  Categories CRUD (Milestone 3) stayed plain full-page Django views, and
  Milestone 4 (Transactions) reached for Alpine.js instead of HTMX too (see
  the Transactions bullet below) — its dynamic form fields are pure
  client-side show/hide, no server round-trip needed. First real HTMX usage
  is now expected at the Milestone 6 dashboard, wherever a partial re-render
  (date-range filters, chart updates) actually pays for the added moving
  parts.
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
  `apps.core.currencies` (hand-maintained ISO-4217 subset, no dependency).
  `Account.currency` is never a free-choice form field — it's always set
  server-side from `request.user.profile.base_currency` (in the create view's
  `get_form()`, before validation runs) and re-checked by `Account.clean()` —
  this is what actually enforces the spec's "single currency per user" rule.
- **Accounts & balance invariants** (Milestone 3): `Account.opening_balance`
  is not directly editable through the normal edit form (`AccountEditForm`
  only exposes `name`/`type`) — treated like the ledger's implicit first entry
  rather than an ad-hoc rewrite target. `balance` is never a form field; it's
  set from `opening_balance` on creation and otherwise only moves through
  `Account.adjust_balance(delta)`, the row-locking primitive
  (`select_for_update()` inside `transaction.atomic()`) that Milestone 4's
  transaction writes now call (see the Transactions bullet below — every
  individual balance delta, on both legs of a transfer, goes through this
  same primitive). A dedicated `Account.set_opening_balance(new_value)` (same
  row-locked shape as `adjust_balance`) was added post-Milestone-4 for the one
  legitimate reason to change it — correcting a wrong starting figure — and
  shifts `balance` by the same delta so every individual transaction's
  recorded effect is left untouched; it deliberately does **not** create a
  Transaction, since it's a correction to the ledger's baseline, not an event
  in it (see the Transactions bullet's `ADJUSTMENT` type for the event case).
  Exposed via `AccountOpeningBalanceForm`/`AccountEditOpeningBalanceView` at
  `/accounts/<pk>/opening-balance/`. Both this and the balance-correction flow
  (see the Transactions bullet's `ADJUSTMENT` paragraph) render as extra
  sections on the account **edit** page (`accounts/form.html`,
  `AccountUpdateView`) rather than as separate linked pages, so a user editing
  an account sees every account-level mutation in one place. Each section is
  still its own `<form>` posting to its own dedicated view/URL — the edit page
  only embeds the markup, it doesn't merge the three view/validation flows
  into one. This matters for `apps.accounts`' dependency direction: the
  correction section's fields are hand-written HTML on the template (matching
  `AccountBalanceCorrectionForm`'s field names) rather than
  `apps.accounts.views` importing that form class from `apps.transactions`,
  which would make `accounts` depend on `transactions` while `transactions`
  already depends on `accounts` (via the `Transaction.account` FK) — a cycle.
  `AccountOpeningBalanceForm` has no such issue since it's native to
  `apps.accounts`, so it's passed through `AccountUpdateView.get_context_data()`
  normally. Concretely: submitting the correction section redirects to
  `accounts:edit` (not the old submission's page) same as the opening-balance
  section, keeping the user in this same enriched edit view either way; a
  validation error in either sub-form still renders that section's own
  dedicated fallback template (`transactions/correct_balance_form.html`,
  `accounts/opening_balance_form.html`) rather than the merged page, since the
  two aren't a single Django view. The concurrency test for `adjust_balance`
  (`tests/accounts/test_models.py::AdjustBalanceConcurrencyTest`) only runs
  against Postgres — SQLite has no real row locking and raises "database is
  locked" under genuine thread contention instead of serializing, so the test
  self-skips there rather than being flaky or misleading. Both `Account` and
  `Category` use archive/soft-delete (`is_archived` + `archived_at`), never a
  hard delete, so future FK references (Transactions) never orphan. The
  `unique(user, name)` constraint on both models is a *conditional*
  `UniqueConstraint` (`condition=Q(is_archived=False)`) — scoped to active
  rows only, so archiving "Wallet" and creating a new active "Wallet" both
  named at once no longer raises `IntegrityError`; the archived row keeps its
  original name for history rather than needing a rename-on-archive hack.
  That DB constraint alone isn't enough for a clean UX: `user` is set
  server-side (never a form field), and Django's automatic unique-constraint
  form validation silently skips any constraint touching a field that's
  excluded from the form — so a name conflict would otherwise bypass
  validation entirely and surface as a raw `IntegrityError` at `save()`.
  `apps.core.forms.UniqueActiveNameFormMixin` (used by `AccountCreateForm`,
  `AccountEditForm`, `CategoryForm`) does the active-name-conflict check
  explicitly in `clean_name()` against `self.user` (passed in via the view's
  `get_form_kwargs()`), so it's a normal form error instead. The create/edit
  templates (`accounts/form.html`, `categories/form.html`) render
  `partials/form_errors_modal.html` — an Alpine.js modal (`x-data`/`x-show`,
  closes on Escape/backdrop-click/button) that pops up whenever `form.errors`
  is non-empty, listing every field error including the name conflict.
- **Categories**: `Category.kind` (`EXPENSE` | `INCOME`) was split from the
  start, ahead of when Milestone 4 strictly needs it, to avoid a later
  migration/backfill. Every new user gets a starter set
  (`apps/categories/defaults.py`) seeded by a `post_save` signal on the user
  model, owned by `apps.categories` itself (registered in
  `CategoriesConfig.ready()`) — `apps.users` has no idea `apps.categories`
  exists, keeping the dependency one-directional.
- **Transactions** (Milestone 4): `Transaction.type` is `EXPENSE` | `INCOME` |
  `TRANSFER` | `ADJUSTMENT`. A transfer is one row, not two linked rows —
  `account` is the source (or the only account for EXPENSE/INCOME/ADJUSTMENT)
  and `transfer_to_account` (nullable, TRANSFER-only) is the destination.
  `category` is required and kind-matched (`category.kind == type`) for
  EXPENSE/INCOME, forbidden for TRANSFER and ADJUSTMENT — enforced in
  `Transaction.clean()`, the single source of truth regardless of entry
  point. All of this — plus cross-user account checks and the
  currency-must-match-account check — lives in `clean()`, not scattered
  across the form, so it's exercised the same way by the view, the admin (if
  it were ever writable), and a future seed command. `amount` carries no
  field-level `MinValueValidator` (removed post-Milestone-4) — its sign rule
  is type-dependent (`ADJUSTMENT` needs a signed delta, every other type a
  positive magnitude), so it's enforced in `clean()` alongside everything
  else rather than as a second validation path.
  **`ADJUSTMENT`** ("Balance Correction" in the UI) is a post-Milestone-4
  addition for the "I forgot to log a week of spending, just fix the
  balance" case: a single-account transaction with a *signed* `amount`
  (`_effects()` uses it as-is, joining `INCOME` in that branch), no
  `category`, no `transfer_to_account`. It flows through the exact same
  `services.create_transaction`/`delete_transaction` pipeline as every other
  type — that's what keeps `reconcile_balances` correct automatically instead
  of "fixing" the correction back out as drift. Users never pick it directly:
  `TransactionForm.type` excludes it from its choices, and it's only ever
  created via `AccountBalanceCorrectionView`
  (`/transactions/correct-balance/<account_pk>/`, embedded as a section on the
  account edit page — see the Accounts bullet above for why that's a
  hand-written form on the template rather than an import of this view's form
  class), where the user enters the *target* balance and the view computes
  the signed delta. `TransactionUpdateView` redirects away (with a
  message) instead of rendering the edit form for an `ADJUSTMENT` row —
  editing a dated correction after the fact defeats the point of it; deleting
  one (the normal delete flow, unchanged) correctly reverses it and is the
  supported "undo."
  Balance mutation is **not** a `Transaction.save()` side effect — it lives in
  `apps/transactions/services.py` (`create_transaction`/`update_transaction`/
  `delete_transaction`), so a plain `.save()` (shell, fixtures, `bulk_create`)
  can never silently desync the balance cache; views call these functions
  instead of `ModelForm.save()`. The edit path is the spec's core risk
  ("reverse the old effect and apply the new one — atomically"): `Transaction._effects()`
  returns `[(account, signed_delta), ...]` for the instance's *current* field
  values; `update_transaction` re-fetches the *old* row locked (`select_for_update()`)
  before the in-memory instance's new values overwrite anything, reverses
  those old effects, saves, then applies the new ones — all inside one
  `transaction.atomic()` block, with every individual delta going through
  `Account.adjust_balance()` (M3) and effects applied in a consistent
  `account.pk` order to avoid lock-ordering deadlocks on a transfer's two
  accounts. **Hard delete**, not archive — unlike Account/Category, nothing
  references a Transaction by FK, so nothing can orphan; a confirm page
  (`transactions/confirm_delete.html`, via Django's `DeleteView`) guards the
  irreversible action. `reconcile_balances` (`apps/transactions/management/commands/`)
  recomputes each account's expected balance via DB aggregation (`Sum`/`Case`/`When`,
  not a Python loop) over the full ledger vs. `opening_balance`, reports any
  drift, and corrects it with `--fix`; it lives in `apps.transactions` (not
  `apps.accounts`) since recomputing needs the full ledger, which
  `transactions` owns — `transactions` already depends on `accounts` via FK,
  so this doesn't introduce a new dependency direction.
  The Transaction admin is **read-only** (`has_add/change/delete_permission = False`)
  — a writable default `ModelAdmin` would let a mutation bypass
  `services.py` and silently desync the balance cache; a mutation-safe,
  audit-logged admin path is Milestone 7's job, not built here.
  Archived accounts/categories are still valid on an *existing* transaction
  (no model-level block) but are excluded from the `account`/
  `transfer_to_account`/`category` querysets on the create/edit form, so they
  can't be picked for new activity. The create/edit form
  (`transactions/form.html`) uses Alpine.js to show/hide `transfer_to_account`
  (TRANSFER only) and to swap between two `category` `<select>`s (one
  EXPENSE-kind, one INCOME-kind, the inactive one `:disabled` so it never
  submits a stray value) based on the selected `type` — see the Frontend
  bullet above for why this is Alpine, not HTMX. Receipts are a plain
  `receipt_reference` text/URL field, not a real upload — no storage backend
  or `MEDIA_ROOT`/`MEDIA_URL` needed yet; overdraft is allowed everywhere, no
  balance floor enforced (matches how a `CREDIT_CARD` account naturally
  works).
  **List filtering** (post-Milestone-4 addition): the list view
  (`TransactionListView`) was deliberately plain CRUD with no filter UI when
  Milestone 4 shipped — filtering was assumed to belong to the Milestone 6
  dashboard instead. That was revisited: `TransactionFilterForm`
  (`apps/transactions/forms.py`, all fields optional — `date_from`, `date_to`,
  `type`, `account`, `category`) now drives `get_queryset()`'s filtering
  directly off `request.GET`, only applied when the form validates; an
  invalid filter (e.g. a malformed date typed into the URL) renders the full
  unfiltered list with the form's errors shown rather than erroring. The
  `account`/`category` `ModelChoiceField` querysets are scoped to the request
  user and use `.active()`, same as the create/edit form — an archived
  account/category can still be the target of a historical transaction, but
  it no longer appears as a filter option (revised post-launch: an archived
  category showing up in the filter dropdown read as clutter, not a useful
  history-browsing affordance). Filtering by an archived row's id directly
  (e.g. a stale bookmarked URL) now fails `ModelChoiceField` validation the
  same way a cross-user id does — the whole filter form is rejected and the
  full unfiltered list renders with the error shown, rather than silently
  applying it. `type` still includes `ADJUSTMENT` (filtering existing
  corrections is useful even though *creating* one through this dropdown
  stays blocked). The `account` filter matches either leg of a transfer
  (`account` OR `transfer_to_account`) so "everything touching this account"
  includes transfers into it, not just out of it. This is still the Milestone
  6 dashboard's Analytics-section filtering requirement (arbitrary date range
  with presets) — the list filters here are the ledger's own structured
  fields, not the aggregation/charting work that milestone still owns.
- **Database**: Postgres everywhere it matters — Docker Compose (dev override
  and prod) and CI — via `django-environ`'s `DATABASE_URL`. SQLite
  (`sqlite:///db.sqlite3`) is only the fallback for a quick non-Docker local
  run, so day-to-day dev without Docker never touches Postgres-specific
  behavior (row locking, etc.) — be aware of that gap when testing anything
  concurrency-sensitive (balance updates, transfers) and prefer running
  against Postgres for those.
- **Domain apps** (one per bounded context; created as their milestone lands,
  not all up front): `core` (shared abstract models/utils — exists),
  `users` (Profile — exists), `accounts` (exists), `categories` (exists;
  shared by transactions and budgets — kept separate to avoid a dependency
  cycle between the two), `transactions` (exists), `budgets`, `analytics`
  (aggregation only, no models), `audit` (append-only log).

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
  added when they're set up (Milestone 9). Plain `build` has a "skip if up to
  date" check that has been observed to silently no-op on a template-only
  class-name change (reports "is up to date. Use --force to rebuild." even
  though the class is genuinely new) — if a class you just added doesn't show
  up after a build + hard browser refresh, rerun with
  `uv run python manage.py tailwind build --force` before assuming it's a
  browser-cache issue. `tailwind watch` isn't known to have this problem since
  it recompiles on every detected file change rather than short-circuiting.
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
    forms.py              # UniqueActiveNameFormMixin — shared active-name-conflict
                           #   validation, used by accounts + categories forms
    views.py             # /healthz/
  users/
    models.py            # Profile (OneToOne to auth.User, base_currency)
    forms.py              # SignupForm — adds base_currency, creates Profile
    views.py              # ProfileView (own profile only)
  accounts/
    models.py             # Account: type, currency, opening_balance, balance,
                           #   is_archived; adjust_balance(), set_opening_balance(),
                           #   archive(), clean()
    forms.py               # AccountCreateForm (+opening_balance) vs AccountEditForm
                            #   vs AccountOpeningBalanceForm (post-creation correction)
    views.py                # List/Detail/Create/Update/Archive/EditOpeningBalance,
                             #   all user-scoped
  categories/
    models.py              # Category: kind (EXPENSE|INCOME), is_archived; archive()
    defaults.py             # DEFAULT_EXPENSE_CATEGORIES / DEFAULT_INCOME_CATEGORIES
    signals.py               # post_save(User) -> seeds defaults for every new user
  transactions/
    models.py               # TransactionType (incl. ADJUSTMENT); Transaction: account,
                             #   transfer_to_account (TRANSFER-only), category, amount,
                             #   currency, date, note, receipt_reference; clean(), _effects()
    services.py              # create_transaction/update_transaction/delete_transaction —
                              #   the reverse-and-reapply balance logic (views call these,
                              #   not form.save())
    forms.py                 # TransactionForm — user-scoped + .active()-only querysets,
                              #   excludes ADJUSTMENT from type choices; +
                              #   AccountBalanceCorrectionForm (target-balance input)
    views.py                 # List(paginated)/Detail/Create/Update/Delete +
                              #   AccountBalanceCorrectionView, all user-scoped
    management/commands/
      reconcile_balances.py  # --fix; per-account DB-aggregate drift report
templates/               # project-level templates, shared across apps
  base.html               # site skeleton: tailwind_css tag, Alpine CDN, nav
  partials/
    form_errors_modal.html  # Alpine-driven modal for form.errors — see below
  allauth/                # overrides allauth's own template pack — see "Tailwind"
    layouts/base.html
    elements/*.html
theme/
  source.css              # Tailwind input (committed); compiles to assets/css/tailwind.css
tests/                  # all tests live here, mirroring apps/ — not inside each app
  factories.py            # factory-boy: UserFactory, ProfileFactory, AccountFactory,
                           #   CategoryFactory, TransactionFactory — shared across app
                           #   test subpackages
  core/
    test_healthz.py
  users/
    test_models.py, test_signup.py, test_login_logout.py, test_profile_view.py
  accounts/
    test_models.py, test_views.py
  categories/
    test_models.py, test_signals.py, test_views.py
  transactions/
    test_models.py, test_services.py, test_reconcile_balances.py, test_views.py
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
  requirements). Delivered starting Milestone 3, and followed by every app
  since: every Accounts/Categories/Transactions view scopes
  `get_queryset()`/`get_object_or_404()` by `user=request.user`, so a valid
  pk belonging to another user 404s via Django's normal `get_object_or_404`
  path — no separate permission-denied branch to maintain. See
  `tests/accounts/test_views.py`, `tests/categories/test_views.py`, and
  `tests/transactions/test_views.py` for the concrete tests. (`ProfileView`
  in Milestone 2 has no `<pk>` in its URL — it's always "my profile" — so it
  had no cross-user surface to test.)
- **URL namespace**: `django-allauth` is mounted at `/auth/` (not the more
  common `/accounts/`) specifically to keep it out of the way of the
  `apps.accounts` (financial Accounts) CRUD app, which owns `/accounts/`.
  Mounting both under `/accounts/` would work today (their sub-paths happen
  not to collide) but is exactly the "Account" vs "user account" naming
  collision the spec calls out avoiding — don't reintroduce it. Everything
  that references allauth URLs does so by name (`account_login`,
  `account_signup`, ...) via `reverse()`/`{% url %}`, never a hardcoded path,
  so the prefix itself can move freely if needed.
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
- **Milestone 11: Index page** (`/`) — anonymous visitors go to login,
  authenticated users go to the dashboard (also recorded in `specs.md`'s
  Milestones list). Sequenced after Milestone 6, since it needs the
  dashboard to exist as its logged-in target; there's no `/` route at all
  yet (only `/healthz/`, `/profile/`, `/accounts/`, `/categories/`,
  `/transactions/`, and `/auth/...`).
- **Milestone 12: Custom 404 page** — a branded `templates/404.html`
  (also recorded in `specs.md`'s Milestones list), replacing Django's
  default 404 for both genuinely-missing URLs and the by-design cross-user
  404s (see the cross-user-404 bullet above). Only takes effect with
  `DEBUG=False`, so it isn't visible in local dev without explicitly
  testing it (`DEBUG=False` + a real `ALLOWED_HOSTS` entry, or
  `config.settings.prod`).
