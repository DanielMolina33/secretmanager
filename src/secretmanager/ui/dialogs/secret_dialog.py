from datetime import date, time

from PySide6.QtCore import QCoreApplication, QDate, QDateTime, QTime, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ...domain.exceptions import (
    DuplicateSecretError,
    EmptySecretValueError,
    InvalidSecretNameError,
)
from qfluentwidgets import (
    CalendarPicker,
    CheckBox,
    FluentIcon as FIF,
    CaptionLabel,
    LineEdit,
    PasswordLineEdit,
    SubtitleLabel,
    TransparentToolButton,
    SwitchButton,
    TimeEdit,
    TextEdit,
    ToolTipFilter,
    ToolTipPosition,
)
from ..components.copy_button import create_copy_button
from ..components.dialog_base import AppMessageBoxBase


class SecretDialog(AppMessageBoxBase):
    def __init__(
        self,
        parent=None,
        secret=None,
    ):
        super().__init__(parent, minimum_width=520, confirm_text=QCoreApplication.translate("SecretManager", 'ui.save'))

        self.form_widget = QWidget(self.content_widget)
        self.form_layout = QVBoxLayout(self.form_widget)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(12)
        self.viewLayout.addWidget(self.form_widget)

        self.is_editing = secret is not None
        self._submit_callback = None

        title = (
            QCoreApplication.translate("SecretManager", 'ui.edit_secret')
            if self.is_editing
            else QCoreApplication.translate("SecretManager", 'ui.new_secret')
        )

        subtitle = (
            QCoreApplication.translate("SecretManager", 'ui.update_the_secret_stored_in_your_local_vault')
            if self.is_editing
            else QCoreApplication.translate("SecretManager", 'ui.save_a_new_secret_in_your_local_vault')
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
            QCoreApplication.translate("SecretManager", 'ui.e_g_aws_access_key')
        )
        self.name_input.setClearButtonEnabled(
            True
        )
        self.name_error = self._create_error_label()
        self.name_input.textChanged.connect(
            lambda _text: self.clear_error("name")
        )
        self.name_copy_button = create_copy_button(self.name_input.text, self)
        self.name_copy_button.setEnabled(False)
        self.name_input.textChanged.connect(
            lambda text: self.name_copy_button.setEnabled(bool(text))
        )

        self.value_input = PasswordLineEdit(
            self
        )
        self.value_input.setPlaceholderText(
            QCoreApplication.translate("SecretManager", 'ui.secret_value')
        )
        self.value_error = self._create_error_label()
        self.value_input.textChanged.connect(
            lambda _text: self.clear_error("value")
        )
        self.value_copy_button = create_copy_button(self.value_input.text, self)
        self.value_copy_button.setEnabled(False)
        self.value_input.textChanged.connect(
            lambda text: self.value_copy_button.setEnabled(bool(text))
        )

        self.cli_permission = SwitchButton(QCoreApplication.translate("SecretManager", 'ui.allow_use_from_cli'), self)
        self.cli_permission.setOffText(QCoreApplication.translate("SecretManager", 'ui.allow_use_from_cli'))
        self.cli_permission.setOnText(QCoreApplication.translate("SecretManager", 'ui.allow_use_from_cli'))

        self.cli_info_button = TransparentToolButton(FIF.INFO, self)
        self.cli_info_button.setAccessibleName(QCoreApplication.translate("SecretManager", 'ui.information_about_cli_access'))
        self.cli_info_button.setToolTip(
            QCoreApplication.translate(
                "SecretManager",
                'ui.when_enabled_this_secret_can_be_requested_and_used_f',
            )
        )
        self.cli_info_tooltip = ToolTipFilter(
            self.cli_info_button,
            showDelay=300,
            position=ToolTipPosition.RIGHT,
        )
        self.cli_info_button.installEventFilter(self.cli_info_tooltip)

        self.cli_permission_layout = QHBoxLayout()
        self.cli_permission_layout.setContentsMargins(0, 0, 0, 0)
        self.cli_permission_layout.setSpacing(4)
        self.cli_permission_layout.addWidget(self.cli_permission)
        self.cli_permission_layout.addWidget(self.cli_info_button)
        self.cli_permission_layout.addStretch(1)

        self.note_input = TextEdit(self)
        self.note_input.setPlaceholderText(
            QCoreApplication.translate("SecretManager", 'ui.optional_note')
        )
        self.note_input.setFixedHeight(90)

        self.expiry_enabled = SwitchButton(
            QCoreApplication.translate("SecretManager", 'ui.set_expiration'),
            self,
        )

        self.expiry_enabled.setOffText(
            QCoreApplication.translate("SecretManager", 'ui.set_expiration')
        )

        self.expiry_enabled.setOnText(
            QCoreApplication.translate("SecretManager", 'ui.expiration_enabled')
        )

        self.expiry_date_label = CaptionLabel(QCoreApplication.translate("SecretManager", 'ui.date'), self)
        self.expiry_date_input = CalendarPicker(self)
        self.expiry_date_input.setDateFormat("dd/MM/yyyy")
        self.expiry_date_input.setDate(
            QDateTime.currentDateTime().date()
        )

        self.expiry_time_enabled = CheckBox(QCoreApplication.translate("SecretManager", 'ui.time'), self)
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

        self.form_layout.addWidget(
            self.title_label
        )

        self.form_layout.addWidget(
            self.subtitle_label
        )

        self.form_layout.addSpacing(8)

        self._add_field(
            QCoreApplication.translate("SecretManager", 'ui.name'),
            self.name_input,
            self.name_error,
            self.name_copy_button,
        )

        self._add_field(
            QCoreApplication.translate("SecretManager", 'ui.value'),
            self.value_input,
            self.value_error,
            self.value_copy_button,
        )
        self.form_layout.addLayout(self.cli_permission_layout)
        self.form_layout.addSpacing(4)

        self._add_field(
            QCoreApplication.translate("SecretManager", 'ui.note'),
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
                QCoreApplication.translate("SecretManager", 'ui.expiration'),
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

        self.form_layout.addLayout(
            expiry_layout
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
            self.cli_permission.setChecked(secret.allow_cli)

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
        copy_button=None,
    ):
        self.form_layout.addWidget(
            CaptionLabel(
                label_text,
                self,
            )
        )

        if copy_button is None:
            self.form_layout.addWidget(widget)
        else:
            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)
            row_layout.addWidget(widget, 1)
            row_layout.addWidget(copy_button)
            self.form_layout.addWidget(row)
        if error_label is not None:
            self.form_layout.addWidget(error_label)

        self.form_layout.addSpacing(4)

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
            "allow_cli": self.cli_permission.isChecked(),
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
                QCoreApplication.translate("SecretManager", 'ui.use_a_valid_name_letters_numbers_and_underscores_it'),
            )
            return False
        except DuplicateSecretError:
            self.set_error("name", QCoreApplication.translate("SecretManager", 'ui.a_secret_with_that_name_already_exists'))
            return False
        except EmptySecretValueError:
            self.set_error("value", QCoreApplication.translate("SecretManager", 'ui.enter_the_secret_value'))
            return False
        return True

