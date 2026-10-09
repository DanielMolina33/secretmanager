from __future__ import annotations

from PySide6.QtCore import QThread


class IpcLifecycleThread(QThread):
    """Run IPC process startup or cleanup without blocking the GUI thread."""

    def __init__(self, operation: str, worker, parent=None):
        super().__init__(parent)
        if operation not in {"start", "stop"}:
            raise ValueError(f"Unsupported IPC lifecycle operation: {operation}")
        self.operation = operation
        self.worker = worker
        self.error: Exception | None = None
        self.cleanup_error: Exception | None = None
        self.restart_if_enabled = True

    def run(self) -> None:
        try:
            getattr(self.worker, self.operation)()
        except Exception as error:
            self.error = error
            if self.operation == "start":
                try:
                    self.worker.stop()
                except Exception as cleanup_error:
                    self.cleanup_error = cleanup_error
