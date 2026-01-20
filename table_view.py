from PySide6.QtWidgets import QTableView, QAbstractItemDelegate
from PySide6.QtCore import Qt


class EditableTableView(QTableView):
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()

            if index.isValid():
                editor = self.focusWidget()
                delegate = self.itemDelegate(index)

                # 🔴 QUESTO È IL PASSAGGIO CRITICO
                if editor:
                    delegate.commitData.emit(editor)
                    delegate.closeEditor.emit(
                        editor,
                        QAbstractItemDelegate.EndEditHint.NoHint
                    )

                row = index.row()
                col = index.column() + 1

                if col < self.model().columnCount():
                    next_index = self.model().index(row, col)
                    self.setCurrentIndex(next_index)
                    self.edit(next_index)

                return  # blocca comportamento standard

        super().keyPressEvent(event)
