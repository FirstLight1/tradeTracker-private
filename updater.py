import os, sys, time, shutil, subprocess, tempfile, requests
from packaging import version as v
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

REPO = 'FirstLight1/tradeTracker'
URL = f"https://api.github.com/repos/{REPO}/releases/latest"
NEW_APP_NAME = 'TradeTracker.exe'  # New name for the application
OLD_APP_NAME = 'run_app.exe'  # Legacy name for backward compatibility

# The local version is now a variable.
# This should be updated for each new release when you build the .exe.
LOCAL_VERSION = "2.8.2"

# Detect which executable we're currently running
def get_current_exe_name():
    """Returns the name of the currently running executable"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.basename(sys.executable)
    else:
        # Running as script, default to new name
        return NEW_APP_NAME 

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def get_download_url():
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        data = response.json()
        assets = data.get('assets', [])
        
        if assets:
            return assets[0]["browser_download_url"]
        else:
            messagebox.showerror("Update Info", "No assets found in release. Skipping update check.")
            print("No assets found in release. Skipping update check.")
            return None
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Update Error", f"Failed to fetch release info: {e}")
        print(f"Failed to fetch release info: {e}")
        return None
    
def start_update():
    download_url = get_download_url()
    if download_url:
        current_exe = get_current_exe_name()
        update_with_cmd(download_update(download_url), current_exe)
    else:
        messagebox.showerror("Update Error", "Failed to get download URL. Update skipped.")
        print("Failed to get download URL. Update skipped.")
    
def check_version():
    try:
        # The local version is now read from the variable
        print(f"Current version: {LOCAL_VERSION}")

        try:
            response = requests.get(URL, timeout=10)
            response.raise_for_status()
            latest_version = response.json()["tag_name"]

            if v.parse(latest_version) > v.parse(LOCAL_VERSION):
                root = tk.Tk()
                root.title("TradeTracker Updater")
                root.resizable(False, False)

                root.eval('tk::PlaceWindow . center')
                frm = ttk.Frame(root, padding=25,style="Custom.TFrame")
                frm.pack()
                ttk.Label(frm, text="New update found! Do you want to update?").pack(pady=(0, 5))
                ttk.Label(frm, text=f"Current version: {LOCAL_VERSION} | New version: {latest_version}").pack(pady=(0, 15))
                buttons = ttk.Frame(frm)
                buttons.pack()
                ttk.Button(buttons, text="Yes", command=start_update).pack(side="left", padx=(10))
                ttk.Button(buttons, text="No", command=sys.exit).pack(side="left", padx=(10))
                root.mainloop()

                
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Update Check Error", f"Failed to check for updates: {e}")
            print(f"Failed to check for updates: {e}")
        except (KeyError, TypeError) as e:
            messagebox.showerror("Update Check Error", f"Could not find version from GitHub release: {e}")
            print(f"Could not find version from GitHub release: {e}")

    except Exception as e:
        messagebox.showerror("Version Check Error", f"Error during version check: {e}")
        print(f"Error during version check: {e}")


def download_update(download_url):
    try:
        temp_path = os.path.join(tempfile.gettempdir(), "tradeTracker.zip")
        with requests.get(download_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 1024  # 1 Kibibyte
            
            with open(temp_path, "wb") as f:
                for data in r.iter_content(block_size):
                    f.write(data)
                    # You could add a progress bar here if desired
                    
        print('Download complete! Starting update process...')
        return temp_path
    except Exception as e:
        print(f"Error downloading update: {e}")
        return None


def update_with_cmd(newFile, targetFile):
    if not newFile:
        messagebox.showerror("Update Error", "Update file not available. Update cancelled.")
        print("Update file not available. Update cancelled.")
        return
        
    try:
        # Clean up both old and new exe names to ensure smooth transition
        script = f"""
@echo off
echo Waiting for application to close...
ping 127.0.0.1 -n 2 > nul
if exist "{OLD_APP_NAME}" del "{OLD_APP_NAME}"
if exist "{NEW_APP_NAME}" del "{NEW_APP_NAME}"
echo Installing new version...
move "{newFile}" "{NEW_APP_NAME}"
echo Starting updated application...
start "" "{NEW_APP_NAME}"
del "%~f0"
"""
        temp_dir = tempfile.gettempdir()
        cmd_path = os.path.join(temp_dir, "update_app.cmd")
        with open(cmd_path, "w") as f:
            f.write(script)

        print("Starting update process...")
        time.sleep(2)
        # Run updater script and exit app
        subprocess.Popen(["cmd", "/c", cmd_path])
        sys.exit()
    except Exception as e:
        messagebox.showerror("Update Error", f"Error during update process: {e}")
        print(f"Error during update process: {e}")
        return False

if __name__ == "__main__":
    check_version()
