from PySide6.QtCore import Qt

from qfluentwidgets import (
    CaptionLabel,
    MessageBoxBase,
    PasswordLineEdit,
    SubtitleLabel,
)


class MasterPasswordDialog(MessageBoxBase):
    def __init__(self, parent=None, *, create_mode: bool = False):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.create_mode = create_mode
        self._password_validator = None
        self.authenticated_value = None

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
        self.password_input.textChanged.connect(
            lambda _text: self._clear_error("password")
        )

        self.confirm_input = None
        self.confirm_error = None

        self.viewLayout.addWidget(self.title_label)
        self.viewLayout.addWidget(self.subtitle_label)
        self.viewLayout.addSpacing(8)
        self.viewLayout.addWidget(self.password_input)
        self.viewLayout.addWidget(self.password_error)

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

    @property
    def password(self) -> str:
        return self.password_input.text()

    def clear_sensitive_data(self) -> None:
        self.password_input.clear()
        if self.confirm_input is not None:
            self.confirm_input.clear()

    def _handle_password_enter(self) -> None:
        if self.confirm_input is not None:
            self.confirm_input.setFocus()
            return
        self.yesButton.click()

    def validate(self) -> bool:
        if not self.password_input.text():
            self.set_error("password", "Escribe la contrase\u00f1a maestra.")
            return False
        if self.create_mode and self.password_input.text() != self.confirm_input.text():
            self.set_error("confirm", "Las contrase\u00f1as no coinciden.")
            return False
        if not self.create_mode and self._password_validator is not None:
            try:
                self.authenticated_value = self._password_validator(self.password)
            except ValueError:
                self.set_error(
                    "password",
                    "La contrase\u00f1a maestra no es correcta.",
                )
                return False
        return True
