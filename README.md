# Trade Tracker

A Flask-based web application for tracking trading-card auctions, singles, bulk inventory, and sales. Includes invoice (PDF) generation, a companion Chrome extension integration for importing data from Cardmarket, and FIFO-based bulk/holo inventory accounting.

Production deployment: `https://app.cardanvil.sk` (API on `https://api.cardanvil.sk`).

## Features

- Auctions, singles, and collection management
- Sold items history with multi-payment-method support
- Bulk / holo / EX inventory with FIFO deduction on sale
- Invoice generation (PDF) with QR-code payment slips
- Chrome extension endpoint (`/CardMarketTable`) to import scraped Cardmarket rows
- Cloudflare Access JWT verification for browser routes
- Static API-token auth for extension calls
- CSRF, CORS allowlist, CSP via Flask-Talisman, rate limiting via Flask-Limiter

## Project layout

```
run_app.py                 # WSGI entry — exposes `app` for Waitress / Flask
conftest.py                # Repository-root pytest configuration
tradeTracker/
  __init__.py              # create_app() — CORS, CSP, CSRF, blueprints
  api.py                   # /api endpoints (extension)
  tracker.py               # Page routes
  actions.py               # Mutating endpoints (auctions, sales, etc.)
  renderers.py             # HTML rendering routes
  db.py                    # SQLite connection + init
  generateInvoice.py       # PDF invoice generation
  services/
    cfAuth.py              # Cloudflare Access JWT + API token decorators
    sale_service.py        # Sale processing
    reciept_service.py     # Receipt generation
    models.py
  static/, templates/, fonts/
tests/                     # pytest suite (payments, bulk FIFO, endpoints)
migrations/                # Active Yoyo migrations applied on app startup
migration_archive/         # Historical scripts only; not applied on startup
  pre_yoyo_migrations.py   # Legacy pre-Yoyo migration implementation
  add_bulk.py
  migrate_to_sales_history.py
scripts/                   # Manual maintenance utilities; not startup migrations
  backfill_cardmarket_id.py
  normalize_names.py
docs/TODO.md               # Feature / bugfix backlog
requirements.txt
```

Root configuration files and dependency manifests remain at the repository root alongside
`run_app.py` and `conftest.py`.

## Requirements

- Python 3.11+
- Dependencies pinned in `requirements.txt`

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `tradeTracker/.env` (loaded automatically when `FLASK_ENV` is not `production`):

```env
SECRET_KEY=<random-secret>
CHROME_EXTENSION_ID=<your-extension-id>
CHROME_EXTENSION_API_TOKEN=<shared-token>
KEY=<base64-encoded-encryption-key>
POLICY_AUD=<cloudflare-access-aud>
TEAM_DOMAIN=<your-team>.cloudflareaccess.com
```

The SQLite database is created automatically on first run under the Flask `instance/` folder (or `DATA_DIR` in production).

## Running

Development:

```powershell
$env:FLASK_APP = "run_app.py"
flask run
```

Production (Waitress):

```powershell
$env:FLASK_ENV = "prod"
waitress-serve --listen=127.0.0.1:420 run_app:app
```

In production the app expects to sit behind a Cloudflare Tunnel; bind only to `127.0.0.1`.

## Database migrations and maintenance

`create_app()` applies pending Yoyo migrations from the repository's `migrations/`
directory on startup, using the configured database. Yoyo tracks applied migrations;
there is no `tradeTracker/migration.py` or manual `migrate_database()` registration.
For schema changes, add a new migration importing `step` from `yoyo`, declare any
required predecessor IDs in `__depends__`, and define `steps` with both forward SQL
and rollback SQL (see existing migrations). Verify apply and rollback on a disposable
database copy before deployment, and back up the live database first.

`migration_archive/` is historical reference only, including `add_bulk.py` and
`migrate_to_sales_history.py`; do not run these as part of startup or routine maintenance.

Run manual utilities from the **repository root** with the virtual environment active,
after taking a consistent SQLite backup (stop writers or use SQLite's backup facility).
For Cardmarket ID backfills, supply the intended database and CSV explicitly, review
the default dry run, and only then repeat with `--commit`:

```powershell
python scripts/backfill_cardmarket_id.py --csv cards.csv --db "instance/tradeTracker.sqlite"
python scripts/backfill_cardmarket_id.py --csv cards.csv --db "instance/tradeTracker.sqlite" --commit
python scripts/normalize_names.py
```

`normalize_names.py` writes immediately and uses the root-relative
`instance/tradeTracker.sqlite`; confirm that is the intended database before running it.
For backfills against production, pass the actual database path (for example under
`DATA_DIR`) instead. Neither utility is a startup migration.

See `docs/TODO.md` for the backlog; historical line references and statuses there may be stale.

## Tests

```powershell
python -m pytest tests/ -v
```

See `tests/README_TESTS.md` for detailed coverage of the payment validation and bulk-FIFO test suites.

## Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing — required |
| `FLASK_ENV` | `prod` enables production paths (`DATA_DIR`, secure logging) |
| `DATA_DIR` | Override for database + generated-file location (prod only) |
| `CHROME_EXTENSION_ID` | Allowed extension origin for CORS |
| `CHROME_EXTENSION_API_TOKEN` | Bearer token required by `/api/*` endpoints |
| `KEY` | Base64 key used by sale/receipt encryption |
| `POLICY_AUD` | Cloudflare Access application AUD claim |
| `TEAM_DOMAIN` | Cloudflare Access team domain (for JWKS lookup) |
| `TRADETRACKER_LOG_LEVEL` | Optional log level override |

## License

MIT — see `LICENSE`.
