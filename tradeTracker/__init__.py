import os
from flask import Flask
from flask_cors import CORS
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_wtf import CSRFProtect
import logging
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv
from .logging_config import configure_logging
from . import actions

limiter = Limiter(key_func=get_remote_address)
crsf = CSRFProtect()

def abort_secret_key():
    raise RuntimeError

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    limiter.init_app(app)
    crsf.init_app(app)

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    ALLOWED_ORIGINS = [
    "https://tracker.yourdomain.com",
    f"chrome-extension://{os.environ['CHROME_EXTENSION_ID']}"
    ]
    CORS(app, 
         origins=ALLOWED_ORIGINS, 
         supports_credentials=True, 
         allow_headers=["Content-Type", "X-CSRF-Token"],
         methods=["GET", "POST", "PATCH", "DELETE"])

    csp = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
    }
    Talisman(app, content_security_policy=csp)

    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    # Use DATA_DIR for database storage in production
    if os.getenv("FLASK_ENV") == "prod":
        data_dir = os.getenv("DATA_DIR", app.instance_path)
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.path.join(data_dir, "tradeTracker.sqlite")
    else:
        # Running in development
        db_path = os.path.join(app.instance_path, "tradeTracker.sqlite")

    app.config.from_mapping(
        DATABASE=db_path,
        SECRET_KEY=os.environ.get('SECRET_KEY') or abort_secret_key() 
    )

    #I dont even need this I think
    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile("config.py", silent=True) 
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import db, tracker, actions, migration, renderers

    # Run database migration before initializing the app
    migration.migrate_database(app.config["DATABASE"])

    db.init_app(app)

    configure_logging(app)
    app.logger.info("App startup")
    app.logger.setLevel(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("waitress").setLevel(logging.WARNING)

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        if isinstance(err, HTTPException):
            return err
        app.logger.exception("Unhandled exception during request")
        return {"status": "error", "message": "Internal server error"}, 500

    # Initialize the database if it doesn't exist
    if not os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            db.init_db()
            print("Database initialized automatically on first run")

    app.register_blueprint(tracker.bp)
    app.register_blueprint(actions.bp) 
    app.register_blueprint(renderers.bp)

    return app
