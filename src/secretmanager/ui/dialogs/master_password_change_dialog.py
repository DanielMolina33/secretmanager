from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget
from ...localization.localization import master_password_policy_text
from qfluentwidgets import CaptionLabel, PasswordLineEdit, SubtitleLabel

from ...domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from ..components.password_strength_indicator import PasswordStrengthIndicator
from ..components.dialog_base import AppMessageBoxBase


class MasterPasswordChangeDialog(AppMessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent, minimum_width=420, confirm_text=QCoreApplication.translate("SecretManager", 'ui.change'))
        self._change_handler = None

        self.title_label = SubtitleLabel(QCoreApplication.translate("SecretManager", 'ui.change_master_password'), self)
        self.current_input = PasswordLineEdit(self)
        self.current_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.current_master_password'))
        self.current_error = self._create_error_label()
        self.current_input.textChanged.connect(lambda _text: self._clear_error(self.current_error))

        self.new_password_input = PasswordLineEdit(self)
        self.new_password_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.new_master_password'))
        self.password_error = self._create_error_label()
        self.strength_indicator = PasswordStrengthIndicator(self)
        self.new_password_input.textChanged.connect(self._on_new_password_changed)

        self.confirm_input = PasswordLineEdit(self)
        self.confirm_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.confirm_new_password'))
        self.confirm_error = self._create_error_label()
        self.confirm_input.textChanged.connect(lambda _text: self._clear_error(self.confirm_error))

        self.operation_error = self._create_error_label()
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.current_input)
        self.viewLayout.addWidget(self.current_error)
        self.viewLayout.addWidget(self.new_password_input)
        self.viewLayout.addWidget(self.password_error)
        self.viewLayout.addWidget(self.strength_indicator)
        self.viewLayout.addWidget(self.confirm_input)
        self.viewLayout.addWidget(self.confirm_error)
        self.viewLayout.addWidget(self.operation_error)
        QWidget.setTabOrder(self.current_input, self.new_password_input)
        QWidget.setTabOrder(self.new_password_input, self.confirm_input)
        QWidget.setTabOrder(self.confirm_input, self.yesButton)

        self.current_input.returnPressed.connect(self.new_password_input.setFocus)
        self.new_password_input.returnPressed.connect(self.confirm_input.setFocus)
        self.confirm_input.returnPressed.connect(self.yesButton.click)
        self.current_input.setFocus()

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
        self._clear_error(self.operation_error)
        if master_password_length(text) > MAX_MASTER_PASSWORD_CODE_POINTS:
            self.password_error.setText(
                QCoreApplication.translate("SecretManager", 'ui.the_master_password_cannot_exceed_1_characters').replace("%1", str(MAX_MASTER_PASSWORD_CODE_POINTS))
            )
            self.password_error.show()
            self.strength_indicator.set_password("")
            return
        self.strength_indicator.set_password(text)

    def set_change_handler(self, handler) -> None:
        self._change_handler = handler

    def clear_sensitive_data(self) -> None:
        self.current_input.clear()
        self.new_password_input.clear()
        self.confirm_input.clear()

    def validate(self) -> bool:
        if not self.current_input.text():
            self.current_error.setText(QCoreApplication.translate("SecretManager", 'ui.enter_your_current_master_password'))
            self.current_error.show()
            self.current_input.setFocus()
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
        if self._change_handler is None:
            self.operation_error.setText(QCoreApplication.translate("SecretManager", 'ui.could_not_start_the_password_change'))
            self.operation_error.show()
            return False
        try:
            self._change_handler(self.current_input.text(), self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(master_password_policy_text(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        except ValueError:
            self.current_error.setText(QCoreApplication.translate("SecretManager", 'ui.the_current_master_password_is_incorrect'))
            self.current_error.show()
            self.current_input.setFocus()
            return False
        except OSError:
            self.operation_error.setText(QCoreApplication.translate("SecretManager", 'ui.could_not_save_the_change_try_again'))
            self.operation_error.show()
            return False
        except RuntimeError:
            self.operation_error.setText(QCoreApplication.translate("SecretManager", 'ui.the_vault_was_locked_unlock_it_and_try_again'))
            self.operation_error.show()
            return False
        return True
