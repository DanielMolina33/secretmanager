from PySide6.QtCore import QEvent, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetricsF, QPainter
from PySide6.QtWidgets import QStyleOptionViewItem
from qfluentwidgets import FluentIcon as FIF, TableItemDelegate, getFont, isDarkTheme

from .secrets_table_model import (
    NAME_COLUMN,
    OPTIONS_COLUMN,
    SECRET_NAME_ROLE,
    SECRET_NOTE_ROLE,
    SECRET_STATUS_ROLE,
    STATUS_COLUMN,
)
from ...domain.expiry import EXPIRED, EXPIRING, VALID


class SecretsTableDelegate(TableItemDelegate):
    """Paints secret rows as data while retaining QFluentWidgets row hover."""

    optionsRequested = Signal(str, QRect)

    _STATUS_COLORS = {
        VALID: ((15, 123, 15), (108, 203, 95), (255, 255, 255), (0, 0, 0)),
        EXPIRING: ((157, 93, 0), (255, 244, 206), (255, 255, 255), (0, 0, 0)),
        EXPIRED: ((196, 43, 28), (255, 153, 164), (255, 255, 255), (0, 0, 0)),
    }

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        option.text = ""

    def paint(self, painter, option, index):
        base_option = QStyleOptionViewItem(option)
        super().paint(painter, base_option, index)

        if index.column() == NAME_COLUMN:
            self._paint_name_and_note(painter, option, index)
        elif index.column() == STATUS_COLUMN:
            self._paint_status(painter, option, index)
        elif index.column() == OPTIONS_COLUMN:
            self._paint_options(painter, option)

    def _paint_name_and_note(self, painter, option, index):
        name = index.data(SECRET_NAME_ROLE) or ""
        note = index.data(SECRET_NOTE_ROLE) or ""
        rect = option.rect
        text_rect = QRectF(rect).adjusted(8, 0, -8, 0)
        title_font = getFont(14)
        note_font = getFont(12)
        title_metrics = QFontMetricsF(title_font)
        note_metrics = QFontMetricsF(note_font)
        title_height = title_metrics.height()

        painter.save()
        painter.setClipRect(rect)
        painter.setFont(title_font)
        painter.setPen(QColor(Qt.GlobalColor.white if isDarkTheme() else Qt.GlobalColor.black))

        if note:
            note_height = note_metrics.height()
            spacing = 2
            total_height = title_height + spacing + note_height
            top = rect.center().y() - total_height / 2
            title_rect = QRectF(
                text_rect.left(), top, text_rect.width(), title_height
            )
            note_rect = QRectF(
                text_rect.left(), top + title_height + spacing,
                text_rect.width(), note_height,
            )
            title = title_metrics.elidedText(
                name, Qt.TextElideMode.ElideRight, int(text_rect.width())
            )
            note_text = note_metrics.elidedText(
                note, Qt.TextElideMode.ElideRight, int(text_rect.width())
            )
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )
            painter.setFont(note_font)
            painter.setPen(QColor("#d2d2d2" if isDarkTheme() else "#606060"))
            painter.drawText(
                note_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                note_text,
            )
        else:
            title = title_metrics.elidedText(
                name, Qt.TextElideMode.ElideRight, int(text_rect.width())
            )
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title,
            )

        painter.restore()

    def _paint_status(self, painter, option, index):
        status = index.data(SECRET_STATUS_ROLE)
        colors = self._STATUS_COLORS.get(status)
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if colors is None or not text:
            return

        light_background, dark_background, light_text, dark_text = colors
        dark = isDarkTheme()
        background = QColor(*(dark_background if dark else light_background))
        foreground = QColor(*(dark_text if dark else light_text))
        font = getFont(11)
        metrics = QFontMetricsF(font)
        height = metrics.height() + 5
        width = metrics.horizontalAdvance(text) + 10
        badge_rect = QRectF(
            option.rect.center().x() - width / 2,
            option.rect.center().y() - height / 2,
            width,
            height,
        )

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(option.rect)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(badge_rect, height / 2, height / 2)
        painter.setFont(font)
        painter.setPen(foreground)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    @staticmethod
    def _options_button_rect(rect):
        return QRect(
            rect.x() + (rect.width() - 32) // 2,
            rect.y() + (rect.height() - 32) // 2,
            32,
            32,
        )

    def _paint_options(self, painter, option):
        button_rect = self._options_button_rect(option.rect)
        icon_rect = QRect(0, 0, 16, 16)
        icon_rect.moveCenter(button_rect.center())
        FIF.MORE.icon().paint(painter, icon_rect)

    def editorEvent(self, event, model, option, index):
        if (
            index.column() != OPTIONS_COLUMN
            or event.type() != QEvent.Type.MouseButtonRelease
            or event.button() != Qt.MouseButton.LeftButton
            or not self._options_button_rect(option.rect).contains(
                event.position().toPoint()
            )
        ):
            return super().editorEvent(event, model, option, index)

        secret_name = index.data(SECRET_NAME_ROLE)
        view = self.parent()
        if secret_name and view is not None:
            button_rect = self._options_button_rect(option.rect)
            global_button_rect = QRect(
                view.viewport().mapToGlobal(button_rect.topLeft()),
                button_rect.size(),
            )
            self.optionsRequested.emit(secret_name, global_button_rect)
            return True

        return False

