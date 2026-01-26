from PySide6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex,
    Signal
)
from PySide6.QtGui import QColor, QFont


class EditableTableModel(QAbstractTableModel):
    
    has_pending_changes = Signal(bool)  # Signal when pending changes state changes
    
    def __init__(self, repository, fields, headers):
        super().__init__()
        self.repo = repository
        self.fields = fields
        self.headers = headers + [""]  # ➕/🗑️/✓ column
        self.new_row = {f: "" for f in self.fields}
        self.edited_cells = {}  # {row: {field: value}}
        self.original_values = {}  # {row: {field: original_value}}
        self.refresh()

    # ---------- BASIC ----------

    def refresh(self):
        self.beginResetModel()
        self.rows = self.repo.all()
        self.edited_cells = {}
        self.original_values = {}
        self.endResetModel()
        self.has_pending_changes.emit(False)

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows) + 1  # creation row

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields) + 1  # ➕/🗑️/✓

    # ---------- DATA ----------

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # ─── CREATION ROW (row 0) ─────────────────────────
        if row == 0:
            # ➕ button (last column)
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

        # Last column: 🗑️ button or 🗑️✓❌ buttons
        if col == len(self.fields):
            # Check if this row has pending changes
            has_edits = row in self.edited_cells and len(self.edited_cells[row]) > 0
            
            if role == Qt.ItemDataRole.DisplayRole:
                if has_edits:
                    return "🗑️ ✓ ❌"
                return "🗑️"
            
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(255, 0, 0)
            
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(True)
                return font
            
            return None

        if col < len(self.fields):
            field = self.fields[col]
            
            # Get value (edited or original)
            if row in self.edited_cells and field in self.edited_cells[row]:
                value = self.edited_cells[row][field]
            else:
                value = getattr(obj, field)
            
            # Background color for edited cells
            if role == Qt.ItemDataRole.BackgroundRole:
                if row in self.edited_cells and field in self.edited_cells[row]:
                    return QColor(200, 255, 200)  # Light green
            
            if role in (
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
            ):
                return value

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

        # NORMAL ROW - Track changes
        obj = self.rows[row - 1]
        field = self.fields[col]
        original_value = getattr(obj, field)
        
        # Only track if value actually changed
        if str(value) != str(original_value):
            # Initialize tracking for this row
            if row not in self.edited_cells:
                self.edited_cells[row] = {}
                self.original_values[row] = {}
            
            # Store original value if not already stored
            if field not in self.original_values[row]:
                self.original_values[row][field] = original_value
            
            # Store edited value
            self.edited_cells[row][field] = value
            
            # Emit signal that we have pending changes
            self.has_pending_changes.emit(True)
        else:
            # Value changed back to original, remove from tracking
            if row in self.edited_cells and field in self.edited_cells[row]:
                del self.edited_cells[row][field]
                del self.original_values[row][field]
                
                # Clean up empty dicts
                if not self.edited_cells[row]:
                    del self.edited_cells[row]
                    del self.original_values[row]
                
                # Check if we still have pending changes
                self.has_pending_changes.emit(bool(self.edited_cells))
        
        self.dataChanged.emit(index, index)
        # Update the action column
        action_index = self.index(row, len(self.fields))
        self.dataChanged.emit(action_index, action_index)
        
        return True

    # ---------- FLAGS ----------

    def flags(self, index):
        row = index.row()
        col = index.column()

        # CREATION ROW
        if row == 0:
            # ➕ column (last column)
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
        # 🗑️/✓ column (last column)
        if col == len(self.fields):
            return (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
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
    
    # ---------- DELETE ----------
    
    def soft_delete_row(self, row):
        if row > 0 and row <= len(self.rows):
            obj = self.rows[row - 1]
            self.repo.soft_delete(obj)
            self.refresh()
    
    # ---------- UPDATE MANAGEMENT ----------
    
    def has_changes(self):
        return bool(self.edited_cells)
    
    def commit_all_changes(self):
        """Commit all pending changes to database"""
        for row, changes in self.edited_cells.items():
            obj = self.rows[row - 1]
            for field, value in changes.items():
                setattr(obj, field, value)
        
        if self.edited_cells:
            self.repo.session.commit()
        
        self.edited_cells = {}
        self.original_values = {}
        
        # Refresh to update display
        self.beginResetModel()
        self.endResetModel()
        self.has_pending_changes.emit(False)
    
    def cancel_all_changes(self):
        """Cancel all pending changes"""
        self.edited_cells = {}
        self.original_values = {}
        
        # Refresh to update display
        self.beginResetModel()
        self.endResetModel()
        self.has_pending_changes.emit(False)
    
    def commit_row_changes(self, row):
        """Commit changes for a specific row"""
        if row in self.edited_cells:
            obj = self.rows[row - 1]
            for field, value in self.edited_cells[row].items():
                setattr(obj, field, value)
            
            self.repo.session.commit()
            
            del self.edited_cells[row]
            del self.original_values[row]
            
            # Update the entire row
            for col in range(self.columnCount()):
                index = self.index(row, col)
                self.dataChanged.emit(index, index)
            
            # Check if we still have pending changes
            self.has_pending_changes.emit(bool(self.edited_cells))
    
    def cancel_row_changes(self, row):
        """Cancel changes for a specific row"""
        if row in self.edited_cells:
            del self.edited_cells[row]
            del self.original_values[row]
            
            # Update the entire row
            for col in range(self.columnCount()):
                index = self.index(row, col)
                self.dataChanged.emit(index, index)
            
            # Check if we still have pending changes
            self.has_pending_changes.emit(bool(self.edited_cells))