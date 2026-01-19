from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QRect, QPoint


class DeleteButtonDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_MouseOver:
            icon = QIcon.fromTheme("user-trash")
            rect = QRect(
                option.rect.right() - 24,
                option.rect.top() + 4,
                16,
                16
            )
            icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter)
