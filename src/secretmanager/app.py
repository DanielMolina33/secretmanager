import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
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
    icon_path = Path(__file__).parent / "resources" / "icons" / "secretmanager.png"
    application_icon = QIcon(str(icon_path))
    app.setWindowIcon(application_icon)

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
        from .settings_config import app_config, load_app_config
        from .localization.language_manager import LanguageManager
        from .ui.main_window import MainWindow

        load_app_config()
        language_manager = LanguageManager(app, app_config.language.value)
        window = MainWindow()
        window.setWindowIcon(application_icon)
        window.language_manager = language_manager
        instance.activated.connect(lambda: _activate_window(window))
        window.show()
        return app.exec()
    finally:
        instance.close()


if __name__ == "__main__":  
    raise SystemExit(main())
