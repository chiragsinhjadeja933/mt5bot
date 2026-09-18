"""
Preflight Environment & Platform Check
Sections 0.1, 0.2, 44 [ADD]
Checks:
- OS is Windows (critical: MetaTrader5 only works on Windows)
- Python >= 3.10
- Node.js & npm installed
- MetaTrader5 Python package installed and imported
- Detection of terminal64.exe installed and running
- Free disk space & working directory
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> str | None:
    try:
        if platform.system() == "Windows" and cmd[0] in ("npm", "npx"):
            cmd = [cmd[0] + ".cmd"] + cmd[1:]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return None


def main() -> int:
    print("=" * 60)
    print("MT5 DEMO TRADING TERMINAL — PREFLIGHT CHECK")
    print("=" * 60)

    blockers = []
    warnings = []

    # 1. Operating System
    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    print(f"[*] OS: {os_name} {os_release} (version {os_version})")
    if os_name != "Windows":
        blockers.append(
            f"OS is '{os_name}'. MetaTrader5 Python library requires Windows native execution."
        )

    # 2. Python version
    py_ver = platform.python_version()
    print(f"[*] Python: {py_ver} ({sys.executable})")
    if sys.version_info < (3, 10):
        blockers.append(f"Python 3.10+ required; found {py_ver}")

    # 3. Pip version
    pip_ver = run_cmd([sys.executable, "-m", "pip", "--version"])
    print(f"[*] Pip: {pip_ver or 'NOT FOUND'}")
    if not pip_ver:
        warnings.append("pip was not detected")

    # 4. Node.js & npm
    node_ver = run_cmd(["node", "--version"])
    npm_ver = run_cmd(["npm", "--version"])
    print(f"[*] Node.js: {node_ver or 'NOT FOUND'}")
    print(f"[*] npm: {npm_ver or 'NOT FOUND'}")
    if not node_ver:
        warnings.append("Node.js not found in PATH (needed for frontend dev/build)")
    if not npm_ver:
        warnings.append("npm not found in PATH")

    # 5. MetaTrader5 package
    try:
        import MetaTrader5 as mt5  # type: ignore
        mt5_ver = getattr(mt5, "__version__", "installed")
        print(f"[*] MetaTrader5 package: {mt5_ver} (import OK)")
    except ImportError as e:
        warnings.append(
            f"MetaTrader5 package import failed ({e}). Install via 'pip install MetaTrader5'."
        )
        print("[-] MetaTrader5 package: NOT INSTALLED / FAILED TO IMPORT")

    # 6. MT5 terminal64.exe detection
    mt5_paths = [
        Path(r"C:\Program Files\MetaTrader 5\terminal64.exe"),
        Path(r"C:\Program Files (x86)\MetaTrader 5\terminal64.exe"),
    ]
    custom_path = os.getenv("MT5_PATH")
    if custom_path:
        mt5_paths.insert(0, Path(custom_path))

    found_terminal = None
    for p in mt5_paths:
        if p.exists():
            found_terminal = p
            break

    if found_terminal:
        print(f"[*] MT5 desktop terminal detected at: {found_terminal}")
    else:
        warnings.append(
            "terminal64.exe not found at standard path (C:\\Program Files\\MetaTrader 5\\terminal64.exe). "
            "Set MT5_PATH in .env if installed elsewhere."
        )
        print("[-] MT5 desktop terminal: Not found in standard locations")

    # 7. Check if terminal64.exe process is currently running
    tasklist = run_cmd(["tasklist", "/FI", "IMAGENAME eq terminal64.exe"])
    if tasklist and "terminal64.exe" in tasklist:
        print("[*] MT5 process (terminal64.exe): CURRENTLY RUNNING")
    else:
        print("[*] MT5 process (terminal64.exe): NOT RUNNING (will be started on connect)")

    # 8. Free disk space & CWD
    cwd = Path.cwd()
    print(f"[*] Working directory: {cwd}")
    total, used, free = shutil.disk_usage(cwd)
    free_gb = free // (2**30)
    print(f"[*] Free disk space: {free_gb} GB")
    if free_gb < 2:
        warnings.append("Less than 2 GB free disk space remaining.")

    print("-" * 60)
    if warnings:
        print("WARNINGS / NON-BLOCKING OBSERVATIONS:")
        for w in warnings:
            print(f"  [!] {w}")

    if blockers:
        print("\nFATAL BLOCKERS:")
        for b in blockers:
            print(f"  [X] {b}")
        print("=" * 60)
        return 1

    print("\nPREFLIGHT STATUS: OK to run.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
