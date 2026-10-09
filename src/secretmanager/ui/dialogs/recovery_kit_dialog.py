from PySide6.QtCore import QCoreApplication
from ...localization.localization import master_password_policy_text
from PySide6.QtWidgets import QHBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, LineEdit, PasswordLineEdit, SubtitleLabel

from ...domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from ..components.password_strength_indicator import PasswordStrengthIndicator
from ..components.copy_button import create_copy_button
from ..components.dialog_base import AppMessageBoxBase


class MasterPasswordConfirmationDialog(AppMessageBoxBase):
    def __init__(self, parent=None, *, title: str, content: str, action_text: str):
        super().__init__(parent, minimum_width=420, confirm_text=action_text)
        self._validator = None
        self.authenticated_value = None
        self.title_label = SubtitleLabel(title, self)
        self.content_label = CaptionLabel(content, self)
        self.content_label.setWordWrap(True)
        self.password_input = PasswordLineEdit(self)
        self.password_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.master_password'))
        self.error_label = self._create_error_label()
        self.password_input.textChanged.connect(self._clear_error)
        self.password_input.returnPressed.connect(self.yesButton.click)
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.content_label)
        self.viewLayout.addWidget(self.password_input)
        self.viewLayout.addWidget(self.error_label)
        QWidget.setTabOrder(self.password_input, self.yesButton)

    @staticmethod
    def _create_error_label():
        label = CaptionLabel()
        label.setTextColor("#c42b1c", "#ff99a4")
        label.setWordWrap(True)
        label.hide()
        return label

    def set_validator(self, validator) -> None:
        self._validator = validator

    def _clear_error(self, _text="") -> None:
        self.error_label.clear()
        self.error_label.hide()

    def clear_sensitive_data(self) -> None:
        self.password_input.clear()

    def validate(self) -> bool:
        if not self.password_input.text():
            self.error_label.setText(QCoreApplication.translate("SecretManager", 'ui.enter_the_master_password'))
            self.error_label.show()
            self.password_input.setFocus()
            return False
        if self._validator is None:
            return True
        try:
            self.authenticated_value = self._validator(self.password_input.text())
        except ValueError:
            self.error_label.setText(QCoreApplication.translate("SecretManager", 'ui.the_master_password_is_incorrect'))
            self.error_label.show()
            self.password_input.setFocus()
            return False
        except OSError:
            self.error_label.setText(QCoreApplication.translate("SecretManager", 'ui.could_not_save_the_change_try_again'))
            self.error_label.show()
            return False
        except RuntimeError:
            self.error_label.setText(QCoreApplication.translate("SecretManager", 'ui.the_vault_was_locked_unlock_it_and_try_again'))
            self.error_label.show()
            return False
        return True


class RecoveryKitDisplayDialog(AppMessageBoxBase):
    def __init__(self, code: str, commit, parent=None, *, replacing: bool = False):
        super().__init__(
            parent,
            minimum_width=460,
            confirm_text=QCoreApplication.translate("SecretManager", 'ui.i_saved_it'),
        )
        self._code = code
        self._commit = commit
        title = QCoreApplication.translate("SecretManager", 'ui.new_recovery_kit') if replacing else QCoreApplication.translate("SecretManager", 'ui.recovery_kit_fb8c2a')
        description = (
            QCoreApplication.translate("SecretManager", 'ui.the_current_kit_will_keep_working_until_you_confirm')
            if replacing
            else QCoreApplication.translate("SecretManager", 'ui.save_this_code_in_a_safe_place_it_will_only_become_a')
        )
        self.title_label = SubtitleLabel(title, self)
        self.content_label = CaptionLabel(description, self)
        self.content_label.setWordWrap(True)
        self.code_input = LineEdit(self)
        self.code_input.setText(code)
        self.code_input.setReadOnly(True)
        code_row = QWidget(self)
        code_row_layout = QHBoxLayout(code_row)
        code_row_layout.setContentsMargins(0, 0, 0, 0)
        code_row_layout.setSpacing(8)
        code_row_layout.addWidget(self.code_input, 1)
        self.copy_button = create_copy_button(
            lambda: self._code,
            code_row,
            QCoreApplication.translate("SecretManager", 'ui.copy_recovery_kit'),
            auto_clear=False,
        )
        code_row_layout.addWidget(self.copy_button)
        self.save_label = CaptionLabel(QCoreApplication.translate("SecretManager", 'ui.continuing_confirms_that_you_saved_the_code'), self)
        self.error_label = MasterPasswordConfirmationDialog._create_error_label()
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.content_label)
        self.viewLayout.addWidget(code_row)
        self.viewLayout.addWidget(self.save_label)
        self.viewLayout.addWidget(self.error_label)
        QWidget.setTabOrder(self.code_input, self.copy_button)
        QWidget.setTabOrder(self.copy_button, self.yesButton)

    def clear_sensitive_data(self) -> None:
        self.code_input.clear()
        self._code = ""

    def validate(self) -> bool:
        try:
            self._commit()
        except (OSError, RuntimeError, ValueError):
            self.error_label.setText(QCoreApplication.translate("SecretManager", 'ui.could_not_save_the_kit_the_code_is_still_available_t'))
            self.error_label.show()
            return False
        return True


class RecoveryDialog(AppMessageBoxBase):
    def __init__(self, recover, parent=None):
        super().__init__(parent, minimum_width=460, confirm_text=QCoreApplication.translate("SecretManager", 'ui.recover'))
        self._recover = recover
        self.recovered_vault = None
        self.title_label = SubtitleLabel(QCoreApplication.translate("SecretManager", 'ui.recover_vault'), self)
        self.description_label = CaptionLabel(
            QCoreApplication.translate(
                "SecretManager",
                'ui.enter_your_recovery_kit_and_set_a_new_master_passwor',
            ),
            self,
        )
        self.description_label.setWordWrap(True)
        self.recovery_input = PasswordLineEdit(self)
        self.recovery_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.recovery_kit_fb8c2a'))
        self.recovery_error = self._create_error_label()
        self.new_password_input = PasswordLineEdit(self)
        self.new_password_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.new_master_password'))
        self.password_error = self._create_error_label()
        self.strength_indicator = PasswordStrengthIndicator(self)
        self.confirm_input = PasswordLineEdit(self)
        self.confirm_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.confirm_new_password'))
        self.confirm_error = self._create_error_label()
        self.operation_error = self._create_error_label()
        self.recovery_input.textChanged.connect(lambda _text: self._clear_error(self.recovery_error))
        self.new_password_input.textChanged.connect(self._on_new_password_changed)
        self.confirm_input.textChanged.connect(lambda _text: self._clear_error(self.confirm_error))
        QWidget.setTabOrder(self.recovery_input, self.new_password_input)
        QWidget.setTabOrder(self.new_password_input, self.confirm_input)
        QWidget.setTabOrder(self.confirm_input, self.yesButton)

        self.confirm_input.returnPressed.connect(self.yesButton.click)
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.description_label)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.recovery_input)
        self.viewLayout.addWidget(self.recovery_error)
        self.viewLayout.addWidget(self.new_password_input)
        self.viewLayout.addWidget(self.password_error)
        self.viewLayout.addWidget(self.strength_indicator)
        self.viewLayout.addWidget(self.confirm_input)
        self.viewLayout.addWidget(self.confirm_error)
        self.viewLayout.addWidget(self.operation_error)
        self.recovery_input.setFocus()

    @staticmethod
    def _create_error_label():
        label = CaptionLabel()
        label.setTextColor("#c42b1c", "#ff99a4")
        label.setWordWrap(True)
        label.hide()
        return label

    @staticmethod
    def _clear_error(label) -> None:
        label.clear()
        label.hide()

    def _on_new_password_changed(self, text: str) -> None:
        self._clear_error(self.password_error)
        if master_password_length(text) > MAX_MASTER_PASSWORD_CODE_POINTS:
            self.password_error.setText(
                QCoreApplication.translate("SecretManager", 'ui.the_master_password_cannot_exceed_1_characters').replace("%1", str(MAX_MASTER_PASSWORD_CODE_POINTS))
            )
            self.password_error.show()
            self.strength_indicator.set_password("")
            return
        self.strength_indicator.set_password(text)

    def clear_sensitive_data(self) -> None:
        self.recovery_input.clear()
        self.new_password_input.clear()
        self.confirm_input.clear()

    def validate(self) -> bool:
        if not self.recovery_input.text().strip():
            self.recovery_error.setText(QCoreApplication.translate("SecretManager", 'ui.enter_the_recovery_kit'))
            self.recovery_error.show()
            self.recovery_input.setFocus()
            return False
        try:
            validate_new_master_password(self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(master_password_policy_text(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        if normalize_master_password(self.new_password_input.text()) != normalize_master_password(
            self.confirm_input.text()
        ):
            self.confirm_error.setText(QCoreApplication.translate("SecretManager", 'ui.the_passwords_do_not_match'))
            self.confirm_error.show()
            self.confirm_input.setFocus()
            return False
        try:
            self.recovered_vault = self._recover(self.recovery_input.text(), self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(master_password_policy_text(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        except ValueError:
            self.recovery_error.setText(QCoreApplication.translate("SecretManager", 'ui.the_recovery_kit_is_invalid_or_has_already_been_used'))
            self.recovery_error.show()
            self.recovery_input.setFocus()
            return False
        except OSError:
            self.operation_error.setText(QCoreApplication.translate("SecretManager", 'ui.could_not_complete_recovery_try_again'))
            self.operation_error.show()
            return False
        return True