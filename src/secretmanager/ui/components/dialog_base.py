"""Reusable dialog behavior built on QFluentWidgets dialog components."""

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from qfluentwidgets import MessageBox, MessageBoxBase, ScrollArea



def _owner_window(parent):
    """Return the containing top-level window used for dialog masking."""
    return parent.window() if isinstance(parent, QWidget) else parent


class AppMessageBoxBase(MessageBoxBase):
    """Shared behavior for SecretManager forms using Fluent MessageBoxBase."""

    def __init__(
        self,
        parent=None,
        *,
        minimum_width: int = 420,
        confirm_text: str | None = None,
        cancel_text: str | None = None,
    ):
        super().__init__(_owner_window(parent))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.yesButton.setText(
            QCoreApplication.translate("SecretManager", "ui.accept")
            if confirm_text is None else confirm_text
        )
        self.cancelButton.setText(
            QCoreApplication.translate("SecretManager", "ui.cancel")
            if cancel_text is None else cancel_text
        )
        if minimum_width:
            self.widget.setMinimumWidth(minimum_width)

        old_view_layout = self.viewLayout
        self.vBoxLayout.removeItem(old_view_layout)
        old_view_layout.deleteLater()

        self.content_widget = QWidget()
        self.viewLayout = QVBoxLayout(self.content_widget)
        self.viewLayout.setContentsMargins(24, 24, 24, 24)
        self.viewLayout.setSpacing(12)

        self.scroll_area = ScrollArea(self.widget)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setWidget(self.content_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.enableTransparentBackground()
        self.vBoxLayout.insertWidget(0, self.scroll_area, 1)

        # Keep the existing screen-height rule common to every form dialog.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available_height = screen.availableGeometry().height()
            self.widget.setMaximumHeight(max(1, int(available_height * 0.85)))


class ConfirmationDialog(MessageBox):
    """Standard masked confirmation with consistent parent, size, and wrapping."""

    WIDTH = 420
    HORIZONTAL_CONTENT_MARGIN = 24

    def __init__(
        self,
        title: str,
        content: str,
        parent=None,
        *,
        confirm_text: str | None = None,
        cancel_text: str | None = None,
    ):
        super().__init__(title, content, _owner_window(parent))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.yesButton.setText(
            QCoreApplication.translate("SecretManager", "ui.accept")
            if confirm_text is None else confirm_text
        )
        self.cancelButton.setText(
            QCoreApplication.translate("SecretManager", "ui.cancel")
            if cancel_text is None else cancel_text
        )

        content_width = self.WIDTH - 2 * self.HORIZONTAL_CONTENT_MARGIN
        for label in (self.titleLabel, self.contentLabel):
            label.setWordWrap(True)
            label.setFixedWidth(content_width)

        # MessageBox sizes itself from unwrapped text. Constrain the content
        # first, then let the Fluent layout determine the height needed by it.
        self.widget.setMinimumHeight(0)
        self.widget.setMaximumHeight(16_777_215)
        self.widget.setFixedWidth(self.WIDTH)
        self.widget.layout().activate()
        self.widget.adjustSize()
        content_height = self.widget.layout().sizeHint().height()
        self.widget.setFixedSize(self.WIDTH, content_height)
