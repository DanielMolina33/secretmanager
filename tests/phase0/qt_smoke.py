from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, Theme, setTheme

from secretmanager.paths import get_data_dir, get_portable_root


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SecretManager Phase 0 Qt smoke")
    setTheme(Theme.AUTO)

    root = get_portable_root()
    data_dir = get_data_dir()
    if data_dir.parent != root:
        raise RuntimeError("The portable data directory escaped the app root.")
    if getattr(sys, "frozen", False) and root != Path(sys.executable).resolve().parent:
        raise RuntimeError("The bundled executable did not resolve its own portable root.")

    window = FluentWindow()
    window.resize(640, 480)
    window.show()
    app.processEvents()
    if not window.isVisible():
        return 1
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
