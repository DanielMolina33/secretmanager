from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon as FIF,
    IconWidget,
    PrimaryPushButton,
    SimpleCardWidget,
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
        card.setMinimumSize(420, 360)

        card_layout = QVBoxLayout(card)

        card_layout.setContentsMargins(
            48,
            44,
            48,
            44,
        )

        card_layout.setSpacing(14)

        title = SubtitleLabel(
            QCoreApplication.translate("SecretManager", 'ui.vault_locked'),
            card,
        )
        title.pixelFontSize = 22

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        description = BodyLabel(
            QCoreApplication.translate("SecretManager", 'ui.unlock_the_vault_to_access_your_secrets'),
            card,
        )

        description.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        description.setWordWrap(True)

        unlock_button = PrimaryPushButton(
            FIF.POWER_BUTTON,
            QCoreApplication.translate("SecretManager", 'ui.unlock'),
            card,
        )
        unlock_button.setFixedSize(160, 44)

        unlock_button.clicked.connect(
            on_unlock
        )

        icon_background = SimpleCardWidget(card)
        icon_background.setFixedSize(88, 88)
        icon_background.setBorderRadius(44)

        icon_layout = QVBoxLayout(icon_background)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon = IconWidget(FIF.VPN, icon_background)
        icon.setFixedSize(52, 52)
        icon_layout.addWidget(
            icon,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        card_layout.addWidget(
            icon_background,
            alignment=Qt.AlignmentFlag.AlignCenter,
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




