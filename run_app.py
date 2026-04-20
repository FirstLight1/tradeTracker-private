import os
import sys
import webbrowser
import threading
import time
import socket
import shutil
from tradeTracker import create_app
from waitress import serve
from dotenv import load_dotenv

import logging

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(__file__), "tradeTracker", ".env"))


def setup_expansion_files():
    """Copy expansion JSON files to DATA_DIR on first run."""
    if os.getenv("FLASK_ENV") == "prod":
        data_dir = os.getenv("DATA_DIR")
        if not data_dir:
            logger.warning("DATA_DIR is not set; skipping expansion file setup")
            return

        os.makedirs(data_dir, exist_ok=True)
        expansions_path = os.path.join(data_dir, "setAbbs.json")

        # Copy Set Abbreviations if it doesn't exist
        if not os.path.exists(expansions_path):
            try:
                source = os.path.join(
                    os.path.dirname(__file__),
                    "tradeTracker",
                    "data",
                    "expansions",
                    "setAbbs.json",
                )
                shutil.copy(source, expansions_path)
                print(f"Copied Set Abbreviations to {expansions_path}")
            except Exception as e:
                print(f"Error copying Set Abbreviations: {e}")


# Setup expansion files before anything else
setup_expansion_files()

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser():
    time.sleep(1.5)  # Wait for the server to start
    webbrowser.open("http://127.0.0.1:420")


def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


def handle_thread_exception(args):
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    logger.critical(
        "Unhandled thread exception",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


if __name__ == "__main__":
    sys.excepthook = handle_unhandled_exception
    threading.excepthook = handle_thread_exception
    is_prod = os.getenv("FLASK_ENV") == "prod"

    # Check if another instance is already running
    if is_port_in_use(420):
        if not is_prod:
            webbrowser.open("http://127.0.0.1:420")
        sys.exit(0)

    if not is_prod:
        threading.Thread(target=open_browser, daemon=True).start()
    app = create_app()

    # Use waitress as the production server
    print("TradeTracker is running. Close this window to shut down the server.")
    serve(app, host="127.0.0.1", port=420, threads=4)
