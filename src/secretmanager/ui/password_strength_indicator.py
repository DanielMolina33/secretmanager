from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ProgressBar
from zxcvbn import zxcvbn

from ..domain.master_password import normalize_master_password


_STRENGTH_LABELS = (
    "Muy débil",
    "Débil",
    "Razonable",
    "Fuerte",
    "Muy fuerte",
)
_GUESS_THRESHOLDS = (10**7, 10**11, 10**14, 10**16)


class PasswordStrengthIndicator(QWidget):
    """Local, advisory strength estimate displayed with Fluent controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.level_label = CaptionLabel(self)
        self.level_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_bar = ProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout.addWidget(self.level_label)
        layout.addWidget(self.progress_bar)
        self.hide()

    def set_password(self, password: str) -> None:
        if not password:
            self.level_label.clear()
            self.progress_bar.setValue(0)
            self.hide()
            return

        guesses = zxcvbn(normalize_master_password(password))["guesses"]
        level = sum(guesses >= threshold for threshold in _GUESS_THRESHOLDS)
        self.level_label.setText(_STRENGTH_LABELS[level])
        self.progress_bar.setValue((level + 1) * 20)
        self.show()
