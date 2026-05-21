#!/usr/bin/env python3
"""
launch.py — Single entry point for Job Bot.
Starts the FastAPI server and opens the browser automatically.

Usage:
    python launch.py              # production (uses built ui/dist)
    python launch.py --dev        # start API only (Vite serves UI separately)
    python launch.py --port 8099  # custom port
"""
import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent
UI_DIST  = BASE_DIR / "ui" / "dist"
PORT     = 8099


def _wait_for_server(url: str, retries: int = 20) -> bool:
    import urllib.request
    for _ in range(retries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(description="Job Bot Launcher")
    parser.add_argument("--dev",    action="store_true", help="Dev mode (no UI build check)")
    parser.add_argument("--port",   type=int, default=PORT, help="Port to listen on")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    port = args.port

    # Build React UI if needed (production mode)
    if not args.dev and not UI_DIST.exists():
        ui_dir = BASE_DIR / "ui"
        if ui_dir.exists() and (ui_dir / "package.json").exists():
            print("Building UI (first run)...")
            try:
                _npm = "npm.cmd" if sys.platform == "win32" else "npm"
                subprocess.run([_npm, "install"], cwd=str(ui_dir), check=True)
                subprocess.run([_npm, "run", "build"], cwd=str(ui_dir), check=True)
                print("UI built successfully.")
            except Exception as e:
                print(f"Warning: Could not build UI: {e}")
                print("Run: cd ui && npm install && npm run build")
        else:
            print("Warning: ui/ directory not found. Run setup first.")

    print(f"Starting Job Bot on http://localhost:{port} ...")

    server = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "api.main:app",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ],
        cwd=str(BASE_DIR),
    )

    url = f"http://localhost:{port}"

    if _wait_for_server(url + "/api/settings"):
        print(f"Job Bot running at {url}")
        if not args.no_browser:
            webbrowser.open(url)
    else:
        print("Warning: Server may not have started correctly.")

    print("Press Ctrl+C to stop.")
    try:
        server.wait()
    except KeyboardInterrupt:
        print("\nStopping Job Bot...")
        server.terminate()
        server.wait(timeout=5)
        print("Stopped.")


if __name__ == "__main__":
    main()
