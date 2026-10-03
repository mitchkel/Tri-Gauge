# Tri-Gauge

A household money-and-time dashboard. Phase 1 provides a Django 5.2 LTS
application, server-rendered navigation, and a persistent SQLite database.
No UP Bank requests, classifier, or gauge visual are implemented.

## Run locally

Use Python 3.12. From the repository directory:

```sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Only copy the example if you do not already have a `.env`. Generate a secret:

```sh
.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Put that generated value in `.env` as `DJANGO_SECRET_KEY`. Leave
`DJANGO_DEBUG=true` for local development. The fake `UP_BANK_TOKEN` is unused;
do not supply a real bank token in this phase.

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

On your own computer, open `http://127.0.0.1:8000/`. In the cloud, use local HTTP
requests for validation; no public preview or deployment is configured.
This onboarding checkout already has an ignored local `.env` and migrated database.

## Verify

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py showmigrations
curl --fail http://127.0.0.1:8000/health/
```

The health response should be:

```json
{"status": "ok", "database": "ok", "bank_connection": "not_configured"}
```

It queries all application tables and returns 503 with a generic message if a
query fails. Tests use a separate temporary database and exercise writes,
relationships, exact decimal amounts, uniqueness, cycle date constraints,
page navigation, and health failure handling. They do not add sample household
data to your actual database. `db.sqlite3` persists local data across restarts.

## Database foundation

- `BankAccount`: bank identifier, name, currency.
- `RawTransaction`: account, unique bank identifier, date, signed decimal amount,
  currency, description, raw transaction payload.
- `ClassificationRule`: enabled flag, priority, criteria, target category.
- `TransactionClassification`: one current classification per transaction,
  optional rule and household cycle.
- `ManualOverride`: one current manual correction per transaction with reason.
- `HouseholdCycle`: named date range with an ordered-date constraint.
- `SyncState`: one pagination cursor and last successful sync time per provider.

Rules and overrides are storage only; no precedence or classification engine
exists yet. Raw payloads must contain transaction data only, never request
headers, credentials, or tokens. Foreign keys protect accounts with transactions.
The initial schema assumes one household and globally unique transaction IDs
from a single future provider. Multi-household permissions, history, and broader
provider support are deferred.

## Secrets and deployment boundary

`.env`, virtual environments, and SQLite files are ignored by Git. `.env.example`
contains fake values only. Environment variables supplied by the deployment
platform take precedence over `.env`. Startup requires a real Django secret.
The future `UP_BANK_TOKEN` must be read only by server-side integration code;
Phase 1 does not read it, send it, store it, or render it. Never log environment
variables, settings dumps, authorization headers, or bank credentials. No secret
entry form or browser JavaScript is included.

This is a local development foundation, not a production-ready financial service.
Before deploying: set `DJANGO_DEBUG=false`, inject secrets securely, specify
`DJANGO_ALLOWED_HOSTS`, use HTTPS and a production WSGI/ASGI server, configure
static-file serving (`manage.py collectstatic`), implement authentication and
household authorization, and establish backups. Do not expose the development
server publicly or use real bank secrets with debug mode enabled.
SQLite is suitable for local development; Django's migrations provide a path to
PostgreSQL when deployment requirements are known. PostgreSQL dependencies and
configuration are intentionally not installed yet.

## Scope

Complete: application structure, four placeholder screens, seven database tables
and migration, ignored local configuration, health endpoint, and foundation tests.
Deferred: UP Bank integration, sync jobs, classifier execution, gauge visuals,
financial calculations, data-entry screens, authentication, and production hosting.
