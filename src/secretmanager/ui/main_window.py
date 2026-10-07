import sys
from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QDialog
from qfluentwidgets import FluentIcon as FIF,FluentWindow,NavigationItemPosition
from ..database.database import Database
from ..repositories.sqlite_secret_repository import SqliteSecretRepository
from ..services.secret_service import SecretService
from .dialogs.master_password_dialog import MasterPasswordDialog
from .dialogs.master_password_change_dialog import MasterPasswordChangeDialog
from .dialogs.recovery_kit_dialog import (
    MasterPasswordConfirmationDialog,
    RecoveryDialog,
    RecoveryKitDisplayDialog,
)
from .pages.secrets_page import SecretsPage
from .pages.settings_page import SettingsPage
from .appearance.theme_manager import ThemeManager
from ..ipc import LocalSecretServer
from ..paths import get_data_dir
from ..settings_config import app_config
from ..system_events import SystemEventMonitor
from ..vault_manager import VaultManager
class MainWindow(FluentWindow):
    # These values must exist before super().__init__() returns.
    # FluentWindow creates child widgets during construction, and Qt may send
    # events before MainWindow initialization has completed.
    vault = None
    database = None
    secret_service = None

    def __init__(self):
        super().__init__()

        self.setWindowTitle(QCoreApplication.translate("SecretManager", 'ui.secret_manager'))
        self.setMinimumSize(900, 600)
        self.resize(900, 600)
        # self.resize(1100, 700)

        self.auto_lock_timeout = int(app_config.autoLockMinutes.value) * 60 * 1000

        self.auto_lock_timer = QTimer(self)
        self.auto_lock_timer.setSingleShot(True)
        app_config.autoLockMinutes.valueChanged.connect(self._auto_lock_minutes_changed)
        self.auto_lock_timer.timeout.connect(
            self._auto_lock_vault
        )

        self.vault_manager = VaultManager(get_data_dir())
        self.ipc_server = None

        self.theme_manager = ThemeManager(self)

        self._build_pages()
        self._configure_navigation()
        self._configure_shortcuts()
        self.system_event_monitor = SystemEventMonitor(self, self)
        self.system_event_monitor.lockRequested.connect(
            self._lock_vault
        )
        self._update_vault_ui()

        # IMPORTANTE:
        # Install the filter only after FluentWindow has finished construction.
        QApplication.instance().installEventFilter(
            self
        )

        # Initialize the vault after the window has been fully constructed.
        QTimer.singleShot(
            0,
            self._initialize_vault,
        )

    # ------------------------------------------------------------------
    # Application state
    # ------------------------------------------------------------------



    def closeEvent(self, event):
        system_event_monitor = getattr(
            self,
            "system_event_monitor",
            None,
        )
        if system_event_monitor is not None:
            system_event_monitor.close()

        database, self.database = self.database, None
        self._stop_ipc_server()
        if database is not None:
            database.close()
        if self.vault is not None:
            self.vault.lock()
        self.auto_lock_timer.stop()
        self.theme_manager.close()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        """
        Handles activity used by the auto-lock timer.

        This method can be called by Qt while MainWindow is being created
        or destroyed, so it must never assume that instance attributes
        already exist.
        """

        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self.theme_manager.apply_system_accent()

        vault = getattr(
            self,
            "vault",
            None,
        )

        if (
            vault is not None
            and vault.is_unlocked
            and event.type()
            in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.Wheel,
                QEvent.Type.KeyPress,
            )
        ):
            self._reset_auto_lock_timer()

        return super().eventFilter(
            watched,
            event,
        )

    def _auto_lock_vault(self):
        vault = getattr(
            self,
            "vault",
            None,
        )

        if (
            vault is None
            or not vault.is_unlocked
        ):
            return

        self._lock_vault()

    def _reset_auto_lock_timer(self):
        vault = getattr(
            self,
            "vault",
            None,
        )

        timer = getattr(
            self,
            "auto_lock_timer",
            None,
        )

        if (
            vault is None
            or not vault.is_unlocked
            or timer is None
        ):
            return

        timer.start(
            self.auto_lock_timeout
        )

    def _start_auto_lock_timer(self):
        vault = getattr(
            self,
            "vault",
            None,
        )

        timer = getattr(
            self,
            "auto_lock_timer",
            None,
        )

        if (
            vault is None
            or not vault.is_unlocked
            or timer is None
        ):
            return

        timer.start(
            self.auto_lock_timeout
        )

    # ------------------------------------------------------------------
    # Vault
    # ------------------------------------------------------------------

    def _initialize_vault(self):
        if self.vault_manager.exists:
            # An existing vault starts locked. The user can open the unlock
            # dialog with the interface button.
            self._update_vault_ui()
            return

        self._create_vault()
        self._update_vault_ui()

    def _create_vault(self):
        dialog = MasterPasswordDialog(
            self,
            create_mode=True,
        )

        if (
            dialog.exec()
            != QDialog.DialogCode.Accepted
        ):
            dialog.clear_sensitive_data()
            QApplication.quit()
            return False

        self.vault = (
            self.vault_manager.create(
                dialog.password
            )
        )
        dialog.clear_sensitive_data()

        self.database = Database(
            self.vault_manager.database_path,
            self.vault.get_dek(),
        )

        self.database.create_tables()

        repository = SqliteSecretRepository(
            self.database.Session,
            self.vault.get_dek,
        )

        self.secret_service = SecretService(repository)
        self.secrets_page.set_service(self.secret_service)
        self._start_ipc_server()

        self._start_auto_lock_timer()

        return True

    def _unlock_vault(self):
        dialog = MasterPasswordDialog(
            self,
            create_mode=False,
            recovery_available=self.vault_manager.recovery_configured,
        )
        dialog.set_password_validator(self.vault_manager.unlock)
        dialog.start_unlock_cooldown(self.vault_manager.unlock_cooldown_remaining)
        result = dialog.exec()
        if dialog.recovery_requested:
            dialog.clear_sensitive_data()
            recovery_dialog = RecoveryDialog(self.vault_manager.recover, self)
            if recovery_dialog.exec() != QDialog.DialogCode.Accepted:
                recovery_dialog.clear_sensitive_data()
                return False
            self.vault = recovery_dialog.recovered_vault
            recovery_dialog.clear_sensitive_data()
        elif result == QDialog.DialogCode.Accepted:
            self.vault = dialog.authenticated_value
            dialog.clear_sensitive_data()
        else:
            dialog.clear_sensitive_data()
            return False

        self.database = Database(
            self.vault_manager.database_path,
            self.vault.get_dek(),
        )
        repository = SqliteSecretRepository(
            self.database.Session,
            self.vault.get_dek,
        )

        self.secret_service = SecretService(repository)
        self.secrets_page.set_service(self.secret_service)
        self._start_ipc_server()

        self._start_auto_lock_timer()

        return True

    def _start_ipc_server(self):
        self._stop_ipc_server()
        if self.secret_service is None:
            return
        server = LocalSecretServer(
            self.vault_manager.data_dir,
            self.secret_service.get,
        )
        try:
            server.start()
        except (OSError, RuntimeError):
            # Keep the GUI vault usable if local CLI IPC cannot start.
            import logging
            logging.getLogger(__name__).exception(
                "Could not start the local CLI IPC server."
            )
            return
        self.ipc_server = server

    def _stop_ipc_server(self):
        server = getattr(self, "ipc_server", None)
        self.ipc_server = None
        if server is not None:
            server.close()

    def _lock_vault(self):
        vault = getattr(
            self,
            "vault",
            None,
        )

        if (
            vault is None
            or not vault.is_unlocked
        ):
            return

        timer = getattr(
            self,
            "auto_lock_timer",
            None,
        )

        if timer is not None:
            timer.stop()

        database, self.database = self.database, None
        self._stop_ipc_server()
        if database is not None:
            database.close()
        self.secrets_page.reject_active_secret_dialog()

        vault.lock()

        self.secret_service = None

        self.secrets_page.set_service(self.secret_service)
        self._update_vault_ui()

    def _unlock_vault_from_ui(self):
        if self._unlock_vault():
            self._update_vault_ui()

    def _toggle_vault_lock(self):
        vault = getattr(
            self,
            "vault",
            None,
        )

        if (
            vault is not None
            and vault.is_unlocked
        ):
            self._lock_vault()
        else:
            self._unlock_vault_from_ui()

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def _update_vault_ui(self):
        if not hasattr(self, "secrets_page"):
            return
        unlocked = self.vault is not None and self.vault.is_unlocked
        self.lock_shortcut.setEnabled(unlocked)
        self.lock_button.setVisible(unlocked)
        self.secrets_page.set_unlocked(unlocked)
        if hasattr(self, "settings_page"):
            self.settings_page.set_master_password_state(unlocked)
            self.settings_page.set_recovery_state(
                self.vault_manager.recovery_configured,
                unlocked,
            )

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def _build_pages(self):
        self.secrets_page = SecretsPage(self._unlock_vault_from_ui, self)
        self.secrets_page.setObjectName("secretsPage")
        mica_available = self.isMicaEffectEnabled()
        self.settings_page = SettingsPage(
            self,
            mica_available=mica_available,
        )
        self.settings_page.setObjectName("settingsPage")
        self.settings_page.themeChanged.connect(self._theme_selection_changed)
        self.settings_page.micaChanged.connect(self.setMicaEffectEnabled)
        self.settings_page.configureRecoveryRequested.connect(self._configure_recovery_kit)
        self.settings_page.disableRecoveryRequested.connect(self._disable_recovery_kit)
        self.settings_page.changeMasterPasswordRequested.connect(self._change_master_password)
        self.settings_page.settingsRestored.connect(self._settings_restored)
        self.settings_page.set_master_password_state(
            self.vault is not None and self.vault.is_unlocked,
        )
        self.settings_page.set_recovery_state(
            self.vault_manager.recovery_configured,
            self.vault is not None and self.vault.is_unlocked,
        )
        self.setMicaEffectEnabled(app_config.micaEnabled.value)

    def _configure_navigation(self):
        self.addSubInterface(
            self.secrets_page,
            FIF.VPN,
            QCoreApplication.translate("SecretManager", 'ui.secrets'),
        )

        self.addSubInterface(
            self.settings_page,
            FIF.SETTING,
            QCoreApplication.translate("SecretManager", 'ui.settings'),
        )

        self.lock_button = self.navigationInterface.addItem(
            routeKey="vault-lock",
            icon=FIF.POWER_BUTTON,
            text=QCoreApplication.translate("SecretManager", 'ui.lock'),
            onClick=self._toggle_vault_lock,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
    def _change_master_password(self):
        if self.vault is None or not self.vault.is_unlocked:
            return

        dialog = MasterPasswordChangeDialog(self)
        dialog.set_change_handler(self.vault_manager.change_master_password)
        try:
            dialog.exec()
        finally:
            dialog.clear_sensitive_data()

    def _configure_recovery_kit(self):
        if self.vault is None or not self.vault.is_unlocked:
            return

        replacing = self.vault_manager.recovery_configured
        content = (
            QCoreApplication.translate("SecretManager", 'ui.confirm_your_master_password_to_prepare_another_kit')
            if replacing
            else QCoreApplication.translate("SecretManager", 'ui.confirm_your_master_password_to_set_up_an_optional_r')
        )
        password_dialog = MasterPasswordConfirmationDialog(
            self,
            title=QCoreApplication.translate("SecretManager", 'ui.confirm_master_password_73641c'),
            content=content,
            action_text=QCoreApplication.translate("SecretManager", 'ui.continue'),
        )
        password_dialog.set_validator(self.vault_manager.prepare_recovery_kit)
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            password_dialog.clear_sensitive_data()
            return

        pending = password_dialog.authenticated_value
        password_dialog.clear_sensitive_data()
        kit_dialog = RecoveryKitDisplayDialog(
            pending.code,
            lambda: self.vault_manager.commit_recovery_kit(pending),
            self,
            replacing=replacing,
        )
        if kit_dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings_page.set_recovery_state(True, True)
        kit_dialog.clear_sensitive_data()

    def _disable_recovery_kit(self):
        if self.vault is None or not self.vault.is_unlocked:
            return

        dialog = MasterPasswordConfirmationDialog(
            self,
            title=QCoreApplication.translate("SecretManager", 'ui.disable_recovery_kit'),
            content=QCoreApplication.translate("SecretManager", 'ui.confirm_your_master_password_the_kit_will_no_longer'),
            action_text=QCoreApplication.translate("SecretManager", 'ui.disable'),
        )
        dialog.set_validator(self.vault_manager.disable_recovery_kit)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings_page.set_recovery_state(False, True)
        dialog.clear_sensitive_data()

    def _configure_shortcuts(self):
        sequence = QKeySequence.fromString(
            str(app_config.lockShortcut.value),
            QKeySequence.SequenceFormat.PortableText,
        )
        if sequence.isEmpty():
            sequence = QKeySequence(app_config.lockShortcut.default)
        self.lock_shortcut = QShortcut(sequence, self)
        self.lock_shortcut.activated.connect(self._lock_vault)
        app_config.lockShortcut.valueChanged.connect(self._lock_shortcut_changed)

    def _lock_shortcut_changed(self, portable_text):
        sequence = QKeySequence.fromString(
            str(portable_text),
            QKeySequence.SequenceFormat.PortableText,
        )
        if not sequence.isEmpty():
            self.lock_shortcut.setKey(sequence)

    def _auto_lock_minutes_changed(self, minutes):
        self.auto_lock_timeout = int(minutes) * 60 * 1000
        self._start_auto_lock_timer()

    def _settings_restored(self):
        theme_indices = {"AUTO": 0, "LIGHT": 1, "DARK": 2}
        self.theme_manager.set_mode_from_index(
            theme_indices[app_config.themeMode.value.name]
        )
        self.setMicaEffectEnabled(app_config.micaEnabled.value)


    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def _theme_selection_changed(self, index):
        self.theme_manager.set_mode_from_index(index)

    def refresh_secret_list(self):
        self.secrets_page.refresh_secret_list()
