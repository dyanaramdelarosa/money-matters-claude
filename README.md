# MoneyMatters

A personal budgeting web application. See `specs.md` for the full product spec and
`CLAUDE.md` for architecture, domain rules, and conventions.

> This README covers Milestones 1-2 (scaffold, auth). Docker Compose, seed data, and
> full deployment notes land in a later milestone.

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
account). You'll land on `/profile/` after signing up. Password-reset emails print to
the terminal in dev (console email backend) instead of actually sending.

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
pre-commit install               # install git hooks once per clone
pre-commit run --all-files       # run all hooks manually
```

## Deployment

Docker Compose setup lands in a later milestone (see `specs.md` Milestones list).
