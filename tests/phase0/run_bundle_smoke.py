from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

bundle_dir = Path(os.environ["PHASE0_BUNDLE_DIR"]).resolve()
executable_name = "phase0-qt-smoke.exe" if os.name == "nt" else "phase0-qt-smoke"
executable = bundle_dir / executable_name
if not executable.is_file():
    raise SystemExit(f"Bundled executable not found: {executable}")

environment = os.environ.copy()
environment["QT_QPA_PLATFORM"] = "offscreen"
with tempfile.TemporaryDirectory(prefix="phase0-run-") as run_directory:
    result = subprocess.run(
        [str(executable)],
        cwd=run_directory,
        env=environment,
        check=False,
        timeout=60,
    )
if result.returncode:
    raise SystemExit(result.returncode)
print("PASS: the onedir PySide6/Fluent bundle starts outside its build directory")
