from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QKeySequenceEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    ComboBoxSettingCard,
    FluentIcon as FIF,
    PushButton,
    PushSettingCard,
    SettingCard,
    SettingCardGroup,
    ScrollArea,
    SwitchSettingCard,
    Theme,
)
from ...settings_config import app_config, restore_app_config_defaults
from ..components.dialog_base import ConfirmationDialog


class SettingsPage(QWidget):
    themeChanged = Signal(int)
    micaChanged = Signal(bool)
    configureRecoveryRequested = Signal()
    disableRecoveryRequested = Signal()
    changeMasterPasswordRequested = Signal()
    settingsRestored = Signal()

    def __init__(self, parent=None, *, mica_available=False):
        super().__init__(parent)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = ScrollArea(self)
        self.scroll_widget = QWidget()
        layout = QVBoxLayout(self.scroll_widget)
        layout.setContentsMargins(70, 50, 70, 50)
        layout.setSpacing(20)

        personalization_group = SettingCardGroup(QCoreApplication.translate("SecretManager", 'ui.personalization'), self.scroll_widget)
        self.language_card = ComboBoxSettingCard(
            configItem=app_config.language,
            icon=FIF.LANGUAGE,
            title=QCoreApplication.translate("SecretManager", 'ui.application_language'),
            content=QCoreApplication.translate("SecretManager", 'ui.the_change_will_take_effect_the_next_time_you_start'),
            texts=[QCoreApplication.translate("SecretManager", 'ui.spanish'), QCoreApplication.translate("SecretManager", 'ui.english'), QCoreApplication.translate("SecretManager", 'ui.system')],
            parent=personalization_group,
        )
        personalization_group.addSettingCard(self.language_card)

        self.mica_card = SwitchSettingCard(
            configItem=app_config.micaEnabled,
            icon=FIF.TRANSPARENT,
            title=QCoreApplication.translate("SecretManager", 'ui.mica_effect'),
            content=QCoreApplication.translate("SecretManager", 'ui.applies_a_semi_transparent_material_to_windows_and_s'),
            parent=personalization_group,
        )
        self.mica_card.switchButton.setEnabled(mica_available)
        if not mica_available:
            self.mica_card.switchButton.setToolTip(
                QCoreApplication.translate("SecretManager", 'ui.mica_is_only_available_on_windows_11')
            )
        self.mica_card.checkedChanged.connect(self.micaChanged)
        personalization_group.addSettingCard(self.mica_card)

        theme_texts = {
            Theme.LIGHT: QCoreApplication.translate("SecretManager", 'ui.light'),
            Theme.DARK: QCoreApplication.translate("SecretManager", 'ui.dark'),
            Theme.AUTO: QCoreApplication.translate("SecretManager", 'ui.use_system_setting'),
        }
        theme_options = app_config.themeMode.options
        self.theme_card = ComboBoxSettingCard(
            configItem=app_config.themeMode,
            icon=FIF.BRUSH,
            title=QCoreApplication.translate("SecretManager", 'ui.application_theme'),
            content=QCoreApplication.translate("SecretManager", 'ui.change_the_appearance_of_the_application'),
            texts=[theme_texts[option] for option in theme_options],
            parent=personalization_group,
        )
        self.theme_card.comboBox.currentIndexChanged.connect(self._emit_theme_changed)
        personalization_group.addSettingCard(self.theme_card)

        behavior_group = SettingCardGroup(QCoreApplication.translate("SecretManager", 'ui.behavior'), self.scroll_widget)
        self.auto_lock_card = ComboBoxSettingCard(
            configItem=app_config.autoLockMinutes,
            icon=FIF.POWER_BUTTON,
            title=QCoreApplication.translate("SecretManager", 'ui.auto_lock_after_inactivity'),
            content=QCoreApplication.translate("SecretManager", 'ui.locks_the_vault_after_a_period_of_inactivity'),
            texts=[
                QCoreApplication.translate("SecretManager", 'ui.1_minute'),
                QCoreApplication.translate("SecretManager", 'ui.5_minutes'),
                QCoreApplication.translate("SecretManager", 'ui.10_minutes'),
                QCoreApplication.translate("SecretManager", 'ui.15_minutes'),
                QCoreApplication.translate("SecretManager", 'ui.30_minutes'),
            ],
            parent=behavior_group,
        )
        behavior_group.addSettingCard(self.auto_lock_card)

        self.clipboard_history_card = SwitchSettingCard(
            configItem=app_config.clipboardHistoryAllowed,
            icon=FIF.COPY,
            title=QCoreApplication.translate("SecretManager", 'ui.include_copied_items_in_clipboard_history'),
            content=QCoreApplication.translate("SecretManager", 'ui.allows_copied_names_values_and_recovery_kits_to_appe'),
            parent=behavior_group,
        )
        behavior_group.addSettingCard(self.clipboard_history_card)
        self.clipboard_clear_card = ComboBoxSettingCard(
            configItem=app_config.clipboardClearAfter,
            icon=FIF.DELETE,
            title=QCoreApplication.translate("SecretManager", 'ui.clear_clipboard_automatically'),
            content=QCoreApplication.translate("SecretManager", 'ui.clears_a_copied_name_or_value_after_the_selected_tim'),
            texts=[
                QCoreApplication.translate("SecretManager", 'ui.never'),
                QCoreApplication.translate("SecretManager", 'ui.10_seconds'),
                QCoreApplication.translate("SecretManager", 'ui.20_seconds'),
                QCoreApplication.translate("SecretManager", 'ui.30_seconds'),
                QCoreApplication.translate("SecretManager", 'ui.1_minute'),
                QCoreApplication.translate("SecretManager", 'ui.2_minutes'),
                QCoreApplication.translate("SecretManager", 'ui.5_minutes'),
            ],
            parent=behavior_group,
        )
        behavior_group.addSettingCard(self.clipboard_clear_card)

        self.shortcut_card = SettingCard(
            icon=FIF.POWER_BUTTON,
            title=QCoreApplication.translate("SecretManager", 'ui.vault_lock_shortcut'),
            content=QCoreApplication.translate("SecretManager", 'ui.select_the_field_and_press_a_combination_with_ctrl_a'),
            parent=behavior_group,
        )
        self.shortcut_edit = QKeySequenceEdit(
            QKeySequence.fromString(
                str(app_config.lockShortcut.value),
                QKeySequence.SequenceFormat.PortableText,
            ),
            self.shortcut_card,
        )
        self.shortcut_edit.setMaximumSequenceLength(1)
        self.shortcut_edit.setClearButtonEnabled(False)
        self.shortcut_edit.setFixedWidth(175)
        self.shortcut_edit.setAccessibleName(QCoreApplication.translate("SecretManager", 'ui.vault_lock_shortcut'))
        self.shortcut_card.hBoxLayout.addWidget(self.shortcut_edit)
        self.shortcut_edit.editingFinished.connect(self._save_lock_shortcut)
        app_config.lockShortcut.valueChanged.connect(self._sync_lock_shortcut)
        behavior_group.addSettingCard(self.shortcut_card)

        security_group = SettingCardGroup(QCoreApplication.translate("SecretManager", 'ui.security'), self.scroll_widget)
        self.change_password_card = PushSettingCard(
            text=QCoreApplication.translate("SecretManager", 'ui.change'),
            icon=FIF.EDIT,
            title=QCoreApplication.translate("SecretManager", 'ui.master_password'),
            content=QCoreApplication.translate("SecretManager", 'ui.change_the_password_that_protects_your_vault'),
            parent=security_group,
        )
        self.change_password_card.clicked.connect(self.changeMasterPasswordRequested)
        security_group.addSettingCard(self.change_password_card)

        self.recovery_card = PushSettingCard(
            text=QCoreApplication.translate("SecretManager", 'ui.set_up'),
            icon=FIF.CERTIFICATE,
            title=QCoreApplication.translate("SecretManager", 'ui.recovery_kit'),
            content=QCoreApplication.translate("SecretManager", 'ui.not_configured_lets_you_recover_the_vault_if_you_los'),
            parent=security_group,
        )
        self.recovery_card.clicked.connect(self.configureRecoveryRequested)
        security_group.addSettingCard(self.recovery_card)

        self.disable_recovery_card = PushSettingCard(
            text=QCoreApplication.translate("SecretManager", 'ui.disable'),
            icon=FIF.DELETE,
            title=QCoreApplication.translate("SecretManager", 'ui.disable_recovery_kit_02f31d'),
            content=QCoreApplication.translate("SecretManager", 'ui.removes_the_current_kit_your_master_password_will_co'),
            parent=security_group,
        )
        self.disable_recovery_card.clicked.connect(self.disableRecoveryRequested)
        security_group.addSettingCard(self.disable_recovery_card)

        layout.addWidget(personalization_group)
        layout.addWidget(behavior_group)
        layout.addWidget(security_group)

        layout.addSpacing(24)
        reset_layout = QVBoxLayout()
        reset_layout.setContentsMargins(0, 0, 0, 0)
        reset_layout.setSpacing(8)
        reset_layout.addWidget(
            CaptionLabel(
                QCoreApplication.translate("SecretManager", 'ui.resets_application_preferences_it_does_not_change_th'),
                self.scroll_widget,
            )
        )
        self.reset_settings_button = PushButton(
            QCoreApplication.translate("SecretManager", 'ui.reset'),
            self.scroll_widget,
        )
        self.reset_settings_button.clicked.connect(self._confirm_restore_defaults)
        reset_layout.addWidget(
            self.reset_settings_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        layout.addLayout(reset_layout)
        layout.addStretch(1)

        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.enableTransparentBackground()
        page_layout.addWidget(self.scroll_area)
        self.set_recovery_state(False, False)

    def _save_lock_shortcut(self) -> None:
        sequence = self.shortcut_edit.keySequence()
        portable_text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        modifiers = portable_text.split('+')[:-1]
        if not portable_text or not {'Ctrl', 'Alt', 'Meta'}.intersection(modifiers):
            self._sync_lock_shortcut(app_config.lockShortcut.value)
            return

        from qfluentwidgets import qconfig

        qconfig.set(app_config.lockShortcut, portable_text)

    def _sync_lock_shortcut(self, portable_text: str) -> None:
        sequence = QKeySequence.fromString(
            str(portable_text),
            QKeySequence.SequenceFormat.PortableText,
        )
        if sequence.isEmpty():
            sequence = QKeySequence(app_config.lockShortcut.default)
        self.shortcut_edit.setKeySequence(sequence)

    def _confirm_restore_defaults(self) -> None:
        dialog = ConfirmationDialog(
            QCoreApplication.translate("SecretManager", 'ui.reset_settings'),
            QCoreApplication.translate("SecretManager", 'ui.application_preferences_will_be_restored_to_their_de'),
            self,
            confirm_text=QCoreApplication.translate("SecretManager", 'ui.reset'),
            cancel_text=QCoreApplication.translate("SecretManager", 'ui.cancel_56fc52'),
        )
        if dialog.exec():
            restore_app_config_defaults()
            self.settingsRestored.emit()

    def set_master_password_state(self, unlocked: bool) -> None:
        self.change_password_card.button.setEnabled(unlocked)

    def set_recovery_state(self, configured: bool, unlocked: bool) -> None:
        self.recovery_card.button.setText(QCoreApplication.translate("SecretManager", 'ui.regenerate') if configured else QCoreApplication.translate("SecretManager", 'ui.set_up'))
        if configured:
            self.recovery_card.setContent(
                QCoreApplication.translate("SecretManager", 'ui.configured_generating_a_new_one_invalidates_the_prev')
            )
        else:
            self.recovery_card.setContent(
                QCoreApplication.translate("SecretManager", 'ui.not_configured_lets_you_recover_the_vault_if_you_los')
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