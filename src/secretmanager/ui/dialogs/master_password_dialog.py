from math import ceil
from time import monotonic

from PySide6.QtCore import QCoreApplication, QTimer
from ...localization.localization import master_password_policy_text

from qfluentwidgets import (
    CaptionLabel,
    HyperlinkLabel,
    PasswordLineEdit,
    SubtitleLabel,
)

from ...vault_manager import UnlockAttemptError
from ...domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from ..components.password_strength_indicator import PasswordStrengthIndicator
from ..components.dialog_base import AppMessageBoxBase


class MasterPasswordDialog(AppMessageBoxBase):
    def __init__(self, parent=None, *, create_mode: bool = False, recovery_available: bool = True):
        super().__init__(
            parent,
            minimum_width=420,
            confirm_text=QCoreApplication.translate("SecretManager", 'ui.create') if create_mode else QCoreApplication.translate("SecretManager", 'ui.unlock'),
            cancel_text=QCoreApplication.translate("SecretManager", 'ui.cancel_56fc52'),
        )
        self.create_mode = create_mode
        self._password_validator = None
        self.authenticated_value = None
        self.recovery_requested = False
        self._unlock_cooldown_until = 0.0
        self._unlock_cooldown_timer = QTimer(self)
        self._unlock_cooldown_timer.setInterval(250)
        self._unlock_cooldown_timer.timeout.connect(self._update_unlock_cooldown)

        self.title_label = SubtitleLabel(
            QCoreApplication.translate("SecretManager", 'ui.create_master_password') if create_mode else QCoreApplication.translate("SecretManager", 'ui.unlock_vault'),
            self,
        )
        self.subtitle_label = CaptionLabel(
            (
                QCoreApplication.translate("SecretManager", 'ui.this_password_protects_your_vault_it_cannot_be_recov')
                if create_mode
                else QCoreApplication.translate("SecretManager", 'ui.enter_your_master_password_to_unlock_the_vault')
            ),
            self,
        )
        self.subtitle_label.setWordWrap(True)

        self.password_input = PasswordLineEdit(self)
        self.password_input.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.master_password'))
        self.password_error = self._create_error_label()
        self.strength_indicator = (
            PasswordStrengthIndicator(self) if create_mode else None
        )
        self.password_input.textChanged.connect(self._on_password_changed)

        self.confirm_input = None
        self.confirm_error = None

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.subtitle_label)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.password_input)
        self.viewLayout.addWidget(self.password_error)
        if self.strength_indicator is not None:
            self.viewLayout.addWidget(self.strength_indicator)

        if create_mode:
            self.confirm_input = PasswordLineEdit(self)
            self.confirm_input.setPlaceholderText(
                QCoreApplication.translate("SecretManager", 'ui.confirm_master_password')
            )
            self.confirm_error = self._create_error_label()
            self.confirm_input.textChanged.connect(
                lambda _text: self._clear_error("confirm")
            )
            self.viewLayout.addWidget(self.confirm_input)
            self.viewLayout.addWidget(self.confirm_error)
        elif recovery_available:
            self.recovery_button = HyperlinkLabel(QCoreApplication.translate("SecretManager", 'ui.forgot_your_password'), self)
            self.recovery_button.clicked.connect(self._request_recovery)
            self.viewLayout.addWidget(self.recovery_button)

        self.password_input.returnPressed.connect(self._handle_password_enter)
        if self.confirm_input is not None:
            self.confirm_input.returnPressed.connect(self.yesButton.click)
        self.password_input.setFocus()

    @staticmethod
    def _create_error_label():
        label = CaptionLabel()
        label.setTextColor("#c42b1c", "#ff99a4")
        label.setWordWrap(True)
        label.hide()
        return label

    def _on_password_changed(self, text: str) -> None:
        if self._unlock_cooldown_remaining():
            self._update_unlock_cooldown()
        else:
            self._clear_error("password")
        if self.strength_indicator is None:
            return
        if master_password_length(text) > MAX_MASTER_PASSWORD_CODE_POINTS:
            self.password_error.setText(
                QCoreApplication.translate("SecretManager", 'ui.the_master_password_cannot_exceed_1_characters').replace("%1", str(MAX_MASTER_PASSWORD_CODE_POINTS))
            )
            self.password_error.show()
            self.strength_indicator.set_password("")
            return
        self.strength_indicator.set_password(text)

    def _clear_error(self, field: str) -> None:
        label = self.password_error if field == "password" else self.confirm_error
        if label is not None:
            label.clear()
            label.hide()

    def set_error(self, field: str, message: str) -> None:
        if field == "password":
            label, target = self.password_error, self.password_input
        else:
            label, target = self.confirm_error, self.confirm_input
        if label is None or target is None:
            return
        label.setText(message)
        label.show()
        target.setFocus()

    def set_password_validator(self, validator) -> None:
        self._password_validator = validator

    def start_unlock_cooldown(self, seconds: int) -> None:
        if seconds <= 0 or self.create_mode:
            return
        self._unlock_cooldown_until = monotonic() + seconds
        self.yesButton.setEnabled(False)
        self._update_unlock_cooldown()
        self._unlock_cooldown_timer.start()

    def _unlock_cooldown_remaining(self) -> int:
        return max(0, ceil(self._unlock_cooldown_until - monotonic()))

    def _update_unlock_cooldown(self) -> None:
        remaining = self._unlock_cooldown_remaining()
        if remaining <= 0:
            self._unlock_cooldown_timer.stop()
            self._unlock_cooldown_until = 0.0
            self.yesButton.setEnabled(True)
            self.password_error.clear()
            self.password_error.hide()
            return
        self.password_error.setText(
            QCoreApplication.translate(
                "SecretManager",
                'ui.too_many_failed_attempts_you_can_try_again_in_1_s',
            ).replace("%1", str(remaining))
        )
        self.password_error.show()

    @property
    def password(self) -> str:
        return self.password_input.text()

    def clear_sensitive_data(self) -> None:
        self.password_input.clear()
        if self.confirm_input is not None:
            self.confirm_input.clear()

    def _request_recovery(self) -> None:
        self.recovery_requested = True
        self.reject()

    def _handle_password_enter(self) -> None:
        if self.confirm_input is not None:
            self.confirm_input.setFocus()
            return
        self.yesButton.click()

    def validate(self) -> bool:
        if self._unlock_cooldown_remaining():
            self._update_unlock_cooldown()
            return False
        if not self.password_input.text():
            self.set_error("password", QCoreApplication.translate("SecretManager", 'ui.enter_the_master_password'))
            return False
        if self.create_mode:
            try:
                validate_new_master_password(self.password)
            except MasterPasswordPolicyError as error:
                self.set_error("password", master_password_policy_text(error))
                return False
            if normalize_master_password(self.password) != normalize_master_password(
                self.confirm_input.text()
            ):
                self.set_error("confirm", QCoreApplication.translate("SecretManager", 'ui.the_passwords_do_not_match'))
                return False
        if not self.create_mode and self._password_validator is not None:
            try:
                self.authenticated_value = self._password_validator(self.password)
            except UnlockAttemptError as error:
                self.set_error(
                    "password",
                    QCoreApplication.translate("SecretManager", 'ui.the_master_password_is_incorrect')
                    if error.retry_after_seconds == 0
                    else QCoreApplication.translate("SecretManager", 'ui.the_master_password_is_incorrect_wait_before_trying'),
                )
                self.start_unlock_cooldown(error.retry_after_seconds)
                return False
            except ValueError:
                self.set_error(
                    "password",
                    QCoreApplication.translate("SecretManager", 'ui.the_master_password_is_incorrect'),
                )
                return False
        return True
