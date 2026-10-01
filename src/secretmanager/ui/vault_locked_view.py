from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    IconWidget,
    PrimaryPushButton,
    SubtitleLabel,

)


class VaultLockedView(QWidget):
    def __init__(
        self,
        on_unlock,
        parent=None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            40,
            40,
            40,
            40,
        )

        layout.addStretch()

        card = CardWidget(self)
        card.setMinimumSize(420, 300)

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(
            48,
            44,
            48,
            44,
        )

        card_layout.setSpacing(14)

        icon = IconWidget(
            FIF.POWER_BUTTON,
            card,
        )

        icon.setFixedSize(48, 48)

        title = SubtitleLabel(
            "Bóveda bloqueada",
            card,
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        description = BodyLabel(
            "Desbloquea la bóveda para acceder "
            "a tus secretos.",
            card,
        )

        description.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        description.setWordWrap(True)

        unlock_button = PrimaryPushButton(
            FIF.POWER_BUTTON,
            "Desbloquear",
            card,
        )
        unlock_button.setFixedSize(160, 44)

        unlock_button.clicked.connect(
            on_unlock
        )

        card_layout.addWidget(
            icon,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        card_layout.addWidget(
            title,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        card_layout.addWidget(
            description,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        card_layout.addSpacing(8)

        card_layout.addWidget(
            unlock_button,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        layout.addWidget(
            card,
            alignment=(
                Qt.AlignmentFlag.AlignCenter
            ),
        )

        layout.addStretch()