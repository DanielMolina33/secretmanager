from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QCoreApplication

from ...domain.expiry import EXPIRED, EXPIRING, VALID


NAME_COLUMN = 0
STATUS_COLUMN = 1
SPACER_COLUMN = 2
OPTIONS_COLUMN = 3
COLUMN_COUNT = 4

SECRET_NAME_ROLE = int(Qt.ItemDataRole.UserRole) + 1
SECRET_NOTE_ROLE = int(Qt.ItemDataRole.UserRole) + 2
SECRET_STATUS_ROLE = int(Qt.ItemDataRole.UserRole) + 3


class SecretsTableModel(QAbstractTableModel):
    """Page-sized, non-sensitive data model for the secrets table."""

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self._headers = tuple(headers)
        self._secrets = ()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._secrets)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else COLUMN_COUNT

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
            and 0 <= section < len(self._headers)
        ):
            return self._headers[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._secrets)):
            return None

        secret = self._secrets[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if column == NAME_COLUMN:
                return secret.name
            if column == STATUS_COLUMN:
                status_key = {
                    VALID: "ui.status.valid",
                    EXPIRING: "ui.status.expiring",
                    EXPIRED: "ui.status.expired",
                }.get(secret.status)
                return (
                    QCoreApplication.translate("SecretManager", status_key)
                    if status_key
                    else ""
                )
            return ""

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == NAME_COLUMN:
                return secret.name
            if column == OPTIONS_COLUMN:
                return QCoreApplication.translate(
                    "SecretManager", "ui.more_options"
                )
            return None

        if role == SECRET_NAME_ROLE:
            return secret.name
        if role == SECRET_NOTE_ROLE:
            return secret.note or ""
        if role == SECRET_STATUS_ROLE:
            return secret.status

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in (STATUS_COLUMN, OPTIONS_COLUMN):
                return Qt.AlignmentFlag.AlignCenter

        return None

    def set_secrets(self, secrets):
        self.beginResetModel()
        self._secrets = tuple(secrets)
        self.endResetModel()

    def secret_at(self, row):
        if 0 <= row < len(self._secrets):
            return self._secrets[row]
        return None
