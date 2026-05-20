#!/usr/bin/env python3
"""
build_app.py — Build a standalone JobBot desktop application using PyInstaller.

Usage:
    python build_app.py

Output: dist/JobBot (macOS/Linux) or dist/JobBot.exe (Windows)
"""
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def main():
    print("Step 1: Building React UI...")
    ui_dir = BASE_DIR / "ui"
    if not ui_dir.exists():
        print("ERROR: ui/ directory not found. Set up the frontend first.")
        sys.exit(1)

    subprocess.run(["npm", "install"], cwd=str(ui_dir), check=True)
    subprocess.run(["npm", "run", "build"], cwd=str(ui_dir), check=True)
    print("UI built.")

    print("Step 2: Running PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "JobBot",
        "--add-data", f"{ui_dir / 'dist'}{os.pathsep}ui/dist",
        "--add-data", f"{BASE_DIR / 'config'}{os.pathsep}config",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "fastapi",
        "--hidden-import", "playwright",
        str(BASE_DIR / "launch.py"),
    ]
    subprocess.run(cmd, check=True)
    print("Build complete. Executable is in dist/JobBot")


if __name__ == "__main__":
    main()
