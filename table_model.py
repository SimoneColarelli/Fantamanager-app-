from PySide6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex
)


class EditableTableModel(QAbstractTableModel):
    def __init__(self, repository, fields, headers):
        super().__init__()
        self.repo = repository
        self.fields = fields
        self.headers = headers + [""]  # colonna +
        self.refresh()

        # creation row buffer
        self.new_row = {f: "" for f in self.fields}

    # ---------- BASIC ----------

    def refresh(self):
        self.beginResetModel()
        self.rows = self.repo.all()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        # +1 for creation row
        return len(self.rows) + 1

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields) + 1  # + button column

    # ---------- DATA ----------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # CREATION ROW
        if row == len(self.rows):
            if col == len(self.fields):
                if role == Qt.ItemDataRole.DisplayRole:
                    return "➕"
                if role == Qt.ItemDataRole.ForegroundRole:
                    return (
                        Qt.GlobalColor.darkGreen
                        if self._can_create()
                        else Qt.GlobalColor.gray
                    )
                return None

            field = self.fields[col]
            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ):
                return self.new_row[field]
            return None

        # NORMAL ROWS
        obj = self.rows[row]
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
        if row == len(self.rows):
            if col < len(self.fields):
                field = self.fields[col]
                self.new_row[field] = value
                self.dataChanged.emit(index, index)
                return True
            return False

        # NORMAL ROW
        obj = self.rows[row]
        field = self.fields[col]
        setattr(obj, field, value)
        self.repo.session.commit()
        self.dataChanged.emit(index, index)
        return True

    # ---------- FLAGS ----------

    def flags(self, index):
        row = index.row()
        col = index.column()

        if row == len(self.rows):
            if col == len(self.fields):
                return (
                    Qt.ItemFlag.ItemIsEnabled
                    if self._can_create()
                    else Qt.ItemFlag.NoItemFlags
                )
            return (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )

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
