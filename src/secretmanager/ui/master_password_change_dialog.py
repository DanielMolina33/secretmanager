from PySide6.QtCore import Qt
from qfluentwidgets import CaptionLabel, MessageBoxBase, PasswordLineEdit, SubtitleLabel

from ..domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from .password_strength_indicator import PasswordStrengthIndicator


class MasterPasswordChangeDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._change_handler = None

        self.title_label = SubtitleLabel("Cambiar contraseña maestra", self)
        self.current_input = PasswordLineEdit(self)
        self.current_input.setPlaceholderText("Contraseña maestra actual")
        self.current_error = self._create_error_label()
        self.current_input.textChanged.connect(lambda _text: self._clear_error(self.current_error))

        self.new_password_input = PasswordLineEdit(self)
        self.new_password_input.setPlaceholderText("Nueva contraseña maestra")
        self.password_error = self._create_error_label()
        self.strength_indicator = PasswordStrengthIndicator(self)
        self.new_password_input.textChanged.connect(self._on_new_password_changed)

        self.confirm_input = PasswordLineEdit(self)
        self.confirm_input.setPlaceholderText("Confirma la nueva contraseña")
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
        self.yesButton.setText("Cambiar")
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(420)

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
                f"La contraseña maestra no puede superar {MAX_MASTER_PASSWORD_CODE_POINTS} caracteres."
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
            self.current_error.setText("Escribe tu contraseña maestra actual.")
            self.current_error.show()
            self.current_input.setFocus()
            return False
        try:
            validate_new_master_password(self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(str(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        if normalize_master_password(self.new_password_input.text()) != normalize_master_password(
            self.confirm_input.text()
        ):
            self.confirm_error.setText("Las contraseñas no coinciden.")
            self.confirm_error.show()
            self.confirm_input.setFocus()
            return False
        if self._change_handler is None:
            self.operation_error.setText("No se pudo iniciar el cambio de contraseña.")
            self.operation_error.show()
            return False
        try:
            self._change_handler(self.current_input.text(), self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(str(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        except ValueError:
            self.current_error.setText("La contraseña maestra actual no es correcta.")
            self.current_error.show()
            self.current_input.setFocus()
            return False
        except OSError:
            self.operation_error.setText("No se pudo guardar el cambio. Inténtalo de nuevo.")
            self.operation_error.show()
            return False
        except RuntimeError:
            self.operation_error.setText("La bóveda se bloqueó. Desbloquéala e inténtalo de nuevo.")
            self.operation_error.show()
            return False
        return True
