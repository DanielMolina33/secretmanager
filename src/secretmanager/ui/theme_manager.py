from importlib import import_module
from threading import Thread

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    SystemThemeListener,
    Theme,
    isDarkTheme,
    qconfig,
    setTheme,
    setThemeColor,
)
from qfluentwidgets.common.style_sheet import updateStyleSheet
from qframelesswindow.utils import getSystemAccentColor

from ..settings_config import app_config

try:
    # winaccent is a Windows-only dependency; import by name to keep this
    # module usable on macOS and Linux.
    winaccent = import_module("winaccent")
except ImportError:
    winaccent = None


class _ThemeSignals(QObject):
    systemColorsChanged = Signal()


class ThemeManager:
    """Owns Fluent theme selection and system appearance synchronization."""

    MODES = ("system", "light", "dark")
    THEME_MODES = {
        Theme.AUTO: "system",
        Theme.LIGHT: "light",
        Theme.DARK: "dark",
    }

    def __init__(self, parent):
        self.mode = self.THEME_MODES[app_config.themeMode.value]
        self.listener = SystemThemeListener(parent)
        self.listener.systemThemeChanged.connect(self._system_theme_changed)
        self.listener.start()

        self._signals = _ThemeSignals(parent)
        self._signals.systemColorsChanged.connect(
            self.apply_system_accent,
            Qt.ConnectionType.QueuedConnection,
        )
        self._closed = False
        self._start_windows_color_listener()
        self.apply()

    def _start_windows_color_listener(self):
        if winaccent is None:
            return

        # winaccent exposes its appearance listener as a blocking loop. Keep
        # it on a daemon thread and relay changes through the queued Qt signal.
        Thread(
            target=winaccent.on_appearance_changed,
            args=(self._on_windows_colors_changed,),
            daemon=True,
            name="winaccent-appearance-listener",
        ).start()

    def _on_windows_colors_changed(self):
        if not self._closed:
            self._signals.systemColorsChanged.emit()

    def set_mode_from_index(self, index):
        self.mode = self.MODES[index]
        self.apply()

    def apply(self):
        setTheme(
            {
                "system": Theme.AUTO,
                "light": Theme.LIGHT,
                "dark": Theme.DARK,
            }[self.mode]
        )
        self.apply_system_accent()

    def apply_system_accent(self):
        app = QApplication.instance()
        if app is None:
            return

        platform_name = app.platformName().lower()
        if platform_name == "windows" and winaccent is not None:
            accent = self._windows_accent_color()
        elif platform_name in ("windows", "cocoa"):
            accent = getSystemAccentColor()
        else:
            accent = app.palette().color(QPalette.ColorRole.Highlight)

        if accent.isValid():
            setThemeColor(accent, save=False)

    def _windows_accent_color(self):
        if winaccent is not None:
            try:
                shade = (
                    winaccent.accent_light_2
                    if isDarkTheme()
                    else winaccent.accent_dark_1
                )
                return QColor(shade)
            except Exception:
                pass

        return getSystemAccentColor()

    def _system_theme_changed(self):
        updateStyleSheet()
        qconfig.themeChangedFinished.emit()
        self.apply_system_accent()

    def close(self):
        self._closed = True
        self.listener.terminate()
        self.listener.deleteLater()
        self._signals.deleteLater()

