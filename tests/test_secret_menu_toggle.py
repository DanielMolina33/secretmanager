import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import RoundMenu

from secretmanager.ui.pages.secrets_page import _SecretOptionsClickFilter


class SecretMenuToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.parent = QWidget()
        cls.parent.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.parent.close()
        cls.app.processEvents()

    def make_menu(self):
        menu = RoundMenu(parent=self.parent)
        menu.addAction(QAction("Option", menu))
        click_filter = _SecretOptionsClickFilter(
            QRect(100, 100, 32, 32), menu
        )
        menu.installEventFilter(click_filter)
        menu._trigger_click_filter = click_filter
        return menu

    def send_outside_press(self, global_position):
        menu = self.make_menu()
        menu.popup(QPoint(10, 10))
        self.app.processEvents()
        self.assertTrue(menu.isVisible())

        local_position = menu.mapFromGlobal(global_position)
        event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(local_position),
            QPointF(global_position),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(menu, event)
        self.app.processEvents()
        return menu

    def test_click_on_same_trigger_closes_menu_without_mouse_replay(self):
        menu = self.send_outside_press(QPoint(110, 110))

        self.assertFalse(menu.isVisible())
        self.assertTrue(menu.testAttribute(Qt.WidgetAttribute.WA_NoMouseReplay))

    def test_click_elsewhere_closes_menu_with_normal_popup_behavior(self):
        menu = self.send_outside_press(QPoint(300, 300))

        self.assertFalse(menu.isVisible())
        self.assertFalse(menu.testAttribute(Qt.WidgetAttribute.WA_NoMouseReplay))

    def test_fluent_round_menu_exec_keeps_drop_down_animation(self):
        menu = self.make_menu()
        menu.exec(QPoint(110, 110))
        self.app.processEvents()

        self.assertTrue(menu.isVisible())
        self.assertIsNotNone(menu.aniManager)
        self.assertEqual(menu.aniManager.ani.state().name, "Running")
        menu.close()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
