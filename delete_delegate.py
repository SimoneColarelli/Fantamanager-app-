from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtGui import QIcon

class DeleteDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_MouseOver:
            icon = QIcon.fromTheme("user-trash")
            icon.paint(painter, option.rect)
