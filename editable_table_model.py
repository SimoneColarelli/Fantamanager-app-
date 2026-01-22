from PySide6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex
)
from PySide6.QtGui import QColor
from PySide6.QtGui import QColor, QFont



class EditableTableModel(QAbstractTableModel):
    def __init__(self, repository, fields, headers):
        super().__init__()
        self.repo = repository
        self.fields = fields
        self.headers = headers + [""]  # colonna +
        self.new_row = {f: "" for f in self.fields}
        self.refresh()

    # ---------- BASIC ----------

    def refresh(self):
        self.beginResetModel()
        self.rows = self.repo.all()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows) + 1  # creation row

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields) + 1

    # ---------- DATA ----------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # ─── CREATION ROW (row 0) ─────────────────────────
        if row == 0:
            # ➕ button
            if col == len(self.fields):

                if role == Qt.ItemDataRole.DisplayRole and self._can_create():
                    return "➕" 

                if role == Qt.ItemDataRole.ForegroundRole:
                    return (
                        QColor(0, 255, 0)
                        if self._can_create()
                        else QColor(160, 160, 160)
                    )

                if role == Qt.ItemDataRole.FontRole and self._can_create():
                    font = QFont()
                    font.setBold(True)
                    return font

                return None


            field = self.fields[col]
            value = self.new_row[field]

            # placeholder
            if value == "":
                if role == Qt.ItemDataRole.DisplayRole:
                    return f"nuovo {field.replace('_', ' ')}"
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(160, 160, 160)
                return None

            # real value
            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ):
                return value

            return None

        # ─── NORMAL ROWS ─────────────────────────────────
        obj = self.rows[row - 1]

        if col < len(self.fields):
            field = self.fields[col]
            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ):
                return getattr(obj, field)

        return None

    # ---------- EDIT ----------

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()

        # CREATION ROW
        if row == 0 and col < len(self.fields):
            self.new_row[self.fields[col]] = value
            self.dataChanged.emit(index, index)
            plus_index = self.index(0, len(self.fields))
            self.dataChanged.emit(plus_index, plus_index)
            return True

        # NORMAL ROW
        obj = self.rows[row - 1]
        field = self.fields[col]
        setattr(obj, field, value)
        self.repo.session.commit()
        self.dataChanged.emit(index, index)
        return True

    # ---------- FLAGS ----------

    def flags(self, index):
        row = index.row()
        col = index.column()

        # CREATION ROW
        if row == 0:
            # ➕ column
            if col == len(self.fields):
                return (
                    Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                )

            # editable fields
            return (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )

        # NORMAL ROWS
        if col < len(self.fields):
            return (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )

        return Qt.ItemFlag.NoItemFlags


    # ---------- HEADER ----------

    def headerData(self, section, orientation, role):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]
        return None

    # ---------- CREATE ----------

    def _can_create(self):
        return all(str(v).strip() != "" for v in self.new_row.values())

    def create_from_row(self):
        if not self._can_create():
            return
        self.repo.create(self.new_row)
        self.new_row = {f: "" for f in self.fields}
        self.refresh()
