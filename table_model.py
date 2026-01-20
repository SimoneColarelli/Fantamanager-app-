from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class EditableTableModel(QAbstractTableModel):
    def __init__(self, repository, fields, headers):
        super().__init__()
        self.repo = repository
        self.fields = fields
        self.headers = headers
        self.refresh()

    def refresh(self):
        self.beginResetModel()
        self.rows = self.repo.all()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        obj = self.rows[index.row()]
        field = self.fields[index.column()]

        if role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            return getattr(obj, field)

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            obj = self.rows[index.row()]
            field = self.fields[index.column()]
            self.repo.set_value(obj, field, value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    def flags(self, index):
        return (
            Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsEditable
        )

    def headerData(self, section, orientation, role):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]
        return None
