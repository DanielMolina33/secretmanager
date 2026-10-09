from datetime import datetime
from threading import Event

from PySide6.QtCore import (
    QEvent,
    QObject,
    QCoreApplication,
    QSignalBlocker,
    QThreadPool,
    Qt,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QDialog, QHBoxLayout, QHeaderView, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    IndeterminateProgressRing,
    PipsPager,
    PipsScrollButtonDisplayMode,
    PrimaryPushButton,
    RoundMenu,
    SearchLineEdit,
    SegmentedWidget,
    TableView,
    TitleLabel,
    qconfig,
)
from ...domain.exceptions import DuplicateSecretError, EmptySecretValueError, InvalidSecretNameError
from ...domain.expiry import EXPIRED, EXPIRING, VALID
from ...services.clipboard import copy_text
from ..dialogs.secret_dialog import SecretDialog
from ..components.dialog_base import ConfirmationDialog
from .vault_locked_view import VaultLockedView
from .secrets_table_model import SecretsTableModel
from .secrets_table_delegate import SecretsTableDelegate
from .empty_state_view import EmptyStateView
from ..workers.secret_list_load_worker import SecretListLoadWorker


class _SecretOptionsClickFilter(QObject):
    def __init__(self, trigger_rect, parent=None):
        super().__init__(parent)
        self._trigger_rect = trigger_rect

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self._trigger_rect.contains(event.globalPosition().toPoint())
        ):
            watched.setAttribute(Qt.WidgetAttribute.WA_NoMouseReplay)
        return False


class SecretsPage(QWidget):
    initialPageLoaded = Signal()

    def __init__(self, on_unlock, parent=None):
        super().__init__(parent)
        self.on_unlock = on_unlock
        self.secret_service = None
        self._secret_count = 0
        self._filtered_secret_count = 0
        self._secret_status_counts = {VALID: 0, EXPIRING: 0, EXPIRED: 0}
        self._status_counts_stale = True
        self._filtered_count_stale = True
        self._filtered_count_query = None
        self._active_page_filter_query = None
        self._next_transition_stale = True
        self._page_index = 0
        self._page_size = 25
        self._pager_page_count = 0
        self._page_refresh_pending = False
        self._page_load_generation = 0
        self._page_load_workers = {}
        self._page_load_pool = QThreadPool(self)
        self._page_load_pool.setMaxThreadCount(1)
        self._initial_page_loading = False
        self._initial_page_load_failed = False
        self._page_loading = False
        self._page_load_failed = False
        self._active_page_request_is_initial = False
        self._active_page_request_shows_loading = False
        self._active_page_request_refreshes_transition = False
        self._active_page_request_resets_scroll = False
        self._next_status_transition = None

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
        self.cancel_pending_page_load()
        self.secret_service = service
        if service is None:
            self.secret_model.set_secrets(())
            self._secret_count = 0
            self._filtered_secret_count = 0
            self._secret_status_counts = {VALID: 0, EXPIRING: 0, EXPIRED: 0}
            self._status_counts_stale = True
            self._filtered_count_stale = True
            self._filtered_count_query = None
            self._active_page_filter_query = None
            self._next_transition_stale = True
            self._page_index = 0
            self._next_status_transition = None
            self._update_secret_filter_counts()
            self._update_pagination(None)
            self._update_page_content()
            return

        self.refresh_secret_list(reset_page=True, show_loading=False)

    def load_initial_page_async(self, service):
        self.secret_service = service
        self._vault_unlocked = True
        self._start_page_load(reset_page=True, show_loading=True, initial=True)

    def _start_page_load(
        self,
        *,
        reset_page=False,
        show_loading=True,
        initial=False,
        refresh_status_counts=True,
        refresh_filtered_count=True,
        refresh_next_transition=True,
        reset_scroll_to_top=False,
    ):
        if not hasattr(self, "secret_list") or self.secret_service is None:
            return

        for _worker, cancel_event in self._page_load_workers.values():
            cancel_event.set()

        self._status_counts_stale = (
            self._status_counts_stale or refresh_status_counts
        )
        self._filtered_count_stale = (
            self._filtered_count_stale or refresh_filtered_count
        )
        self._next_transition_stale = (
            self._next_transition_stale or refresh_next_transition
        )
        refresh_status_counts = self._status_counts_stale
        refresh_filtered_count = self._filtered_count_stale
        refresh_next_transition = self._next_transition_stale

        self._page_load_generation += 1
        request_id = self._page_load_generation
        if reset_page:
            self._page_index = 0

        if refresh_next_transition:
            self._status_timer.stop()
        self.secret_list.setUpdatesEnabled(True)
        self.loading_ring.stop()
        self.loading_ring.hide()
        self.results_loading_ring.stop()
        self.results_loading_ring.hide()
        self._set_loading_error_visible(False)
        self._set_results_error_visible(False)

        self._active_page_request_is_initial = initial
        self._active_page_request_shows_loading = show_loading
        self._active_page_request_refreshes_transition = refresh_next_transition
        self._active_page_request_resets_scroll = reset_scroll_to_top
        self._initial_page_loading = initial
        self._initial_page_load_failed = False
        self._page_loading = show_loading and not initial
        self._page_load_failed = False

        if initial:
            self.loading_label.show()
            self.loading_ring.show()
            self.loading_ring.start()
        elif show_loading:
            self.pagination_footer.hide()
            self.pagination_pager.setEnabled(False)
            self.results_loading_ring.show()
            self.results_loading_ring.start()
            self.results_content.setCurrentWidget(self.results_loading_view)
        else:
            self.pagination_pager.setEnabled(True)

        self._update_page_content()

        now = datetime.now()
        query = {
            "search_text": self.search_box.text(),
            "status": self.secret_filter,
            "descending": self.secret_sort.currentIndex() == 1,
            "page_index": self._page_index,
            "page_size": self._page_size,
            "now": now,
        }
        filter_query = (query["search_text"].strip().lower(), query["status"])
        if filter_query != self._filtered_count_query:
            self._filtered_count_stale = True
        refresh_filtered_count = self._filtered_count_stale
        self._active_page_filter_query = filter_query
        cancel_event = Event()
        worker = SecretListLoadWorker(
            request_id,
            self.secret_service,
            query,
            cancel_event,
            refresh_status_counts=refresh_status_counts,
            refresh_filtered_count=refresh_filtered_count,
            refresh_next_transition=refresh_next_transition,
        )
        worker.signals.succeeded.connect(self._on_page_load_succeeded)
        worker.signals.failed.connect(self._on_page_load_failed)
        worker.signals.finished.connect(self._release_page_load_worker)
        self._page_load_workers[request_id] = (worker, cancel_event)
        self._page_load_pool.start(worker)

    def cancel_pending_page_load(self):
        self._page_load_generation += 1
        for _worker, cancel_event in self._page_load_workers.values():
            cancel_event.set()

        self._initial_page_loading = False
        self._initial_page_load_failed = False
        self._page_loading = False
        self._page_load_failed = False
        self._active_page_request_is_initial = False
        self._active_page_request_shows_loading = False
        self._active_page_request_refreshes_transition = False
        self._active_page_request_resets_scroll = False
        self._status_timer.stop()
        self.secret_list.setUpdatesEnabled(True)
        self.loading_ring.stop()
        self.loading_ring.hide()
        self.results_loading_ring.stop()
        self.results_loading_ring.hide()
        self._set_loading_error_visible(False)
        self._set_results_error_visible(False)

    def _set_loading_error_visible(self, visible):
        self.load_error_label.setVisible(visible)
        self.retry_load_button.setVisible(visible)

    def _set_results_error_visible(self, visible):
        self.results_error_label.setVisible(visible)
        self.results_retry_button.setVisible(visible)

    @Slot(int, object)
    def _on_page_load_succeeded(self, request_id, result):
        if request_id != self._page_load_generation or self.secret_service is None:
            return

        page, next_transition, transition_refreshed = result
        self.secret_list.setUpdatesEnabled(False)
        self._prepare_secret_page(page)
        self.secret_model.set_secrets(page.items)
        self._finish_page_load(
            request_id,
            page,
            next_transition,
            transition_refreshed,
        )

    def _finish_page_load(
        self,
        request_id,
        page,
        next_transition,
        transition_refreshed,
    ):
        if request_id != self._page_load_generation:
            return

        was_initial_load = self._active_page_request_is_initial
        reset_scroll_to_top = self._active_page_request_resets_scroll
        self._initial_page_loading = False
        self._initial_page_load_failed = False
        self._page_loading = False
        self._page_load_failed = False
        self._active_page_request_is_initial = False
        self._active_page_request_shows_loading = False
        self._active_page_request_refreshes_transition = False
        self._active_page_request_resets_scroll = False
        self._finish_secret_list_layout()
        if reset_scroll_to_top:
            scroll_bar = self.secret_list.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.minimum())
        if transition_refreshed:
            self._next_transition_stale = False
            self._schedule_status_timer(next_transition)
        self.loading_ring.stop()
        self.loading_ring.hide()
        self.results_loading_ring.stop()
        self.results_loading_ring.hide()
        self._show_page_results(page)
        self._update_page_content()

        if was_initial_load:
            self.initialPageLoaded.emit()

    @Slot(int)
    def _on_page_load_failed(self, request_id):
        if request_id != self._page_load_generation or self.secret_service is None:
            return

        was_initial_load = self._active_page_request_is_initial
        show_loading = self._active_page_request_shows_loading
        refresh_next_transition = self._active_page_request_refreshes_transition
        self._initial_page_loading = False
        self._page_loading = False
        self._active_page_request_is_initial = False
        self._active_page_request_shows_loading = False
        self._active_page_request_refreshes_transition = False
        self._active_page_request_resets_scroll = False
        self.loading_ring.stop()
        self.loading_ring.hide()
        self.results_loading_ring.stop()
        self.results_loading_ring.hide()

        if was_initial_load:
            self._initial_page_load_failed = True
            self.loading_label.hide()
            self._set_loading_error_visible(True)
            self._update_page_content()
        elif show_loading:
            self._page_load_failed = True
            self._set_results_error_visible(True)
            self.results_content.setCurrentWidget(self.results_error_view)
            self.pagination_footer.hide()
            self._update_page_content()
        else:
            # Keep the current page visible and retry a failed expiry refresh later.
            if self._vault_unlocked and refresh_next_transition:
                self._status_timer.start(30_000)

    @Slot(int)
    def _release_page_load_worker(self, request_id):
        self._page_load_workers.pop(request_id, None)

    def _retry_initial_page_load(self):
        if self.secret_service is not None:
            self.load_initial_page_async(self.secret_service)

    def _retry_page_load(self):
        if self.secret_service is not None:
            self.refresh_secret_list()

    def set_unlocked(self, unlocked):
        if not unlocked:
            self.cancel_pending_page_load()
        self._vault_unlocked = unlocked
        self.add_button.setEnabled(unlocked)
        self.search_box.setEnabled(unlocked)
        self._update_page_content()
        if unlocked:
            self._schedule_status_timer(self._next_status_transition)
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
        self.secret_list = TableView(self.results_content)
        self.secret_model = SecretsTableModel(
            [
                QCoreApplication.translate("SecretManager", 'ui.name'),
                QCoreApplication.translate("SecretManager", 'ui.status'),
                '',
                QCoreApplication.translate("SecretManager", 'ui.options'),
            ],
            self.secret_list,
        )
        self.secret_list.setModel(self.secret_model)
        self.secret_table_delegate = SecretsTableDelegate(self.secret_list)
        self.secret_list.setItemDelegate(self.secret_table_delegate)
        self.secret_table_delegate.optionsRequested.connect(self.show_secret_menu)
        self.secret_list.setBorderVisible(True)
        self.secret_list.setBorderRadius(8)
        self.secret_list.setAlternatingRowColors(False)
        self.secret_list.setSelectionMode(self.secret_list.SelectionMode.NoSelection)
        self.secret_list.setEditTriggers(self.secret_list.EditTrigger.NoEditTriggers)
        self.secret_list.verticalHeader().hide()
        self.secret_list.verticalHeader().setDefaultSectionSize(58)
        header = self.secret_list.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.secret_list.setColumnWidth(0, 320)
        self.secret_list.setColumnWidth(1, 118)
        self.secret_list.setColumnWidth(3, 100)
        self.secret_list.doubleClicked.connect(self._on_secret_table_double_clicked)
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

        self.results_loading_view = QWidget(self.results_content)
        results_loading_layout = QVBoxLayout(self.results_loading_view)
        results_loading_layout.setContentsMargins(24, 20, 24, 20)
        results_loading_layout.addStretch(1)
        self.results_loading_ring = IndeterminateProgressRing(
            self.results_loading_view,
            start=False,
        )
        self.results_loading_ring.setFixedSize(40, 40)
        results_loading_layout.addWidget(
            self.results_loading_ring,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        results_loading_label = BodyLabel(
            QCoreApplication.translate("SecretManager", "ui.loading_secrets"),
            self.results_loading_view,
        )
        results_loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_loading_layout.addWidget(
            results_loading_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        results_loading_layout.addStretch(1)
        self.results_content.addWidget(self.results_loading_view)

        self.results_error_view = QWidget(self.results_content)
        results_error_layout = QVBoxLayout(self.results_error_view)
        results_error_layout.setContentsMargins(24, 20, 24, 20)
        results_error_layout.addStretch(1)
        self.results_error_label = BodyLabel(
            QCoreApplication.translate("SecretManager", "ui.failed_to_load_secrets"),
            self.results_error_view,
        )
        self.results_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_error_layout.addWidget(
            self.results_error_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.results_retry_button = PrimaryPushButton(
            QCoreApplication.translate("SecretManager", "ui.retry"),
            self.results_error_view,
        )
        self.results_retry_button.clicked.connect(self._retry_page_load)
        results_error_layout.addWidget(
            self.results_retry_button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        results_error_layout.addStretch(1)
        self.results_content.addWidget(self.results_error_view)
        self._set_results_error_visible(False)
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
        self.loading_view = QWidget(page)
        loading_layout = QVBoxLayout(self.loading_view)
        loading_layout.setContentsMargins(24, 20, 24, 20)
        loading_layout.addStretch(1)
        self.loading_ring = IndeterminateProgressRing(self.loading_view, start=False)
        self.loading_ring.setFixedSize(48, 48)
        loading_layout.addWidget(
            self.loading_ring,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.loading_label = BodyLabel(
            QCoreApplication.translate("SecretManager", "ui.loading_secrets"),
            self.loading_view,
        )
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(
            self.loading_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.load_error_label = BodyLabel(
            QCoreApplication.translate("SecretManager", "ui.failed_to_load_secrets"),
            self.loading_view,
        )
        self.load_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(
            self.load_error_label,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self.retry_load_button = PrimaryPushButton(
            QCoreApplication.translate("SecretManager", "ui.retry"),
            self.loading_view,
        )
        self.retry_load_button.clicked.connect(self._retry_initial_page_load)
        loading_layout.addWidget(
            self.retry_load_button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        loading_layout.addStretch(1)
        self.loading_label.show()
        self.load_error_label.hide()
        self.retry_load_button.hide()

        self.secret_content = QStackedWidget(page)
        self.secret_content.addWidget(self.secret_list_view)
        self.secret_content.addWidget(self.vault_locked_view)
        self.secret_content.addWidget(self.loading_view)
        page_layout.addWidget(self.secret_content, 1)
        return page

    def _on_secret_table_double_clicked(self, index):
        if not index.isValid() or index.column() == 3:
            return
        secret = self.secret_model.secret_at(index.row())
        if secret is not None:
            self.edit_secret(secret.name)

    def _update_secret_sort_icon(self, *_args):
        icon = FIF.DOWN if self.secret_sort.currentIndex() == 1 else FIF.UP
        self.secret_sort.setIcon(icon.icon())

    def _on_secret_sort_changed(self, _index):
        self._update_secret_sort_icon()
        self.refresh_secret_list(
            reset_page=True,
            refresh_status_counts=False,
            refresh_filtered_count=False,
            refresh_next_transition=False,
        )

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
        self.refresh_secret_list(
            refresh_status_counts=False,
            refresh_filtered_count=False,
            refresh_next_transition=False,
            reset_scroll_to_top=True,
        )

    def refresh_secret_list(
        self,
        *,
        reset_page=False,
        show_loading=True,
        refresh_status_counts=True,
        refresh_filtered_count=True,
        refresh_next_transition=True,
        reset_scroll_to_top=False,
    ):
        self._start_page_load(
            reset_page=reset_page,
            show_loading=show_loading,
            refresh_status_counts=refresh_status_counts,
            refresh_filtered_count=refresh_filtered_count,
            refresh_next_transition=refresh_next_transition,
            reset_scroll_to_top=reset_scroll_to_top,
        )

    def _prepare_secret_page(self, page):
        if page.total_count is not None:
            self._secret_count = page.total_count
        if page.filtered_count is not None:
            self._filtered_secret_count = page.filtered_count
            self._filtered_count_query = self._active_page_filter_query
            self._filtered_count_stale = False
        if page.status_counts is not None:
            self._secret_status_counts = dict(page.status_counts)
            self._status_counts_stale = False
        self._page_index = page.page_index

        self._update_secret_filter_counts()
        self._update_pagination(page)

    def _show_page_results(self, page):
        self.results_content.setCurrentWidget(
            self.secret_list
            if self._filtered_secret_count
            else self.no_results_view
        )
        self._update_pagination(page)

    def _update_pagination(self, page):
        if self._initial_page_loading or self._page_loading or self._page_load_failed:
            self.pagination_footer.setVisible(False)
            self.pagination_pager.setEnabled(False)
            return

        self.pagination_pager.setEnabled(True)
        filtered_count = self._filtered_secret_count
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

        if self._initial_page_loading or self._initial_page_load_failed:
            self.secret_content.setCurrentWidget(self.loading_view)
            return

        self.secret_content.setCurrentWidget(self.secret_list_view)
        has_secret_page_content = (
            self._secret_count > 0
            or self._page_loading
            or self._page_load_failed
        )
        self.secret_list_stack.setCurrentWidget(
            self.secret_list_content if has_secret_page_content else self.empty_state_view
        )

    def _schedule_status_timer(self, next_transition):
        self._next_status_transition = next_transition
        self._status_timer.stop()
        if (
            not self._vault_unlocked
            or self.secret_service is None
            or next_transition is None
        ):
            return

        milliseconds = max(
            1,
            int((next_transition - datetime.now()).total_seconds() * 1000),
        )
        # QTimer's interval is a signed 32-bit millisecond value.
        self._status_timer.start(min(milliseconds, 2_147_000_000))

    def _on_status_transition(self):
        if self._vault_unlocked:
            self.refresh_secret_list(show_loading=False)

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
        self.refresh_secret_list(
            reset_page=True,
            refresh_status_counts=False,
            refresh_filtered_count=True,
            refresh_next_transition=False,
        )

    def _set_secret_filter(self, value):
        self.secret_filter = value
        self.secret_filter_widget.setCurrentItem(value)
        self.refresh_secret_list(
            reset_page=True,
            refresh_status_counts=False,
            refresh_filtered_count=True,
            refresh_next_transition=False,
        )

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

    def show_secret_menu(self, secret_name, trigger_rect):
        if self.secret_service is None:
            return

        menu = RoundMenu(parent=self)
        click_filter = _SecretOptionsClickFilter(trigger_rect, menu)
        menu.installEventFilter(click_filter)
        menu._trigger_click_filter = click_filter
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
        menu.exec(trigger_rect.bottomLeft())

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



