from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import (
    ComboBoxSettingCard,
    FluentIcon as FIF,
    SettingCardGroup,
    SwitchSettingCard,
    Theme,
    qconfig,
)


class SettingsPage(QWidget):
    themeChanged = Signal(int)
    micaChanged = Signal(bool)

    def __init__(self, parent=None, *, mica_available=False):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 16)
        layout.setSpacing(0)

        group = SettingCardGroup('Personalización', self)

        self.mica_card = SwitchSettingCard(
            icon=FIF.TRANSPARENT,
            title='Efecto Mica',
            content='Aplica un material semitransparente a las ventanas y superficies.',
            parent=group,
        )
        self.mica_card.setChecked(mica_available)
        self.mica_card.switchButton.setEnabled(mica_available)
        if not mica_available:
            self.mica_card.switchButton.setToolTip(
                'El efecto Mica solo está disponible en Windows 11.'
            )
        self.mica_card.checkedChanged.connect(self.micaChanged)
        group.addSettingCard(self.mica_card)

        theme_texts = {
            Theme.LIGHT: 'Claro',
            Theme.DARK: 'Oscuro',
            Theme.AUTO: 'Usar configuración del sistema',
        }
        theme_options = qconfig.themeMode.options

        self.theme_card = ComboBoxSettingCard(
            configItem=qconfig.themeMode,
            icon=FIF.BRUSH,
            title='Tema de la aplicación',
            content='Cambia la apariencia de la aplicación.',
            texts=[theme_texts[option] for option in theme_options],
            parent=group,
        )
        self.theme_card.comboBox.currentIndexChanged.connect(
            self._emit_theme_changed
        )
        group.addSettingCard(self.theme_card)

        layout.addWidget(group)
        layout.addStretch(1)

    def _emit_theme_changed(self, index):
        option = self.theme_card.comboBox.itemData(index)
        theme_indices = {
            Theme.AUTO: 0,
            Theme.LIGHT: 1,
            Theme.DARK: 2,
        }
        self.themeChanged.emit(theme_indices[option])