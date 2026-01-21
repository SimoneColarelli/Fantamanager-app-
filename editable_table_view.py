from typing import cast
from PySide6.QtWidgets import QTableView, QAbstractItemDelegate
from PySide6.QtCore import Qt

from editable_table_model import EditableTableModel


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
        # ENTER
        # ===============================
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_enter(index)
            return

        # ===============================
        # FRECCE
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
    # ENTER LOGIC
    # =====================================
    def _handle_enter(self, index):
        if not index.isValid():
            return

        model = self.model()
        model = cast(EditableTableModel, model)

        # ➕ CELL: create record
        if (
            index.row() == 0
            and index.column() == model.columnCount() - 1
        ):
            model.create_from_row()
            return

        # normal cell → commit + move right
        self._commit_and_move(index, dx=1, dy=0)

    # =====================================
    # CORE LOGIC
    # =====================================
    def _commit_and_move(self, index, dx=0, dy=0):
        if not index.isValid():
            return

        model = self.model()
        row = index.row()
        col = index.column()

        # commit editor if editing
        editor = self.focusWidget()
        if editor:
            delegate = self.itemDelegate(index)
            delegate.commitData.emit(editor)
            delegate.closeEditor.emit(
                editor,
                QAbstractItemDelegate.EndEditHint.NoHint
            )

        new_row = row + dy
        new_col = col + dx

        if not (0 <= new_row < model.rowCount()):
            return
        if not (0 <= new_col < model.columnCount()):
            return

        next_index = model.index(new_row, new_col)
        self.setCurrentIndex(next_index)
        self.edit(next_index)
