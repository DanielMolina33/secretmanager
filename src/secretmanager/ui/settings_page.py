from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBoxSettingCard,
    FluentIcon as FIF,
    PushSettingCard,
    SettingCardGroup,
    SwitchSettingCard,
    Theme,
)
from ..settings_config import app_config


class SettingsPage(QWidget):
    themeChanged = Signal(int)
    micaChanged = Signal(bool)
    configureRecoveryRequested = Signal()
    disableRecoveryRequested = Signal()
    changeMasterPasswordRequested = Signal()

    def __init__(self, parent=None, *, mica_available=False):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(20)

        personalization_group = SettingCardGroup('Personalización', self)
        self.mica_card = SwitchSettingCard(
            configItem=app_config.micaEnabled,
            icon=FIF.TRANSPARENT,
            title='Efecto Mica',
            content='Aplica un material semitransparente a las ventanas y superficies.',
            parent=personalization_group,
        )
        self.mica_card.switchButton.setEnabled(mica_available)
        if not mica_available:
            self.mica_card.switchButton.setToolTip(
                'El efecto Mica solo está disponible en Windows 11.'
            )
        self.mica_card.checkedChanged.connect(self.micaChanged)
        personalization_group.addSettingCard(self.mica_card)

        theme_texts = {
            Theme.LIGHT: 'Claro',
            Theme.DARK: 'Oscuro',
            Theme.AUTO: 'Usar configuración del sistema',
        }
        theme_options = app_config.themeMode.options
        self.theme_card = ComboBoxSettingCard(
            configItem=app_config.themeMode,
            icon=FIF.BRUSH,
            title='Tema de la aplicación',
            content='Cambia la apariencia de la aplicación.',
            texts=[theme_texts[option] for option in theme_options],
            parent=personalization_group,
        )
        self.theme_card.comboBox.currentIndexChanged.connect(self._emit_theme_changed)
        personalization_group.addSettingCard(self.theme_card)

        security_group = SettingCardGroup('Seguridad', self)
        self.change_password_card = PushSettingCard(
            text='Cambiar',
            icon=FIF.EDIT,
            title='Contraseña maestra',
            content='Cambia la contraseña que protege tu bóveda.',
            parent=security_group,
        )
        self.change_password_card.clicked.connect(self.changeMasterPasswordRequested)
        security_group.addSettingCard(self.change_password_card)

        self.recovery_card = PushSettingCard(
            text='Configurar',
            icon=FIF.CERTIFICATE,
            title='Kit de recuperación',
            content='No configurado. Permite recuperar la bóveda si pierdes la contraseña maestra.',
            parent=security_group,
        )
        self.recovery_card.clicked.connect(self.configureRecoveryRequested)
        security_group.addSettingCard(self.recovery_card)

        self.disable_recovery_card = PushSettingCard(
            text='Desactivar',
            icon=FIF.DELETE,
            title='Desactivar kit de recuperación',
            content='Quita el kit actual. La contraseña maestra seguirá funcionando.',
            parent=security_group,
        )
        self.disable_recovery_card.clicked.connect(self.disableRecoveryRequested)
        security_group.addSettingCard(self.disable_recovery_card)

        layout.addWidget(personalization_group)
        layout.addWidget(security_group)
        layout.addStretch(1)
        self.set_recovery_state(False, False)

    def set_master_password_state(self, unlocked: bool) -> None:
        self.change_password_card.button.setEnabled(unlocked)

    def set_recovery_state(self, configured: bool, unlocked: bool) -> None:
        self.recovery_card.button.setText('Regenerar' if configured else 'Configurar')
        if configured:
            self.recovery_card.setContent(
                'Configurado. Regenerarlo invalida el código anterior al guardar el nuevo.'
            )
        else:
            self.recovery_card.setContent(
                'No configurado. Permite recuperar la bóveda si pierdes la contraseña maestra.'
            )
        self.recovery_card.button.setEnabled(unlocked)
        self.disable_recovery_card.setVisible(configured)
        self.disable_recovery_card.button.setEnabled(unlocked)

    def _emit_theme_changed(self, index):
        option = self.theme_card.comboBox.itemData(index)
        theme_indices = {
            Theme.AUTO: 0,
            Theme.LIGHT: 1,
            Theme.DARK: 2,
        }
        self.themeChanged.emit(theme_indices[option])