import sys
from PySide6.QtWidgets import QApplication
from .settings_config import load_app_config
from .ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Secret Manager')
    load_app_config()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()