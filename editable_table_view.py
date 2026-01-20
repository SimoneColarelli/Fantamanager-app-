from PySide6.QtWidgets import QTableView, QAbstractItemDelegate
from PySide6.QtCore import Qt


class EditableTableView(QTableView):

    def keyPressEvent(self, event):
        key = event.key()
        index = self.currentIndex()

        arrows = (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down
        )

        # ===============================
        # ENTER → conferma + destra
        # ===============================
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit_and_move(index, dx=1, dy=0)
            return

        # ===============================
        # FRECCE → movimento
        # ===============================
        if key in arrows:
            dx, dy = 0, 0

            if key == Qt.Key.Key_Left:
                dx = -1
            elif key == Qt.Key.Key_Right:
                dx = 1
            elif key == Qt.Key.Key_Up:
                dy = -1
            elif key == Qt.Key.Key_Down:
                dy = 1

            self._commit_and_move(index, dx, dy)
            return

        super().keyPressEvent(event)

    # =====================================
    # CORE LOGIC
    # =====================================
    def _commit_and_move(self, index, dx=0, dy=0):
        if not index.isValid():
            return

        model = self.model()
        row = index.row()
        col = index.column()

        # 👉 Se stiamo editando: commit esplicito
        editor = self.focusWidget()
        if editor:
            delegate = self.itemDelegate(index)
            delegate.commitData.emit(editor)
            delegate.closeEditor.emit(
                editor,
                QAbstractItemDelegate.EndEditHint.NoHint
            )

        # 👉 Calcolo nuova posizione
        new_row = row + dy
        new_col = col + dx

        if not (0 <= new_row < model.rowCount()):
            return

        if not (0 <= new_col < model.columnCount()):
            return

        next_index = model.index(new_row, new_col)
        self.setCurrentIndex(next_index)
        self.edit(next_index)
