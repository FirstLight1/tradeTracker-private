import os
import sys
import webbrowser
import threading
import time
import socket
import shutil
import updater
from tradeTracker import create_app
from waitress import serve

import logging

logger = logging.getLogger(__name__)


def setup_expansion_files():
    """Copy expansion JSON files to AppData on first run (for .exe only)"""
    if getattr(sys, "frozen", False):
        app_data_dir = os.path.join(os.environ["APPDATA"], "TradeTracker")
        os.makedirs(app_data_dir, exist_ok=True)

        expansions_path = os.path.join(app_data_dir, "setAbbs.json")

        # Copy Set Abbreviations if it doesn't exist
        if not os.path.exists(expansions_path):
            try:
                source = os.path.join(sys._MEIPASS, "setAbbs.json")
                shutil.copy(source, expansions_path)
                print(f"Copied Set Abbreviations to {expansions_path}")
            except Exception as e:
                print(f"Error copying Set Abbreviations: {e}")


# Setup expansion files before anything else
setup_expansion_files()

# Run the updater check
updater.check_version()


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


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

    # Check if another instance is already running
    if is_port_in_use(420):
        # If app is already running, just open the browser
        webbrowser.open("http://127.0.0.1:420")
        sys.exit(0)

    threading.Thread(target=open_browser, daemon=True).start()
    app = create_app()

    # Override template and static folders to use bundled resources
    app.template_folder = resource_path(os.path.join("tradeTracker", "templates"))
    app.static_folder = resource_path(os.path.join("tradeTracker", "static"))

    # Use waitress as the production server
    print("TradeTracker is running. Close this window to shut down the server.")
    serve(app, host="127.0.0.1", port=420, threads=4)
