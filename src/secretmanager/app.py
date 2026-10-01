import sys
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme
from .ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Secret Manager')
    setTheme(Theme.AUTO)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()
