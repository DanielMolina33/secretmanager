from datetime import datetime

from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QHeaderView, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    InfoBadge,
    InfoLevel,
    PipsPager,
    PipsScrollButtonDisplayMode,
    PrimaryPushButton,
    RoundMenu,
    SearchLineEdit,
    SegmentedWidget,
    TableWidget,
    TitleLabel,
    TransparentToolButton,
    qconfig,
)
from ...domain.exceptions import DuplicateSecretError, EmptySecretValueError, InvalidSecretNameError
from ...domain.expiry import EXPIRED, EXPIRING, VALID, get_expiry_status
from ...services.clipboard import copy_text
from ..dialogs.secret_dialog import SecretDialog
from ..components.dialog_base import ConfirmationDialog
from .vault_locked_view import VaultLockedView
from .empty_state_view import EmptyStateView


class SecretsPage(QWidget):

    def __init__(self, on_unlock, parent=None):
        super().__init__(parent)
        self.on_unlock = on_unlock
        self.secret_service = None
        self._secret_rows = []
        self._secret_count = 0
        self._filtered_secret_count = 0
        self._secret_status_counts = {VALID: 0, EXPIRING: 0, EXPIRED: 0}
        self._page_index = 0
        self._page_size = 25
        self._pager_page_count = 0
        self._page_refresh_pending = False

        self._active_secret_dialog = None
        self._vault_unlocked = False
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._on_status_transition)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._apply_search_filter)
        self.secret_filter = "all"
        self.secret_filter_labels = {
            "all": QCoreApplication.translate("SecretManager", "ui.filter.all"),
            VALID: QCoreApplication.translate("SecretManager", "ui.filter.valid"),
            EXPIRING: QCoreApplication.translate("SecretManager", "ui.filter.expiring"),
            EXPIRED: QCoreApplication.translate("SecretManager", "ui.filter.expired"),
        }
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self._build_ui())

    def set_service(self, service):
        self.secret_service = service
        self.refresh_secret_list(reset_page=True)

    def set_unlocked(self, unlocked):
        self._vault_unlocked = unlocked
        self.add_button.setEnabled(unlocked)
        self.search_box.setEnabled(unlocked)
        self._update_page_content()
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
        layout.addWidget(TitleLabel(QCoreApplication.translate("SecretManager", 'ui.secrets'), self.secret_list_view))
        self.secret_list_stack = QStackedWidget(self.secret_list_view)
        self.secret_list_content = QWidget(self.secret_list_stack)
        content_layout = QVBoxLayout(self.secret_list_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        search_row = QHBoxLayout()
        search_row.setSpacing(10)
        self.search_box = SearchLineEdit(self.secret_list_content)
        self.search_box.setPlaceholderText(QCoreApplication.translate("SecretManager", 'ui.search_by_name_or_note'))
        self.search_box.textChanged.connect(self.filter_secrets)
        search_row.addWidget(self.search_box, 1)
        self.add_button = PrimaryPushButton(FIF.ADD, QCoreApplication.translate("SecretManager", 'ui.new'), self.secret_list_content)
        self.add_button.clicked.connect(self.add_secret)
        search_row.addWidget(self.add_button)
        content_layout.addLayout(search_row)
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.secret_filter = "all"
        self.secret_filter_labels = {
            "all": QCoreApplication.translate("SecretManager", "ui.filter.all"),
            VALID: QCoreApplication.translate("SecretManager", "ui.filter.valid"),
            EXPIRING: QCoreApplication.translate("SecretManager", "ui.filter.expiring"),
            EXPIRED: QCoreApplication.translate("SecretManager", "ui.filter.expired"),
        }
        self.secret_filter_widget = SegmentedWidget(self.secret_list_content)
        self.secret_filter_buttons = {}
        for key, label in self.secret_filter_labels.items():
            button = self.secret_filter_widget.addItem(routeKey=key, text=f'{label}  0', onClick=lambda checked=False, value=key: self._set_secret_filter(value))
            self.secret_filter_buttons[key] = button
        self.secret_filter_widget.setCurrentItem(self.secret_filter)
        controls.addWidget(self.secret_filter_widget)
        controls.addStretch()
        controls.addWidget(CaptionLabel(QCoreApplication.translate("SecretManager", 'ui.sort'), self.secret_list_content))
        self.secret_sort = ComboBox(self.secret_list_content)
        self.secret_sort.addItem(
            QCoreApplication.translate("SecretManager", 'ui.sort.ascending'),
            icon=FIF.UP,
        )
        self.secret_sort.addItem(
            QCoreApplication.translate("SecretManager", 'ui.sort.descending'),
            icon=FIF.DOWN,
        )
        self.secret_sort.setFixedWidth(170)
        self.secret_sort.currentIndexChanged.connect(self._on_secret_sort_changed)
        qconfig.themeChanged.connect(self._update_secret_sort_icon)
        self._update_secret_sort_icon()
        controls.addWidget(self.secret_sort)
        content_layout.addLayout(controls)
        self.results_content = QStackedWidget(self.secret_list_content)
        self.secret_list = TableWidget(self.results_content)
        self.secret_list.setColumnCount(4)
        self.secret_list.setHorizontalHeaderLabels([QCoreApplication.translate("SecretManager", 'ui.name'), QCoreApplication.translate("SecretManager", 'ui.status'), '', ''])
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
        self.results_content.addWidget(self.secret_list)
        self.no_results_view = QWidget(self.results_content)
        no_results_layout = QVBoxLayout(self.no_results_view)
        no_results_layout.setContentsMargins(0, 0, 0, 0)
        no_results_layout.addStretch(1)
        no_results_label = BodyLabel(
            QCoreApplication.translate("SecretManager", 'ui.no_matching_secrets'),
            self.no_results_view,
        )
        no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_results_layout.addWidget(no_results_label, alignment=Qt.AlignmentFlag.AlignCenter)
        no_results_layout.addStretch(1)
        self.results_content.addWidget(self.no_results_view)
        content_layout.addWidget(self.results_content, 1)

        self.pagination_footer = QWidget(self.secret_list_content)
        pagination_layout = QHBoxLayout(self.pagination_footer)
        pagination_layout.setContentsMargins(8, 0, 8, 0)
        pagination_layout.setSpacing(12)
        self.pagination_range_label = CaptionLabel(self.pagination_footer)
        self.pagination_page_label = CaptionLabel(self.pagination_footer)
        self.pagination_pager = PipsPager(
            Qt.Orientation.Horizontal,
            self.pagination_footer,
        )
        self.pagination_pager.setVisibleNumber(7)
        self.pagination_pager.setPreviousButtonDisplayMode(
            PipsScrollButtonDisplayMode.ALWAYS
        )
        self.pagination_pager.setNextButtonDisplayMode(
            PipsScrollButtonDisplayMode.ALWAYS
        )
        self.pagination_pager.currentIndexChanged.connect(self._on_page_changed)
        pagination_layout.addWidget(self.pagination_range_label)
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(
            self.pagination_pager,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        pagination_layout.addStretch(1)
        pagination_layout.addWidget(self.pagination_page_label)
        self.pagination_footer.setVisible(False)
        content_layout.addWidget(self.pagination_footer)

        self.empty_state_view = EmptyStateView(
            QCoreApplication.translate("SecretManager", 'ui.no_secrets_yet'),
            QCoreApplication.translate("SecretManager", 'ui.add_your_first_secret_to_keep_it_securely_stored_and_ready_to_use'),
            QCoreApplication.translate("SecretManager", 'ui.new_secret'),
            self.add_secret,
            self.secret_list_stack,
        )
        self.secret_list_stack.addWidget(self.secret_list_content)
        self.secret_list_stack.addWidget(self.empty_state_view)
        layout.addWidget(self.secret_list_stack, 1)

        self.vault_locked_view = VaultLockedView(self.on_unlock, page)
        self.secret_content = QStackedWidget(page)
        self.secret_content.addWidget(self.secret_list_view)
        self.secret_content.addWidget(self.vault_locked_view)
        page_layout.addWidget(self.secret_content, 1)
        return page

    def _update_secret_sort_icon(self, *_args):
        icon = FIF.DOWN if self.secret_sort.currentIndex() == 1 else FIF.UP
        self.secret_sort.setIcon(icon.icon())

    def _on_secret_sort_changed(self, _index):
        self._update_secret_sort_icon()
        self.refresh_secret_list(reset_page=True)

    def _on_page_changed(self, page_index):
        if page_index == self._page_index:
            return
        self._page_index = page_index
        if self._page_refresh_pending:
            return

        self._page_refresh_pending = True
        QTimer.singleShot(0, self._refresh_page_after_pager_event)

    def _refresh_page_after_pager_event(self):
        self._page_refresh_pending = False
        self.refresh_secret_list()

    def refresh_secret_list(self, *, reset_page=False):
        if not hasattr(self, "secret_list"):
            return
        if reset_page:
            self._page_index = 0

        self._status_timer.stop()
        self.secret_list.setUpdatesEnabled(False)
        try:
            self.secret_list.setRowCount(0)
            self._secret_rows.clear()

            if self.secret_service is None:
                self._secret_count = 0
                self._filtered_secret_count = 0
                self._secret_status_counts = {
                    VALID: 0,
                    EXPIRING: 0,
                    EXPIRED: 0,
                }
                self._update_secret_filter_counts()
                self._update_pagination(None)
                return

            page = self.secret_service.list_page(
                search_text=self.search_box.text(),
                status=self.secret_filter,
                descending=self.secret_sort.currentIndex() == 1,
                page_index=self._page_index,
                page_size=self._page_size,
                now=datetime.now(),
            )
            self._secret_count = page.total_count
            self._filtered_secret_count = page.filtered_count
            self._secret_status_counts = dict(page.status_counts)
            self._page_index = page.page_index

            for secret in page.items:
                self.add_secret_item(secret)

            self._update_secret_filter_counts()
            self.results_content.setCurrentWidget(
                self.secret_list
                if self._filtered_secret_count
                else self.no_results_view
            )
            self._update_pagination(page)
        finally:
            QTimer.singleShot(0, self._finish_secret_list_layout)
            self._schedule_status_update()
            self._update_page_content()

    def _update_pagination(self, page):
        filtered_count = page.filtered_count if page is not None else 0
        if filtered_count == 0:
            self.pagination_footer.setVisible(False)
            return

        page_count = (filtered_count + self._page_size - 1) // self._page_size
        first_result = self._page_index * self._page_size + 1
        last_result = min(first_result + self._page_size - 1, filtered_count)

        range_text = QCoreApplication.translate(
            "SecretManager",
            "ui.pagination.range",
        )
        for placeholder, value in (
            ("%1", first_result),
            ("%2", last_result),
            ("%3", filtered_count),
        ):
            range_text = range_text.replace(placeholder, str(value))
        self.pagination_range_label.setText(range_text)

        page_text = QCoreApplication.translate(
            "SecretManager",
            "ui.pagination.page",
        )
        page_text = page_text.replace("%1", str(self._page_index + 1))
        page_text = page_text.replace("%2", str(page_count))
        self.pagination_page_label.setText(page_text)

        with QSignalBlocker(self.pagination_pager):
            if self._pager_page_count != page_count:
                self.pagination_pager.setPageNumber(max(1, page_count))
                self._pager_page_count = page_count
            if self.pagination_pager.currentIndex() != self._page_index:
                self.pagination_pager.setCurrentIndex(self._page_index)

        self.pagination_pager.setVisible(page_count > 1)
        self.pagination_footer.setVisible(True)

    def _update_page_content(self):
        if not self._vault_unlocked or self.secret_service is None:
            self.secret_content.setCurrentWidget(self.vault_locked_view)
            return

        self.secret_content.setCurrentWidget(self.secret_list_view)
        self.secret_list_stack.setCurrentWidget(
            self.empty_state_view if self._secret_count == 0 else self.secret_list_content
        )

    def _schedule_status_update(self):
        self._status_timer.stop()
        if not self._vault_unlocked or self.secret_service is None:
            return

        next_transition = self.secret_service.next_status_transition(
            now=datetime.now(),
        )
        if next_transition is None:
            return

        milliseconds = max(
            1,
            int((next_transition - datetime.now()).total_seconds() * 1000),
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
        counts = {
            "all": self._secret_count,
            VALID: self._secret_status_counts.get(VALID, 0),
            EXPIRING: self._secret_status_counts.get(EXPIRING, 0),
            EXPIRED: self._secret_status_counts.get(EXPIRED, 0),
        }
        for key, button in self.secret_filter_buttons.items():
            button.setText(f'{self.secret_filter_labels[key]}  {counts[key]}')

    def filter_secrets(self, _text=None):
        self._search_timer.start()

    def _apply_search_filter(self):
        self.refresh_secret_list(reset_page=True)

    def _set_secret_filter(self, value):
        self.secret_filter = value
        self.secret_filter_widget.setCurrentItem(value)
        self.refresh_secret_list(reset_page=True)

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
        status_badge = InfoBadge(
            {
                VALID: QCoreApplication.translate("SecretManager", "ui.status.valid"),
                EXPIRING: QCoreApplication.translate("SecretManager", "ui.status.expiring"),
                EXPIRED: QCoreApplication.translate("SecretManager", "ui.status.expired"),
            }[status_text],
            self.secret_list,
            status_level,
        )
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
        more_button.setToolTip(QCoreApplication.translate("SecretManager", 'ui.more_options'))
        more_button.clicked.connect(lambda checked=False, name=secret.name, button=more_button: self.show_secret_menu(name, button))
        options_layout.addWidget(
            more_button,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        options_layout.addStretch(1)
        self.secret_list.setCellWidget(row, 3, options_cell)

    @staticmethod
    def _secret_status(secret):
        status = getattr(
            secret,
            "status",
            get_expiry_status(secret.expires_on, secret.expires_at_time),
        )
        levels = {
            VALID: InfoLevel.SUCCESS,
            EXPIRING: InfoLevel.WARNING,
            EXPIRED: InfoLevel.ERROR,
        }
        return status, levels[status]

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
                allow_cli=data["allow_cli"],
            )
        )
        if self._exec_secret_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        self.refresh_secret_list()

    def show_secret_menu(self, secret_name, anchor):
        if self.secret_service is None:
            return
        menu = RoundMenu(parent=self)
        copy_name_action = Action(FIF.COPY, QCoreApplication.translate("SecretManager", 'ui.copy_name'), menu)
        copy_name_action.triggered.connect(
            lambda checked=False, name=secret_name: self.copy_secret(name, copy_value=False)
        )
        copy_value_action = Action(FIF.COPY, QCoreApplication.translate("SecretManager", 'ui.copy_value'), menu)
        copy_value_action.triggered.connect(
            lambda checked=False, name=secret_name: self.copy_secret(name, copy_value=True)
        )
        edit_action = Action(FIF.EDIT, QCoreApplication.translate("SecretManager", 'ui.edit'), menu)
        edit_action.triggered.connect(lambda checked=False, name=secret_name: self.edit_secret(name))
        delete_action = Action(FIF.DELETE, QCoreApplication.translate("SecretManager", 'ui.delete'), menu)
        delete_action.triggered.connect(lambda checked=False, name=secret_name: self.delete_secret(name))
        menu.addAction(copy_name_action)
        menu.addAction(copy_value_action)
        menu.addSeparator()
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def copy_secret(self, secret_name, *, copy_value):
        if self.secret_service is None:
            return
        secret = self.secret_service.get(secret_name)
        if secret is None:
            return
        copy_text(secret.value if copy_value else secret.name)

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
                allow_cli=data["allow_cli"],
            )
        )
        if self._exec_secret_dialog(dialog) != QDialog.DialogCode.Accepted:
            return
        self.refresh_secret_list()

    def delete_secret(self, secret_name):
        if self.secret_service is None:
            return
        confirmation = ConfirmationDialog(
            QCoreApplication.translate("SecretManager", 'ui.delete_secret'),
            QCoreApplication.translate("SecretManager", 'ui.delete_1').replace("%1", secret_name),
            self,
            confirm_text=QCoreApplication.translate("SecretManager", 'ui.delete'),
            cancel_text=QCoreApplication.translate("SecretManager", 'ui.cancel_56fc52'),
        )
        if not self._exec_secret_dialog(confirmation):
            return
        if self.secret_service is None:
            return
        self.secret_service.delete(secret_name)
        self.refresh_secret_list()



