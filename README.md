# Tri-Gauge

A household money-and-time dashboard. Phase 1 provides a Django 5.2 LTS
application, server-rendered navigation, and a persistent SQLite database.
A server-side, read-only UP client is included. No classifier or gauge visual is implemented.

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
leave it fake when running automated tests.

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

On your own computer, open `http://127.0.0.1:8000/`. In the cloud, use local HTTP
requests for validation; no public preview or deployment is configured.
Every new checkout needs its own local configuration and migrations.

## Verify

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test
.venv/bin/python manage.py showmigrations
curl --fail http://127.0.0.1:8000/health/
```

The health response should be:

```json
{"status": "ok", "database": "ok"}
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
Only the internal UP client reads and sends it, exclusively to the UP API. It never stores or renders it. Never log environment
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
Deferred: transaction importing, sync jobs, classifier execution, gauge visuals,
financial calculations, data-entry screens, authentication, and production hosting.


## Phase 2A: deliberate UP verification

Official documentation: https://developer.up.com.au/ (schema source:
https://github.com/up-banking/api/blob/master/v1/openapi.json).
Account mapping uses `id`, `attributes.displayName`, `attributes.balance.currencyCode`,
and `attributes.accountType`. Balances and whole responses are discarded; schema
changes are not needed. Parsed accounts remain in memory only and are not saved.

Provide `UP_BANK_TOKEN` through the secure runtime environment configuration,
not source files or chat. The runtime must allow HTTPS to `api.up.com.au` and
preserve its proxy and trusted CA configuration. Do not copy a setup-only secret
into files to make it accessible. Automated tests use only fake values:

```sh
.venv/bin/python manage.py test
.venv/bin/python manage.py check_up
# Deliberate live requests only when runtime credentials/network are ready:
.venv/bin/python manage.py check_up --live
```

Without `--live`, status reports application/database readiness, token availability,
and `up_connection: not checked`, without contacting UP. With `--live`, the command
makes one ping, validates its response, then reads all account pages. Example
sanitized output (illustrative, not a claim of live verification):

```text
application: ok
database: ok
UP_BANK_TOKEN: available
up_connection: not checked
up_connection: successful
account_count: 2
account_types: SAVER (1), TRANSACTIONAL (1)
```

Errors are sanitized and produce a nonzero command exit status. No automatic
retries occur. Redirects are never followed; pagination must remain on HTTPS
`api.up.com.au` port 443 at `/api/v1/accounts`. Pagination loops and more than
100 pages fail safely. Connect/read timeouts are 5/20 seconds.
`/health/` and ordinary pages never contact UP and do not report UP connectivity.
There is no public endpoint to trigger bank requests. Do not enable HTTP debug
logging, dump request objects, or run a real token with Django debug error pages.
Runtime secrets must remain available to the management command, not just setup.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Only if .env does not already exist:
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
# Put the generated Django secret into your ignored .env.
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Use the same Python executable for `manage.py check_up` (or deliberate `--live`).
Live authentication/account retrieval still require separate runtime verification.
No transactions, sync jobs, webhooks, classification execution, gauge calculations,
or real-account persistence are implemented. Before any financial data is served,
resolve authentication, household authorization, production hosting, and backups.
