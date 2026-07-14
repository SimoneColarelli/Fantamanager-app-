import math
from PySide6.QtCore import (
    QAbstractTableModel,
    Qt,
    QModelIndex,
    Signal
)
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QFont
from helpers import format_date_for_display, format_value_for_display
# Import your calculation function
from constants import calculate_fascia
from repository import Repository 

class EditableTableModel(QAbstractTableModel):
    
    has_pending_changes = Signal(bool)  # Signal when pending changes state changes
    rows_committed = Signal()           # Signal emitted after any successful commit
    editing_locked_changed = Signal(bool)  # Signal when lock state changes

    def __init__(self, repository, fields, headers, computed_fields=None):
        super().__init__()
        self.repo : Repository = repository
        self.model_name = repository.model.__tablename__
        self.fields = fields
        self.headers = headers + [""]  # Add empty header for ➕/🗑️/✓/❌ column
        # computed_fields: {field_name: callable(obj) -> display_value}
        # These fields are display-only; never edited or written to the DB.
        self.computed_fields = computed_fields or {}
        self.new_row = {f: "" for f in self.fields}
        self.edited_cells = {}  # {row: {field: value}}
        self.original_values = {}  # {row: {field: original_value}}
        self.current_row = -1
        self.editing_locked = True  # When True, only row 0 (creation row) remains editable
        self.refresh()

    # ---------- BASIC ----------

    def _invalidate_computed_fields(self):
        seen = set()
        for func in self.computed_fields.values():
            owner = getattr(func, "__self__", None)
            target = owner or func
            cache_key = id(target)
            if cache_key in seen:
                continue
            seen.add(cache_key)
            invalidate = getattr(target, "invalidate_cache", None)
            if callable(invalidate):
                invalidate()

    def refresh(self):
        self.beginResetModel()
        self._invalidate_computed_fields()
        self.rows = self.repo.all()
        self.edited_cells = {}
        self.original_values = {}
        self.new_row = {f: "" for f in self.fields}
        self.endResetModel()
        self.has_pending_changes.emit(False)
    
    def set_editing_locked(self, locked: bool):
        """Lock or unlock editing for all rows except the creation row (row 0)."""
        if self.editing_locked == locked:
            return
        self.editing_locked = locked
        # Refresh all flags by notifying the view that all data changed
        self.dataChanged.emit(
            self.index(1, 0),
            self.index(self.rowCount() - 1, self.columnCount() - 1),
            [Qt.ItemDataRole.BackgroundRole]
        )
        self.editing_locked_changed.emit(locked)

    def set_current_row(self, row):
        if getattr(self, 'current_row', -1) == row:
            return
            
        old_row = getattr(self, 'current_row', -1)
        self.current_row = row
        
        if 0 <= old_row < self.rowCount():
            self.dataChanged.emit(
                self.index(old_row, 0), 
                self.index(old_row, self.columnCount() - 1), 
                [Qt.ItemDataRole.BackgroundRole]
            )
            
        if 0 <= self.current_row < self.rowCount():
            self.dataChanged.emit(
                self.index(self.current_row, 0), 
                self.index(self.current_row, self.columnCount() - 1), 
                [Qt.ItemDataRole.BackgroundRole]
            )

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows) + 1  # creation row

    def columnCount(self, parent=QModelIndex()):
        return len(self.fields) + 1  # ➕/🗑️/✓

    # ---------- DATA ----------

    SORT_ROLE = Qt.ItemDataRole.UserRole + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        # ─── CREATION ROW (row 0) ─────────────────────────
        if row == 0:
            if role == Qt.ItemDataRole.BackgroundRole:
                if getattr(self, 'current_row', -1) == 0:
                    return QColor(240, 240, 240)
                return None
            if role == self.SORT_ROLE:
                return None

            if col == len(self.fields):
                if role == Qt.ItemDataRole.DisplayRole and self._can_create():
                    return "➕"
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(0, 255, 0) if self._can_create() else QColor(160, 160, 160)
                if role == Qt.ItemDataRole.FontRole and self._can_create():
                    font = QApplication.font()
                    font.setBold(True)
                    return font
                return None

            field = self.fields[col]

            if field in self.computed_fields:
                if role == Qt.ItemDataRole.DisplayRole:
                    return "—"
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(160, 160, 160)
                return None

            value = self.new_row[field]

            if value == "":
                if role == Qt.ItemDataRole.DisplayRole:
                    return f"nuovo {field.replace('_', ' ')}"
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(160, 160, 160)
                return None

            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                return value

            return None

        # ─── NORMAL ROWS ─────────────────────────────────
        obj = self.rows[row - 1]

        if col == len(self.fields):
            has_edits = row in self.edited_cells and len(self.edited_cells[row]) > 0

            if role == Qt.ItemDataRole.BackgroundRole:
                if self.editing_locked:
                    return QColor(245, 245, 245)
                if getattr(self, 'current_row', -1) == row:
                    return QColor(240, 240, 240)

            if role == Qt.ItemDataRole.DisplayRole:
                if self.editing_locked:
                    return ""
                return "🗑️ ✓ ❌" if has_edits else "🗑️"
            if role == Qt.ItemDataRole.ForegroundRole:
                return QColor(255, 0, 0)
            if role == Qt.ItemDataRole.FontRole:
                font = QApplication.font()
                font.setBold(True)
                return font
            return None

        if col < len(self.fields):
            field = self.fields[col]

            # ── COMPUTED FIELD ──────────────────────────────
            if field in self.computed_fields:
                if role == Qt.ItemDataRole.BackgroundRole:
                    if self.editing_locked:
                        return QColor(245, 245, 245)
                    if getattr(self, 'current_row', -1) == row:
                        return QColor(240, 240, 240)
                    return None
                if role == self.SORT_ROLE:
                    return self.computed_fields[field](obj)
                if role == Qt.ItemDataRole.DisplayRole:
                    return str(self.computed_fields[field](obj))
                if role == Qt.ItemDataRole.ForegroundRole:
                    return QColor(100, 100, 100)
                return None
            # ────────────────────────────────────────────────

            if row in self.edited_cells and field in self.edited_cells[row]:
                value = self.edited_cells[row][field]
                if role == self.SORT_ROLE:
                    column = getattr(self.repo.model, field)
                    value = self.repo._convert_value(value, column.type)
            else:
                value = getattr(obj, field)
            
            if role == Qt.ItemDataRole.BackgroundRole:
                if self.editing_locked:
                    return QColor(245, 245, 245)
                if row in self.edited_cells and field in self.edited_cells[row]:
                    return QColor(200, 255, 200)
                if getattr(self, 'current_row', -1) == row:
                    return QColor(240, 240, 240)
                    
            if role == self.SORT_ROLE:
                return value
            
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
                if value is None:
                    return ""
                if role == Qt.ItemDataRole.DisplayRole:
                    from helpers import format_value_for_display
                    return format_value_for_display(value)
                return str(value)
            if self.fields[col] == "nome" and role == Qt.ItemDataRole.FontRole:
                font = QApplication.font()
                font.setBold(True)
                return font
            if self.fields[col] == "valore_svincolo" and role == Qt.ItemDataRole.FontRole:
                font = QApplication.font()
                font.setBold(True)
                return font
        return None

    # ---------- EDIT ----------

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role != Qt.ItemDataRole.EditRole:
            return False

        row = index.row()
        col = index.column()

        if col < len(self.fields) and self.fields[col] in self.computed_fields:
            return False

        # CREATION ROW — always allowed regardless of lock
        if row == 0 and col < len(self.fields):
            field_name = self.fields[col]
            
            self.new_row[field_name] = value
            self.dataChanged.emit(index, index)
            
            if field_name == "spesa":
                try:
                    spesa_val = int(value) if value else 0
                    
                    if "fascia" in self.fields:
                        new_fascia = calculate_fascia(spesa_val)
                        self.new_row["fascia"] = str(new_fascia)
                        idx = self.index(0, self.fields.index("fascia"))
                        self.dataChanged.emit(idx, idx)

                    if "valore_svincolo" in self.fields:
                        self.new_row["valore_svincolo"] = str(spesa_val)
                        idx = self.index(0, self.fields.index("valore_svincolo"))
                        self.dataChanged.emit(idx, idx)
                        
                    if "dq" in self.fields:
                        self.new_row["dq"] = "0"
                        idx = self.index(0, self.fields.index("dq"))
                        self.dataChanged.emit(idx, idx)
                        
                except (ValueError, TypeError):
                    pass

            plus_index = self.index(0, len(self.fields))
            self.dataChanged.emit(plus_index, plus_index)
            return True

        # NORMAL ROW — blocked when locked
        if self.editing_locked:
            return False

        obj = self.rows[row - 1]
        field = self.fields[col]
        original_value = getattr(obj, field)
        
        column = getattr(self.repo.model, field)
        converted_value = self.repo._convert_value(value, column.type)
        
        values_are_equal = self._values_are_equal(original_value, converted_value)
        
        if not values_are_equal:
            if row not in self.edited_cells:
                self.edited_cells[row] = {}
                self.original_values[row] = {}
            
            if field not in self.original_values[row]:
                self.original_values[row][field] = original_value
            
            self.edited_cells[row][field] = value
            self.has_pending_changes.emit(True)
        else:
            if row in self.edited_cells and field in self.edited_cells[row]:
                del self.edited_cells[row][field]
                del self.original_values[row][field]
                
                if not self.edited_cells[row]:
                    del self.edited_cells[row]
                    del self.original_values[row]
                
                self.has_pending_changes.emit(bool(self.edited_cells))
        
        self.dataChanged.emit(index, index)
        action_index = self.index(row, len(self.fields))
        self.dataChanged.emit(action_index, action_index)
        
        return True

    def _values_are_equal(self, original, converted):
        if original is None and converted is None:
            return True
        if original is None or converted is None:
            return False
        if hasattr(original, 'strftime') and hasattr(converted, 'strftime'):
            return original == converted
        if isinstance(original, bool) and isinstance(converted, bool):
            return original == converted
        if isinstance(original, (int, float)) and isinstance(converted, (int, float)):
            return original == converted
        return str(original) == str(converted)

    # ---------- FLAGS ----------

    def flags(self, index):
        row = index.row()
        col = index.column()

        # Creation row (row 0) — always fully editable regardless of lock
        if row == 0:
            if col == len(self.fields):
                return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            if col < len(self.fields) and self.fields[col] in self.computed_fields:
                return Qt.ItemFlag.ItemIsEnabled
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

        # Normal rows — read-only when locked
        if self.editing_locked:
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

        if col == len(self.fields):
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

        if col < len(self.fields):
            if self.fields[col] in self.computed_fields:
                return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

        return Qt.ItemFlag.NoItemFlags

    # ---------- HEADER ----------

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
            return ""
        return None

    # ---------- CREATE ----------

    def _can_create(self):
        for v in self.fields:
            if v in self.computed_fields:
                continue
            if v != "in_prestito_a" and v != "inizio_prestito" and v != "fine_prestito":
                if str(self.new_row[v]).strip() != "":
                    continue
                else:
                    return False
        return True
    
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

    def _fields_being_committed(self, cells_dict):
        """Return the set of field names present in a dict of row changes."""
        fields = set()
        for changes in cells_dict.values():
            fields.update(changes.keys())
        return fields
    
    def commit_all_changes(self):
        """Commit all pending changes to database"""
        try:
            touched_fields = self._fields_being_committed(self.edited_cells)

            for row, changes in self.edited_cells.items():
                obj = self.rows[row - 1]
                for field, value in changes.items():
                    column = getattr(self.repo.model, field)
                    converted_value = self.repo._convert_value(value, column.type)
                    setattr(obj, field, converted_value)
                if hasattr(self.repo, "sync_compat_fields"):
                    self.repo.sync_compat_fields(obj)
            
            if self.edited_cells:
                self.repo.session.commit()
            
            self.edited_cells = {}
            self.original_values = {}

            self.refresh()
            self.beginResetModel()
            self.endResetModel()
            self.has_pending_changes.emit(False)

            # Notify listeners (e.g. main_window) that rows were committed,
            # passing which fields changed so they can decide what to refresh.
            self.rows_committed.emit()
        except Exception as e:
            self.repo.session.rollback()
            print(f"Error committing changes: {e}")
            raise
    
    def cancel_all_changes(self):
        self.edited_cells = {}
        self.original_values = {}
        self.refresh()
        self.beginResetModel()
        self.endResetModel()
        self.has_pending_changes.emit(False)
    
    def commit_row_changes(self, row):
        """Commit changes for a specific row"""
        if row in self.edited_cells:
            try:
                obj = self.rows[row - 1]
                for field, value in self.edited_cells[row].items():
                    column = getattr(self.repo.model, field)
                    converted_value = self.repo._convert_value(value, column.type)
                    setattr(obj, field, converted_value)
                if hasattr(self.repo, "sync_compat_fields"):
                    self.repo.sync_compat_fields(obj)
                
                self.repo.session.commit()
                
                del self.edited_cells[row]
                del self.original_values[row]
                
                for col in range(self.columnCount()):
                    index = self.index(row, col)
                    self.dataChanged.emit(index, index)
                
                self.has_pending_changes.emit(bool(self.edited_cells))

                # Notify listeners
                self.rows_committed.emit()
            except Exception as e:
                self.repo.session.rollback()
                print(f"Error committing row changes: {e}")
                raise
    
    def cancel_row_changes(self, row):
        if row in self.edited_cells:
            del self.edited_cells[row]
            del self.original_values[row]
            
            for col in range(self.columnCount()):
                index = self.index(row, col)
                self.dataChanged.emit(index, index)
            
            self.has_pending_changes.emit(bool(self.edited_cells))
