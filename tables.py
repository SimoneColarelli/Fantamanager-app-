from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QTimer
from PySide6.QtGui import QColor


class EditableTableModel(QAbstractTableModel):
    def __init__(self, session, model_cls, fields, headers, undo_manager):
        super().__init__()
        self.session = session
        self.model_cls = model_cls
        self.fields = fields
        self.headers = headers
        self.undo = undo_manager

        self.hovered_row = None
        self.trash_opacity = 0.0

        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self._fade_step)

        self.refresh()

    # ---------------- CORE ----------------

    def refresh(self):
        self.db_rows = self.session.query(self.model_cls).all()
        self.layoutChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        return len(self.db_rows) + 1  # +1 creation row

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields) + 1  # +1 delete column

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.headers[section] if section < len(self.headers) else ""
        return None

    # ---------------- DATA ----------------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # 🗑 DELETE COLUMN
        if col == len(self.fields):
            if row != 0 and row == self.hovered_row:
                if role == Qt.ItemDataRole.DisplayRole:
                    return "🗑"
                if role == Qt.ItemDataRole.ForegroundRole:
                    alpha = int(255 * self.trash_opacity)
                    return QColor(200, 0, 0, alpha)
            return None

        field = self.fields[col]

        # 🔹 PLACEHOLDER (ROW 0)
        if row == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return f"nuovo {self.headers[col].lower()}"
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(160, 160, 160)
            return None

        # 🔹 NORMAL DATA
        obj = self.db_rows[row - 1]

        if role == Qt.ItemDataRole.DisplayRole:
            value = getattr(obj, field)
            return "" if value is None else str(value)

        return None

    def flags(self, index):
        if index.column() == len(self.fields):
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    # ---------------- EDIT ----------------

    def setData(self, index, value, role):
        if role != Qt.ItemDataRole.EditRole:
            return False

        if value is None or str(value).strip() == "":
            return False

        row = index.row()
        col = index.column()
        field = self.fields[col]

        self.undo.snapshot()

        # ➕ INSERT
        if row == 0:
            obj = self.model_cls()
            setattr(obj, field, value)
            self.session.add(obj)
            self.session.commit()
            self.refresh()
            return True

        # ✏ UPDATE
        obj = self.db_rows[row - 1]
        setattr(obj, field, value)
        self.session.commit()
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.EditRole])
        return True

    # ---------------- DELETE ----------------

    def delete_row(self, row):
        if row == 0:
            return
        self.undo.snapshot()
        self.session.delete(self.db_rows[row - 1])
        self.session.commit()
        self.refresh()

    # ---------------- HOVER + FADE ----------------

    def set_hovered_row(self, row):
        if self.hovered_row != row:
            self.hovered_row = row
            self.trash_opacity = 0.0
            if row not in (None, 0):
                self.fade_timer.start(30)
            else:
                self.fade_timer.stop()
            self.layoutChanged.emit()

    def _fade_step(self):
        self.trash_opacity += 0.15
        if self.trash_opacity >= 1.0:
            self.trash_opacity = 1.0
            self.fade_timer.stop()
        self.layoutChanged.emit()