from __future__ import annotations

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from qfluentwidgets import FluentWindow, Theme, setTheme


@unittest.skipIf(
    sys.platform == "darwin"
    and os.environ.get("QT_QPA_PLATFORM") == "offscreen",
    "The macOS frameless-window smoke test requires the native Cocoa QPA plugin.",
)
class PhaseZeroQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_py_side_and_fluent_window_initialize_portably(self):
        setTheme(Theme.AUTO)
        window = FluentWindow()
        window.resize(640, 480)
        window.show()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        window.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
