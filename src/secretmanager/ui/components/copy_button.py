"""Factory for an icon-only Fluent copy button with confirmation feedback."""

from PySide6.QtCore import QCoreApplication, QTimer

from qfluentwidgets import FluentIcon as FIF, ToolButton

from ...services.clipboard import copy_text


def create_copy_button(
    text_provider, parent=None, accessible_name=None, *, auto_clear=True
):
    if accessible_name is None:
        accessible_name = QCoreApplication.translate("SecretManager", "ui.copy")
    button = ToolButton(FIF.COPY, parent)
    button.setFixedSize(32, 32)
    button.setAccessibleName(accessible_name)
    button.setToolTip(accessible_name)
    feedback_timer = QTimer(button)
    feedback_timer.setSingleShot(True)

    def restore_copy_icon():
        button.setIcon(FIF.COPY)
        button.setToolTip(accessible_name)

    def copy_value():
        text = text_provider()
        if not text:
            return
        copy_text(text, auto_clear=auto_clear)
        feedback_timer.stop()
        button.setIcon(FIF.ACCEPT)
        button.setToolTip(QCoreApplication.translate("SecretManager", 'ui.copied'))
        feedback_timer.start(1200)

    button.clicked.connect(copy_value)
    feedback_timer.timeout.connect(restore_copy_icon)
    return button
