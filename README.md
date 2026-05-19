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
tradeTracker/
  __init__.py              # create_app() — CORS, CSP, CSRF, blueprints
  api.py                   # /api endpoints (extension)
  tracker.py               # Page routes
  actions.py               # Mutating endpoints (auctions, sales, etc.)
  renderers.py             # HTML rendering routes
  db.py                    # SQLite connection + init
  migration.py             # Schema migrations run on startup
  generateInvoice.py       # PDF invoice generation
  services/
    cfAuth.py              # Cloudflare Access JWT + API token decorators
    sale_service.py        # Sale processing
    reciept_service.py     # Receipt generation
    models.py
  static/, templates/, fonts/
tests/                     # pytest suite (payments, bulk FIFO, endpoints)
requirements.txt
secureApp.md               # Deployment & hardening plan
```

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

In production the app expects to sit behind a Cloudflare Tunnel; bind only to `127.0.0.1`. See `secureApp.md` for the full deployment plan.

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
