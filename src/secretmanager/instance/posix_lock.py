"""Process-owned singleton lock backed by Qt shared memory on Unix."""

from __future__ import annotations

import errno
import os
import time

from PySide6.QtCore import QSharedMemory


_RECORD_MAGIC = b"SMI1"
_RECORD_SIZE = 8
_ACQUIRE_RETRY_SECONDS = 1.0
_RETRY_INTERVAL_SECONDS = 0.01


def _process_is_running(pid: int) -> bool:
    """Check a PID without treating permission errors as a free lock."""
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        if error.errno == errno.EPERM:
            return True
        # Unknown process-query failures must fail closed.
        return True
    return True


class PosixSharedMemoryLock:
    """Claim a per-user Qt shared-memory key and recover crashed owners."""

    def __init__(self, key: str):
        self.key = key
        self._memory: QSharedMemory | None = None

    def acquire(self) -> bool:
        deadline = time.monotonic() + _ACQUIRE_RETRY_SECONDS
        while True:
            memory = QSharedMemory(self.key)
            if memory.create(_RECORD_SIZE):
                self._write_owner(memory)
                self._memory = memory
                return True

            if memory.error() != QSharedMemory.SharedMemoryError.AlreadyExists:
                raise RuntimeError(
                    f"Could not create the single-instance shared memory: "
                    f"{memory.errorString()}"
                )

            if not memory.attach():
                if memory.error() == QSharedMemory.SharedMemoryError.NotFound:
                    continue
                raise RuntimeError(
                    f"Could not inspect the single-instance shared memory: "
                    f"{memory.errorString()}"
                )

            owner_pid = self._read_owner(memory)
            memory.detach()

            if owner_pid and _process_is_running(owner_pid):
                return False

            # On Unix, Qt documents that a shared segment can survive a crash.
            # Detaching the last reference removes that abandoned segment. If
            # its creator is still initializing it, the next create() will
            # continue to fail and this loop will re-read its owner record.
            if time.monotonic() >= deadline:
                return False
            time.sleep(_RETRY_INTERVAL_SECONDS)

    @staticmethod
    def _write_owner(memory: QSharedMemory) -> None:
        view = memoryview(memory.data())
        try:
            view[4:8] = os.getpid().to_bytes(4, "big", signed=False)
            view[0:4] = _RECORD_MAGIC
        finally:
            view.release()

    @staticmethod
    def _read_owner(memory: QSharedMemory) -> int | None:
        if memory.size() < _RECORD_SIZE:
            return None
        view = memoryview(memory.constData())
        try:
            if bytes(view[0:4]) != _RECORD_MAGIC:
                return None
            return int.from_bytes(view[4:8], "big", signed=False)
        finally:
            view.release()

    def release(self) -> None:
        memory, self._memory = self._memory, None
        if memory is not None and memory.isAttached():
            memory.detach()
