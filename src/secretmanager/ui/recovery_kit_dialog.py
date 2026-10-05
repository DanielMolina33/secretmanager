from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from qfluentwidgets import CaptionLabel, FluentIcon as FIF, LineEdit, MessageBoxBase, PasswordLineEdit, PushButton, SubtitleLabel

from ..domain.master_password import (
    MAX_MASTER_PASSWORD_CODE_POINTS,
    MasterPasswordPolicyError,
    master_password_length,
    normalize_master_password,
    validate_new_master_password,
)
from .password_strength_indicator import PasswordStrengthIndicator


class MasterPasswordConfirmationDialog(MessageBoxBase):
    def __init__(self, parent=None, *, title: str, content: str, action_text: str):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._validator = None
        self.authenticated_value = None
        self.title_label = SubtitleLabel(title, self)
        self.content_label = CaptionLabel(content, self)
        self.content_label.setWordWrap(True)
        self.password_input = PasswordLineEdit(self)
        self.password_input.setPlaceholderText("Contraseña maestra")
        self.error_label = self._create_error_label()
        self.password_input.textChanged.connect(self._clear_error)
        self.password_input.returnPressed.connect(self.yesButton.click)
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.content_label)
        self.viewLayout.addWidget(self.password_input)
        self.viewLayout.addWidget(self.error_label)
        self.yesButton.setText(action_text)
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(420)

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
            self.error_label.setText("Escribe la contraseña maestra.")
            self.error_label.show()
            self.password_input.setFocus()
            return False
        if self._validator is None:
            return True
        try:
            self.authenticated_value = self._validator(self.password_input.text())
        except ValueError:
            self.error_label.setText("La contraseña maestra no es correcta.")
            self.error_label.show()
            self.password_input.setFocus()
            return False
        except OSError:
            self.error_label.setText("No se pudo guardar el cambio. Inténtalo de nuevo.")
            self.error_label.show()
            return False
        except RuntimeError:
            self.error_label.setText("La bóveda se bloqueó. Desbloquéala e inténtalo de nuevo.")
            self.error_label.show()
            return False
        return True


class RecoveryKitDisplayDialog(MessageBoxBase):
    def __init__(self, code: str, commit, parent=None, *, replacing: bool = False):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._code = code
        self._commit = commit
        title = "Nuevo recovery kit" if replacing else "Recovery kit"
        description = (
            "El kit actual seguirá funcionando hasta que confirmes que guardaste este nuevo código."
            if replacing
            else "Guarda este código en un lugar seguro. Solo quedará activo cuando confirmes que lo guardaste."
        )
        self.title_label = SubtitleLabel(title, self)
        self.content_label = CaptionLabel(description, self)
        self.content_label.setWordWrap(True)
        self.code_input = LineEdit(self)
        self.code_input.setText(code)
        self.code_input.setReadOnly(True)
        self.copy_button = PushButton(FIF.COPY, "Copiar", self)
        self.copy_button.clicked.connect(self._copy_code)
        self.save_label = CaptionLabel("Al continuar confirmarás que guardaste el código.", self)
        self.error_label = MasterPasswordConfirmationDialog._create_error_label()
        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.content_label)
        self.viewLayout.addWidget(self.code_input)
        self.viewLayout.addWidget(self.copy_button)
        self.viewLayout.addWidget(self.save_label)
        self.viewLayout.addWidget(self.error_label)
        self.yesButton.setText("Ya lo guardé")
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(460)

    def _copy_code(self) -> None:
        QApplication.clipboard().setText(self._code)
        self.copy_button.setText("Copiado")

    def clear_sensitive_data(self) -> None:
        self.code_input.clear()
        self._code = ""

    def validate(self) -> bool:
        try:
            self._commit()
        except (OSError, RuntimeError, ValueError):
            self.error_label.setText("No se pudo guardar el kit. El código sigue disponible; inténtalo de nuevo.")
            self.error_label.show()
            return False
        return True


class RecoveryDialog(MessageBoxBase):
    def __init__(self, recover, parent=None):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._recover = recover
        self.recovered_vault = None
        self.title_label = SubtitleLabel("Recuperar bóveda", self)
        self.description_label = CaptionLabel(
            "Introduce tu recovery kit y establece una nueva contraseña maestra. "
            "El kit utilizado quedará invalidado. No se generará otro automáticamente; "
            "podrás configurar uno después en Seguridad.", self)
        self.description_label.setWordWrap(True)
        self.recovery_input = PasswordLineEdit(self)
        self.recovery_input.setPlaceholderText("Recovery kit")
        self.recovery_error = self._create_error_label()
        self.new_password_input = PasswordLineEdit(self)
        self.new_password_input.setPlaceholderText("Nueva contraseña maestra")
        self.password_error = self._create_error_label()
        self.strength_indicator = PasswordStrengthIndicator(self)
        self.confirm_input = PasswordLineEdit(self)
        self.confirm_input.setPlaceholderText("Confirma la nueva contraseña")
        self.confirm_error = self._create_error_label()
        self.operation_error = self._create_error_label()
        self.recovery_input.textChanged.connect(lambda _text: self._clear_error(self.recovery_error))
        self.new_password_input.textChanged.connect(self._on_new_password_changed)
        self.confirm_input.textChanged.connect(lambda _text: self._clear_error(self.confirm_error))
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
        self.yesButton.setText("Recuperar")
        self.cancelButton.setText("Cancelar")
        self.widget.setMinimumWidth(460)
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
                f"La contraseña maestra no puede superar {MAX_MASTER_PASSWORD_CODE_POINTS} caracteres."
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
            self.recovery_error.setText("Escribe el recovery kit.")
            self.recovery_error.show()
            self.recovery_input.setFocus()
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
        try:
            self.recovered_vault = self._recover(self.recovery_input.text(), self.new_password_input.text())
        except MasterPasswordPolicyError as error:
            self.password_error.setText(str(error))
            self.password_error.show()
            self.new_password_input.setFocus()
            return False
        except ValueError:
            self.recovery_error.setText("El recovery kit no es válido o ya fue utilizado.")
            self.recovery_error.show()
            self.recovery_input.setFocus()
            return False
        except OSError:
            self.operation_error.setText("No se pudo completar la recuperación. Inténtalo de nuevo.")
            self.operation_error.show()
            return False
        return True