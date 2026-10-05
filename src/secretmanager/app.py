import logging
import sys

from PySide6.QtWidgets import QApplication

from .instance import InstanceCoordinator


def _activate_window(window) -> None:
    if window.isMinimized():
        window.showNormal()
    elif not window.isVisible():
        window.show()
    window.raise_()
    window.activateWindow()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Secret Manager")

    instance = InstanceCoordinator()
    try:
        is_primary = instance.start()
    except Exception:
        logging.getLogger(__name__).exception(
            "Could not establish the single application instance."
        )
        instance.close()
        return 1

    if not is_primary:
        instance.request_activation()
        instance.close()
        return 0

    try:
        # Settings and vault services are initialized only after the process
        # owns the global instance lock.
        from .settings_config import load_app_config
        from .ui.main_window import MainWindow

        load_app_config()
        window = MainWindow()
        instance.activated.connect(lambda: _activate_window(window))
        window.show()
        return app.exec()
    finally:
        instance.close()


if __name__ == "__main__":
    raise SystemExit(main())
