import logging
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


class SecretListLoadSignals(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int)
    finished = Signal(int)


class SecretListLoadWorker(QRunnable):
    def __init__(
        self,
        request_id,
        secret_service,
        query,
        cancel_event=None,
        *,
        refresh_status_counts=True,
        refresh_filtered_count=True,
        refresh_next_transition=True,
    ):
        super().__init__()
        self.request_id = request_id
        self.secret_service = secret_service
        self.query = query
        self.cancel_event = cancel_event or Event()
        self.refresh_status_counts = refresh_status_counts
        self.refresh_filtered_count = refresh_filtered_count
        self.refresh_next_transition = refresh_next_transition
        self.signals = SecretListLoadSignals()

    def run(self):
        try:
            if self.cancel_event.is_set():
                return

            now = self.query["now"]
            page = self.secret_service.list_page(
                **self.query,
                include_status_counts=self.refresh_status_counts,
                include_filtered_count=self.refresh_filtered_count,
            )
            if self.cancel_event.is_set():
                return

            next_transition = None
            if self.refresh_next_transition:
                next_transition = self.secret_service.next_status_transition(now=now)
                if self.cancel_event.is_set():
                    return
        except Exception as error:
            if not self.cancel_event.is_set():
                logger.error(
                    "Secret list load failed (%s).",
                    type(error).__name__,
                )
                self.signals.failed.emit(self.request_id)
        else:
            self.signals.succeeded.emit(
                self.request_id,
                (page, next_transition, self.refresh_next_transition),
            )
        finally:
            self.signals.finished.emit(self.request_id)
