"""Exercise both frozen executables against an isolated temporary vault."""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from secretmanager.ipc import LocalSecretServer  # noqa: E402


def _visible_titles_for_process(process_id: int) -> list[str]:
    if os.name != "nt":
        raise RuntimeError("The Windows bundle smoke check only runs on Windows.")

    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    titles: list[str] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL

    @callback_type
    def visit_window(hwnd, _parameter):
        owner_process = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_process))
        if owner_process.value == process_id and user32.IsWindowVisible(hwnd):
            title = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title, len(title))
            titles.append(title.value)
        return True

    user32.EnumWindows(visit_window, 0)
    return titles


def _check_cli(app_root: Path, isolated_root: Path) -> None:
    cli_exe = app_root / "SecretManagerCLI" / "SecretManagerCLI.exe"
    data_dir = isolated_root / "data"
    env_name = "PACKAGE_SMOKE_SECRET"
    secret_value = "smoke-" + os.urandom(18).hex()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config.json").write_text(
        json.dumps({"SecretManager": {"CliIntegrationEnabled": True}}),
        encoding="utf-8",
    )
    server = LocalSecretServer(
        data_dir,
        lambda name: (
            SimpleNamespace(value=secret_value, allow_cli=True)
            if name == env_name
            else None
        ),
    )
    server.start()
    try:
        command = [
            str(cli_exe),
            "run",
            "--use",
            env_name,
            "--",
            sys.executable,
            "-c",
            "import os, sys; sys.stdout.write(os.environ['PACKAGE_SMOKE_SECRET'])",
        ]
        if secret_value in command:
            raise AssertionError("The smoke secret must not be passed in command arguments.")

        result = subprocess.run(
            command,
            cwd=isolated_root,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"Packaged CLI exited {result.returncode}: {result.stderr.strip()}"
            )
        if result.stdout != secret_value:
            raise AssertionError("The child process did not receive the expected test value.")
    finally:
        server.close()

    print("PASS: packaged CLI authenticated to isolated IPC and injected the value into the child environment.")


def _check_gui(app_root: Path, isolated_root: Path) -> None:
    gui_exe = app_root / "SecretManager" / "SecretManager.exe"
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "windows"
    process = subprocess.Popen(
        [str(gui_exe)],
        cwd=isolated_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 30
        titles: list[str] = []
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(
                    f"Packaged GUI exited before opening its window (code {process.returncode})."
                )
            titles = _visible_titles_for_process(process.pid)
            if "Secret Manager" in titles:
                break
            time.sleep(0.25)
        else:
            raise AssertionError(
                f"Packaged GUI did not show its main window. Visible titles: {titles!r}"
            )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    if (isolated_root / "data" / "vault.key").exists():
        raise AssertionError("GUI smoke unexpectedly created a vault key.")
    if (isolated_root / "data" / "vault.db").exists():
        raise AssertionError("GUI smoke unexpectedly created a vault database.")

    print("PASS: packaged Fluent GUI opened in the isolated portable folder.")


def main() -> int:
    if os.name != "nt":
        raise SystemExit("Run this smoke check on Windows.")

    bundle_root = Path(sys.argv[1]).resolve()
    source_app = bundle_root / "app"
    if not (source_app / "SecretManager" / "SecretManager.exe").is_file():
        raise SystemExit(f"Packaged GUI not found under {source_app}")
    if not (source_app / "SecretManagerCLI" / "SecretManagerCLI.exe").is_file():
        raise SystemExit(f"Packaged CLI not found under {source_app}")

    with tempfile.TemporaryDirectory(prefix="secretmanager-package-smoke-") as temporary:
        isolated_root = Path(temporary)
        copied_app = isolated_root / "app"
        shutil.copytree(source_app, copied_app)
        _check_cli(copied_app, isolated_root)
        _check_gui(copied_app, isolated_root)

    print("PASS: package smoke checks used only temporary data; the project vault was not opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
