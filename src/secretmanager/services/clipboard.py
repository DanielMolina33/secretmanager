"""Copy text and safely clear SecretManager clipboard entries when configured."""

import sys
import uuid

from PySide6.QtCore import QByteArray, QMimeData, QTimer, Qt
from PySide6.QtWidgets import QApplication

from ..settings_config import app_config

_OWNER_MIME = "application/x-secretmanager-clipboard-entry"
_clear_timer = None
_pending_token = None
_clipboard = None
_paused_cleanup_ms = None


def copy_text(text: str, *, auto_clear: bool = True) -> None:
    """Copy text and optionally schedule guarded cleanup per user settings."""
    global _clear_timer, _pending_token, _clipboard, _paused_cleanup_ms

    application = QApplication.instance()
    if application is None:
        raise RuntimeError("Clipboard operations require a running QApplication")

    clipboard = application.clipboard()
    if _clipboard is None:
        _clipboard = clipboard
        clipboard.dataChanged.connect(_on_clipboard_changed)
        if sys.platform == "darwin":
            application.applicationStateChanged.connect(_on_application_state_changed)
    if _clear_timer is not None:
        _clear_timer.stop()
    _pending_token = None
    _paused_cleanup_ms = None

    mime_data = QMimeData()
    mime_data.setText(text)
    if not app_config.clipboardHistoryAllowed.value:
        _mark_sensitive(mime_data)

    delay_seconds = int(app_config.clipboardClearAfter.value) if auto_clear else 0
    if delay_seconds > 0:
        token = uuid.uuid4().hex.encode("ascii")
        mime_data.setData(_OWNER_MIME, QByteArray(token))
        _pending_token = token
        if _clear_timer is None:
            _clear_timer = QTimer(application)
            _clear_timer.setSingleShot(True)
            _clear_timer.timeout.connect(_clear_if_unchanged)

    clipboard.setMimeData(mime_data)
    if delay_seconds > 0:
        _clear_timer.start(delay_seconds * 1000)


def _on_clipboard_changed() -> None:
    """Cancel cleanup if another clipboard write replaced our marked item."""
    global _pending_token, _paused_cleanup_ms
    if _pending_token is None:
        return

    current_data = _clipboard.mimeData()
    if current_data is None or not current_data.hasFormat(_OWNER_MIME):
        _cancel_pending_cleanup()
        return

    current_token = bytes(current_data.data(_OWNER_MIME))
    if current_token != _pending_token:
        _cancel_pending_cleanup()


def _on_application_state_changed(state) -> None:
    """Pause cleanup while macOS defers external clipboard notifications."""
    global _paused_cleanup_ms
    if _pending_token is None or _clear_timer is None:
        return

    if state != Qt.ApplicationState.ApplicationActive:
        if _clear_timer.isActive():
            _paused_cleanup_ms = max(1, _clear_timer.remainingTime())
            _clear_timer.stop()
        return

    # Qt reports external clipboard changes on macOS when this app is activated.
    _on_clipboard_changed()
    if _pending_token is not None and _paused_cleanup_ms is not None:
        _clear_timer.start(_paused_cleanup_ms)
        _paused_cleanup_ms = None


def _cancel_pending_cleanup() -> None:
    global _pending_token, _paused_cleanup_ms
    if _clear_timer is not None:
        _clear_timer.stop()
    _pending_token = None
    _paused_cleanup_ms = None


def _clear_if_unchanged() -> None:
    global _pending_token, _paused_cleanup_ms
    if _pending_token is None:
        return

    # Clipboard access here is write-only. Changes are tracked via dataChanged.
    _clipboard.clear()
    _pending_token = None
    _paused_cleanup_ms = None


def _mark_sensitive(mime_data: QMimeData) -> None:
    if sys.platform == "win32":
        # Qt bridges these MIME names to registered Windows clipboard formats.
        mime_data.setData(
            'application/x-qt-windows-mime;value="CanIncludeInClipboardHistory"',
            QByteArray(4, 0),
        )
        mime_data.setData(
            'application/x-qt-windows-mime;value="CanUploadToCloudClipboard"',
            QByteArray(4, 0),
        )
    elif sys.platform == "darwin":
        # Qt transports this custom format; managers that recognize the
        # NSPasteboard concealed marker can omit the item from history.
        mime_data.setData("org.nspasteboard.ConcealedType", QByteArray(b"1"))
    else:
        # KDE's convention is best-effort; other clipboard managers may ignore it.
        mime_data.setData("x-kde-passwordManagerHint", QByteArray(b"secret"))
