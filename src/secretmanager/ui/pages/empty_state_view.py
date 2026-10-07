from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, FluentIcon as FIF, IconWidget, PrimaryPushButton, SubtitleLabel


class EmptyStateView(QWidget):
    def __init__(self, title, description, action_text, on_action, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(1)

        content = QWidget(self)
        content.setMinimumWidth(0)
        content.setMaximumWidth(480)
        content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        icon = IconWidget(FIF.FOLDER, content)
        icon.setFixedSize(48, 48)
        content_layout.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        title_label = SubtitleLabel(title, content)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        description_label = BodyLabel(description, content)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setWordWrap(True)
        description_label.setMinimumWidth(0)
        description_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        content_layout.addWidget(description_label)

        action_button = PrimaryPushButton(FIF.ADD, action_text, content)
        action_button.clicked.connect(on_action)
        content_layout.addSpacing(8)
        content_layout.addWidget(action_button, alignment=Qt.AlignmentFlag.AlignCenter)

        content_row = QHBoxLayout()
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.addStretch()
        content_row.addWidget(content, 1)
        content_row.addStretch()
        layout.addLayout(content_row)

        layout.addStretch(1)