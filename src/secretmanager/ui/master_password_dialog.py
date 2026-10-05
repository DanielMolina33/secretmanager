from math import ceil
from time import monotonic

from PySide6.QtCore import QTimer, Qt

from qfluentwidgets import (
    CaptionLabel,
    HyperlinkLabel,
    MessageBoxBase,
    PasswordLineEdit,
    SubtitleLabel,
)

from ..vault_manager import UnlockAttemptError
from ..domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from .password_strength_indicator import PasswordStrengthIndicator


class MasterPasswordDialog(MessageBoxBase):
    def __init__(self, parent=None, *, create_mode: bool = False, recovery_available: bool = True):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.create_mode = create_mode
        self._password_validator = None
        self.authenticated_value = None
        self.recovery_requested = False
        self._unlock_cooldown_until = 0.0
        self._unlock_cooldown_timer = QTimer(self)
        self._unlock_cooldown_timer.setInterval(250)
        self._unlock_cooldown_timer.timeout.connect(self._update_unlock_cooldown)

        self.title_label = SubtitleLabel(
            "Crear contrase\u00f1a maestra" if create_mode else "Desbloquear b\u00f3veda",
            self,
        )
        self.subtitle_label = CaptionLabel(
            (
                "Esta contrase\u00f1a protege tu b\u00f3veda. No se puede recuperar."
                if create_mode
                else "Introduce tu contrase\u00f1a maestra para desbloquear la b\u00f3veda."
            ),
            self,
        )
        self.subtitle_label.setWordWrap(True)

        self.password_input = PasswordLineEdit(self)
        self.password_input.setPlaceholderText("Contrase\u00f1a maestra")
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
                "Confirma la contrase\u00f1a maestra"
            )
            self.confirm_error = self._create_error_label()
            self.confirm_input.textChanged.connect(
                lambda _text: self._clear_error("confirm")
            )
            self.viewLayout.addWidget(self.confirm_input)
            self.viewLayout.addWidget(self.confirm_error)
        elif recovery_available:
            self.recovery_button = HyperlinkLabel("¿Perdiste tu contraseña?", self)
            self.recovery_button.clicked.connect(self._request_recovery)
            self.viewLayout.addWidget(self.recovery_button)

        self.yesButton.setText("Crear" if create_mode else "Desbloquear")
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(420)
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
                f"La contraseña maestra no puede superar {MAX_MASTER_PASSWORD_CODE_POINTS} caracteres."
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
            f"Demasiados intentos fallidos. Podrás volver a probar en {remaining} s."
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
            self.set_error("password", "Escribe la contrase\u00f1a maestra.")
            return False
        if self.create_mode:
            try:
                validate_new_master_password(self.password)
            except MasterPasswordPolicyError as error:
                self.set_error("password", str(error))
                return False
            if normalize_master_password(self.password) != normalize_master_password(
                self.confirm_input.text()
            ):
                self.set_error("confirm", "Las contraseñas no coinciden.")
                return False
        if not self.create_mode and self._password_validator is not None:
            try:
                self.authenticated_value = self._password_validator(self.password)
            except UnlockAttemptError as error:
                self.set_error(
                    "password",
                    "La contrase\u00f1a maestra no es correcta."
                    if error.retry_after_seconds == 0
                    else "La contrase\u00f1a maestra no es correcta. Espera antes de volver a intentarlo.",
                )
                self.start_unlock_cooldown(error.retry_after_seconds)
                return False
            except ValueError:
                self.set_error(
                    "password",
                    "La contrase\u00f1a maestra no es correcta.",
                )
                return False
        return True
