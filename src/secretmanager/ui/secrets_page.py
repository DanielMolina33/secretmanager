from datetime import date, datetime, timedelta
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QHeaderView, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import Action, BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF, InfoBadge, InfoLevel, MessageBox, PrimaryPushButton, RoundMenu, SearchLineEdit, SegmentedWidget, TableWidget, TitleLabel, TransparentToolButton
from ..domain.exceptions import DuplicateSecretError, EmptySecretValueError, InvalidSecretNameError
from .secret_dialog import SecretDialog
from .vault_locked_view import VaultLockedView

class SecretsPage(QWidget):

    def __init__(self, on_unlock, parent=None):
        super().__init__(parent)
        self.on_unlock = on_unlock
        self.secret_service = None
        self._secret_rows = []

        self._active_secret_dialog = None
        self._vault_unlocked = False
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._on_status_transition)
        self.secret_filter = 'Todos'
        self.secret_filter_labels = {'Todos': 'Todos', 'Vigente': 'Vigentes', 'Por vencer': 'Por vencer', 'Vencido': 'Vencidos'}
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._build_ui())

    def set_service(self, service):
        self.secret_service = service
        self.refresh_secret_list()

    def set_unlocked(self, unlocked):
        self._vault_unlocked = unlocked
        self.add_button.setEnabled(unlocked)
        self.search_box.setEnabled(unlocked)
        self.secret_content.setCurrentWidget(self.secret_list_view if unlocked else self.vault_locked_view)
        if unlocked:
            self._schedule_status_update()
        else:
            self._status_timer.stop()

    def _exec_secret_dialog(self, dialog):
        self._active_secret_dialog = dialog
        try:
            return dialog.exec()
        finally:
            self._active_secret_dialog = None

    def reject_active_secret_dialog(self):
        dialog = self._active_secret_dialog
        if dialog is None:
            return
        clear_sensitive_data = getattr(dialog, 'clear_sensitive_data', None)
        if clear_sensitive_data is not None:
            clear_sensitive_data()
        dialog.reject()


    def _build_ui(self):
        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        self.secret_list_view = QWidget(page)
        layout = QVBoxLayout(self.secret_list_view)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.addWidget(TitleLabel('Secretos', self.secret_list_view))
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.search_box = SearchLineEdit(self.secret_list_view)
        self.search_box.setPlaceholderText('Buscar por nombre o nota...')
        self.search_box.textChanged.connect(self.filter_secrets)
        search_row.addWidget(self.search_box, 1)
        self.add_button = PrimaryPushButton(FIF.ADD, 'Nuevo', self.secret_list_view)
        self.add_button.clicked.connect(self.add_secret)
        search_row.addWidget(self.add_button)
        layout.addLayout(search_row)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.secret_filter = 'Todos'
        self.secret_filter_labels = {'Todos': 'Todos', 'Vigente': 'Vigentes', 'Por vencer': 'Por vencer', 'Vencido': 'Vencidos'}
        self.secret_filter_widget = SegmentedWidget(self.secret_list_view)
        self.secret_filter_buttons = {}
        for key, label in self.secret_filter_labels.items():
            button = self.secret_filter_widget.addItem(routeKey=key, text=f'{label}  0', onClick=lambda checked=False, value=key: self._set_secret_filter(value))
            self.secret_filter_buttons[key] = button
        self.secret_filter_widget.setCurrentItem(self.secret_filter)
        controls.addWidget(self.secret_filter_widget)
        controls.addStretch()
        controls.addWidget(CaptionLabel('Ordenar:', self.secret_list_view))
        self.secret_sort = ComboBox(self.secret_list_view)
        self.secret_sort.addItems(['Nombre ↑', 'Nombre ↓'])
        self.secret_sort.setFixedWidth(125)
        self.secret_sort.currentIndexChanged.connect(self.refresh_secret_list)
        controls.addWidget(self.secret_sort)
        layout.addLayout(controls)
        self.secret_list = TableWidget(self.secret_list_view)
        self.secret_list.setColumnCount(4)
        self.secret_list.setHorizontalHeaderLabels(['Nombre', 'Estado', '', ''])
        self.secret_list.setBorderVisible(True)
        self.secret_list.setBorderRadius(8)
        self.secret_list.setAlternatingRowColors(False)
        self.secret_list.setSelectionMode(self.secret_list.SelectionMode.NoSelection)
        self.secret_list.setEditTriggers(self.secret_list.EditTrigger.NoEditTriggers)
        self.secret_list.verticalHeader().hide()
        header = self.secret_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.secret_list.setColumnWidth(0, 320)
        self.secret_list.setColumnWidth(1, 118)
        self.secret_list.setColumnWidth(3, 48)
        self.secret_list.cellDoubleClicked.connect(lambda row, column: self.edit_secret(self._secret_rows[row]["name"]))
        layout.addWidget(self.secret_list, 1)
        self.vault_locked_view = VaultLockedView(self.on_unlock, page)
        self.secret_content = QStackedWidget(page)
        self.secret_content.addWidget(self.secret_list_view)
        self.secret_content.addWidget(self.vault_locked_view)
        page_layout.addWidget(self.secret_content, 1)
        return page

    def refresh_secret_list(self):
        if not hasattr(self, "secret_list"):
            return
        self._status_timer.stop()
        self.secret_list.setUpdatesEnabled(False)
        try:
            self.secret_list.setRowCount(0)
            self._secret_rows.clear()
            if self.secret_service is None:
                return
            secrets = list(self.secret_service.list())
            reverse = self.secret_sort.currentIndex() == 1
            secrets.sort(key=lambda secret: secret.name.casefold(), reverse=reverse)
            for secret in secrets:
                self.add_secret_item(secret)
            self._update_secret_filter_counts()
            self.filter_secrets(self.search_box.text())
        finally:
            QTimer.singleShot(0, self._finish_secret_list_layout)
            self._schedule_status_update()

    def _schedule_status_update(self):
        self._status_timer.stop()
        if not self._vault_unlocked or not self._secret_rows:
            return

        now = datetime.now()
        transitions = []
        for row in self._secret_rows:
            expires_on = row["expires_on"]
            if expires_on is None:
                continue

            expires_at_time = row["expires_at_time"]
            if expires_at_time is None:
                due_at = datetime.combine(expires_on, datetime.min.time())
                transitions.extend((due_at, due_at + timedelta(days=1)))
            else:
                expires_at = datetime.combine(expires_on, expires_at_time)
                transitions.extend((
                    expires_at - timedelta(minutes=5),
                    expires_at,
                ))

        upcoming = [transition for transition in transitions if transition > now]
        if not upcoming:
            return

        milliseconds = max(
            1,
            int((min(upcoming) - now).total_seconds() * 1000),
        )
        # QTimer's interval is a signed 32-bit millisecond value.
        self._status_timer.start(min(milliseconds, 2_147_000_000))

    def _on_status_transition(self):
        if self._vault_unlocked:
            self.refresh_secret_list()

    def _finish_secret_list_layout(self):
        self.secret_list.doItemsLayout()
        self.secret_list.setUpdatesEnabled(True)
        self.secret_list.viewport().update()

    def _update_secret_filter_counts(self):
        counts = {'Todos': self.secret_list.rowCount(), 'Vigente': 0, 'Por vencer': 0, 'Vencido': 0}
        for row_data in self._secret_rows:
            status = row_data['status']
            if status in counts:
                counts[status] += 1
        for key, button in self.secret_filter_buttons.items():
            button.setText(f'{self.secret_filter_labels[key]}  {counts[key]}')

    def filter_secrets(self, text):
        text = text.strip().lower()
        for row in range(self.secret_list.rowCount()):
            row_data = self._secret_rows[row]
            name = row_data['name'].lower()
            note = row_data['note'].lower()
            status = row_data['status']
            matches_text = not text or text in name or text in note
            matches_status = self.secret_filter == 'Todos' or status == self.secret_filter
            self.secret_list.setRowHidden(row, not (matches_text and matches_status))

    def _set_secret_filter(self, value):
        self.secret_filter = value
        self.secret_filter_widget.setCurrentItem(value)
        self._update_secret_filter_counts()
        self.filter_secrets(self.search_box.text())

    def add_secret_item(self, secret):
        row = self.secret_list.rowCount()
        self.secret_list.insertRow(row)
        self.secret_list.setRowHeight(row, 58)
        name_cell = QWidget(self.secret_list)
        name_cell.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_layout = QVBoxLayout(name_cell)
        name_layout.setContentsMargins(8, 4, 8, 4)
        name_layout.setSpacing(2)
        name_layout.addStretch(1)
        name_label = BodyLabel(secret.name, name_cell)
        name_label.setWordWrap(False)
        name_label.setToolTip(secret.name)
        name_layout.addWidget(name_label)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if secret.note:
            note_label = CaptionLabel(secret.note, name_cell)
            note_label.setTextColor('#606060', '#d2d2d2')
            note_label.setWordWrap(False)
            note_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            name_layout.addWidget(note_label)
        name_layout.addStretch(1)
        self.secret_list.setCellWidget(row, 0, name_cell)
        status_text, status_level = self._secret_status(secret)
        self._secret_rows.append({
            'name': secret.name,
            'note': (secret.note or '').lower(),
            'status': status_text,
            'expires_on': secret.expires_on,
            'expires_at_time': secret.expires_at_time,
        })
        status_badge = InfoBadge(status_text, self.secret_list, status_level)
        status_cell = QWidget(self.secret_list)
        status_cell.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        status_layout = QVBoxLayout(status_cell)
        status_layout.setContentsMargins(8, 0, 8, 0)
        status_layout.addStretch(1)
        status_layout.addWidget(
            status_badge,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        status_layout.addStretch(1)
        self.secret_list.setCellWidget(row, 1, status_cell)
        options_cell = QWidget(self.secret_list)
        options_layout = QVBoxLayout(options_cell)
        options_layout.setContentsMargins(0, 0, 4, 0)
        options_layout.addStretch(1)
        more_button = TransparentToolButton(FIF.MORE, options_cell)
        more_button.setFixedSize(32, 32)
        more_button.setToolTip('Más opciones')
        more_button.clicked.connect(lambda checked=False, name=secret.name, button=more_button: self.show_secret_menu(name, button))
        options_layout.addWidget(
            more_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        options_layout.addStretch(1)
        self.secret_list.setCellWidget(row, 3, options_cell)

    @staticmethod
    def _secret_status(secret):
        expires_on = secret.expires_on
        if expires_on is None:
            return ('Vigente', InfoLevel.SUCCESS)

        now = datetime.now()
        if secret.expires_at_time is None:
            today = date.today()
            if today < expires_on:
                return ('Vigente', InfoLevel.SUCCESS)
            if today == expires_on:
                return ('Por vencer', InfoLevel.WARNING)
            return ('Vencido', InfoLevel.ERROR)

        expires_at = datetime.combine(expires_on, secret.expires_at_time)
        warning_starts_at = expires_at - timedelta(minutes=5)
        if now < warning_starts_at:
            return ('Vigente', InfoLevel.SUCCESS)
        if now < expires_at:
            return ('Por vencer', InfoLevel.WARNING)
        return ('Vencido', InfoLevel.ERROR)

    def add_secret(self):
        service = self.secret_service
        if service is None:
            return
        dialog = SecretDialog(self.window())
        dialog.set_submit_callback(
            lambda data: service.create(
                name=data["name"],
                value=data["value"],
                note=data["note"],
                expires_on=data["expires_on"],
                expires_at_time=data["expires_at_time"],
            )
        )
        if self._exec_secret_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        self.refresh_secret_list()

    def show_secret_menu(self, secret_name, anchor):
        if self.secret_service is None:
            return
        menu = RoundMenu(parent=self)
        edit_action = Action(FIF.EDIT, 'Editar', menu)
        edit_action.triggered.connect(lambda checked=False, name=secret_name: self.edit_secret(name))
        delete_action = Action(FIF.DELETE, 'Eliminar', menu)
        delete_action.triggered.connect(lambda checked=False, name=secret_name: self.delete_secret(name))
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def edit_secret(self, secret_name):
        service = self.secret_service
        if service is None:
            return
        secret = service.get(secret_name)
        if secret is None:
            return
        current_name = secret.name
        dialog = SecretDialog(self.window(), secret)
        del secret
        dialog.set_submit_callback(
            lambda data: service.update(
                current_name=current_name,
                name=data["name"],
                value=data["value"],
                note=data["note"],
                expires_on=data["expires_on"],
                expires_at_time=data["expires_at_time"],
            )
        )
        if self._exec_secret_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        self.refresh_secret_list()

    def delete_secret(self, secret_name):
        if self.secret_service is None:
            return
        confirmation = MessageBox('Eliminar secreto', f"¿Eliminar '{secret_name}'?", self.window())
        confirmation.setWindowModality(Qt.WindowModality.ApplicationModal)
        confirmation.yesButton.setText('Eliminar')
        confirmation.cancelButton.setText('Cancelar')
        if not self._exec_secret_dialog(confirmation):
            return
        if self.secret_service is None:
            return
        self.secret_service.delete(secret_name)
        self.refresh_secret_list()



