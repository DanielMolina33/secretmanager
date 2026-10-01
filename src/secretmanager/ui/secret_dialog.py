from datetime import date, time

from PySide6.QtCore import QDate, QDateTime, QTime, Qt
from PySide6.QtWidgets import QVBoxLayout

from ..domain.exceptions import (
    DuplicateSecretError,
    EmptySecretValueError,
    InvalidSecretNameError,
)
from qfluentwidgets import (
    CalendarPicker,
    CheckBox,
    CaptionLabel,
    LineEdit,
    MessageBoxBase,
    PasswordLineEdit,
    SubtitleLabel,
    SwitchButton,
    TimeEdit,
    TextEdit,
)


class SecretDialog(MessageBoxBase):
    def __init__(
        self,
        parent=None,
        secret=None,
    ):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        self.is_editing = secret is not None
        self._submit_callback = None

        title = (
            "Editar secreto"
            if self.is_editing
            else "Nuevo secreto"
        )

        subtitle = (
            "Actualiza el secreto guardado en tu "
            "bóveda local."
            if self.is_editing
            else "Guarda un secreto nuevo en tu "
            "bóveda local."
        )

        self.title_label = SubtitleLabel(
            title,
            self,
        )

        self.subtitle_label = CaptionLabel(
            subtitle,
            self,
        )
        self.subtitle_label.setWordWrap(True)

        self.name_input = LineEdit(self)
        self.name_input.setPlaceholderText(
            "Ej. AWS_ACCESS_KEY"
        )
        self.name_input.setClearButtonEnabled(
            True
        )
        self.name_error = self._create_error_label()
        self.name_input.textChanged.connect(
            lambda _text: self.clear_error("name")
        )

        self.value_input = PasswordLineEdit(
            self
        )
        self.value_input.setPlaceholderText(
            "Valor del secreto"
        )
        self.value_error = self._create_error_label()
        self.value_input.textChanged.connect(
            lambda _text: self.clear_error("value")
        )

        self.note_input = TextEdit(self)
        self.note_input.setPlaceholderText(
            "Nota opcional"
        )
        self.note_input.setFixedHeight(90)

        self.expiry_enabled = SwitchButton(
            "Establecer caducidad",
            self,
        )

        self.expiry_enabled.setOffText(
            "Establecer caducidad"
        )

        self.expiry_enabled.setOnText(
            "Caducidad activada"
        )

        self.expiry_date_label = CaptionLabel("Fecha", self)
        self.expiry_date_input = CalendarPicker(self)
        self.expiry_date_input.setDateFormat("dd/MM/yyyy")
        self.expiry_date_input.setDate(
            QDateTime.currentDateTime().addDays(30).date()
        )

        self.expiry_time_enabled = CheckBox("Hora", self)
        self.expiry_time_input = TimeEdit(self)
        self.expiry_time_input.setDisplayFormat("HH:mm")
        self.expiry_time_input.setTime(QTime(0, 0))

        self.expiry_enabled.checkedChanged.connect(
            self._set_expiry_enabled
        )
        self.expiry_time_enabled.toggled.connect(
            lambda checked: self.expiry_time_input.setVisible(
                checked and self.expiry_enabled.isChecked()
            )
        )
        self.expiry_date_label.setVisible(False)
        self.expiry_date_input.setVisible(False)
        self.expiry_time_enabled.setVisible(False)
        self.expiry_time_input.setVisible(False)

        self.viewLayout.addWidget(
            self.title_label
        )

        self.viewLayout.addWidget(
            self.subtitle_label
        )

        self.viewLayout.addSpacing(8)

        self._add_field(
            "Nombre",
            self.name_input,
            self.name_error,
        )

        self._add_field(
            "Valor",
            self.value_input,
            self.value_error,
        )

        self._add_field(
            "Nota",
            self.note_input,
        )

        expiry_layout = QVBoxLayout()
        expiry_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        expiry_layout.setSpacing(8)

        expiry_layout.addWidget(
            CaptionLabel(
                "Caducidad",
                self,
            )
        )

        expiry_layout.addWidget(
            self.expiry_enabled
        )

        expiry_layout.addWidget(self.expiry_date_label)
        expiry_layout.addWidget(self.expiry_date_input)
        expiry_layout.addWidget(self.expiry_time_enabled)
        expiry_layout.addWidget(self.expiry_time_input)

        self.viewLayout.addLayout(
            expiry_layout
        )

        self.yesButton.setText(
            "Guardar"
        )

        self.cancelButton.setText(
            "Cancelar"
        )

        self.widget.setMinimumWidth(
            520
        )

        if self.is_editing:
            self.name_input.setText(
                secret.name
            )

            self.value_input.setText(
                secret.value
            )

            self.note_input.setPlainText(
                secret.note
            )

            if secret.expires_on is not None:
                self.expiry_enabled.setChecked(True)
                self.expiry_date_input.setDate(
                    QDate(
                        secret.expires_on.year,
                        secret.expires_on.month,
                        secret.expires_on.day,
                    )
                )

                if secret.expires_at_time is not None:
                    self.expiry_time_enabled.setChecked(True)
                    self.expiry_time_input.setTime(
                        QTime(
                            secret.expires_at_time.hour,
                            secret.expires_at_time.minute,
                            secret.expires_at_time.second,
                        )
                    )

    def _set_expiry_enabled(self, enabled):
        self.expiry_date_label.setVisible(enabled)
        self.expiry_date_input.setVisible(enabled)
        self.expiry_time_enabled.setVisible(enabled)
        self.expiry_time_input.setVisible(
            enabled and self.expiry_time_enabled.isChecked()
        )

    @staticmethod
    def _create_error_label():
        label = CaptionLabel()
        label.setTextColor("#c42b1c", "#ff99a4")
        label.setWordWrap(True)
        label.hide()
        return label

    def clear_error(self, field):
        label = self.name_error if field == "name" else self.value_error
        label.clear()
        label.hide()

    def set_error(self, field, message):
        if field == "name":
            label, target = self.name_error, self.name_input
        else:
            label, target = self.value_error, self.value_input
        label.setText(message)
        label.show()
        target.setFocus()

    def _add_field(
        self,
        label_text,
        widget,
        error_label=None,
    ):
        self.viewLayout.addWidget(
            CaptionLabel(
                label_text,
                self,
            )
        )

        self.viewLayout.addWidget(
            widget
        )
        if error_label is not None:
            self.viewLayout.addWidget(error_label)

        self.viewLayout.addSpacing(4)

    def get_data(self):
        expires_on = None
        expires_at_time = None

        if self.expiry_enabled.isChecked():
            selected_date = self.expiry_date_input.date
            expires_on = date(
                selected_date.year(),
                selected_date.month(),
                selected_date.day(),
            )

            if self.expiry_time_enabled.isChecked():
                selected_time = self.expiry_time_input.time()
                expires_at_time = time(
                    selected_time.hour(),
                    selected_time.minute(),
                    selected_time.second(),
                )

        return {
            "name": self.name_input.text(),
            "value": self.value_input.text(),
            "note": self.note_input.toPlainText(),
            "expires_on": expires_on,
            "expires_at_time": expires_at_time,
        }

    def clear_sensitive_data(self):
        self.value_input.clear()
        self.name_input.clear()
        self.note_input.clear()

    def set_submit_callback(self, callback):
        self._submit_callback = callback

    def validate(self) -> bool:
        if self._submit_callback is None:
            return True
        try:
            self._submit_callback(self.get_data())
        except InvalidSecretNameError:
            self.set_error(
                "name",
                "Usa un nombre v\u00e1lido: letras, n\u00fameros y guion bajo; no puede empezar con n\u00famero.",
            )
            return False
        except DuplicateSecretError:
            self.set_error("name", "Ya existe un secreto con ese nombre.")
            return False
        except EmptySecretValueError:
            self.set_error("value", "Escribe el valor del secreto.")
            return False
        return True

