from typing import cast
from PySide6.QtWidgets import QTableView, QAbstractItemDelegate, QMessageBox
from PySide6.QtCore import Qt, QTimer, Signal, QPoint, QSortFilterProxyModel
from PySide6.QtGui import QCursor

from editable_table_model import EditableTableModel
from boolean_delegate import BooleanDelegate
from models import Fantasquadra


class EditableTableView(QTableView):
    
    item_deleted = Signal()  # Signal to notify when item is deleted
    item_restored = Signal()  # Signal to notify when item is restored
    
    def __init__(self):
        super().__init__()
        self._boolean_delegate = BooleanDelegate()
        # Rimuove lo sfondo blu standard di Qt dalla cella selezionata 
        # in modo che il colore grigio chiaro del nostro modello sia visibile
        self.setStyleSheet("""
            QTableView::item:selected {
                background-color: transparent;
                color: black;
            }
        """)

    def get_base_model(self):
        """Helper to get the original EditableTableModel, bypassing any Proxy."""
        model = self.model()
        if isinstance(model, QSortFilterProxyModel):
            return model.sourceModel()
        return model
    
    def setModel(self, model):
        """Override setModel to set delegates for boolean columns"""
        super().setModel(model)
        
        if model:
            # Estraiamo il modello base per leggere attributi come 'fields' e 'repo'
            base_model = self.get_base_model()
            
            # Set boolean delegate for boolean columns
            for col, field in enumerate(base_model.fields): #type: ignore
                column = getattr(base_model.repo.model, field) #type: ignore
                column_type = type(column.type).__name__
                
                if field == "squadra":
                    from squadra_delegate import SquadraDelegate
                    self.setItemDelegateForColumn(col, SquadraDelegate())
                if column_type == 'Boolean':
                    self.setItemDelegateForColumn(col, self._boolean_delegate)
                if field == 'fascia':
                    from int_delegate import FasciaDelegate
                    self.setItemDelegateForColumn(col, FasciaDelegate())
                if field == 'in_prestito_a':
                    from squadra_delegate import SquadraDelegate
                    self.setItemDelegateForColumn(col, SquadraDelegate())
                if column_type == 'Date':
                    # Use date delegate
                    from date_delegate import DataAcquistoDelegate, ScadenzaContrattoDelegate, InizioPrestitoDelegate, FinePrestitoDelegate
                    if field == 'data_acquisto':
                        self.setItemDelegateForColumn(col, DataAcquistoDelegate())
                    elif field == 'scadenza_contratto':
                        data_acquisto_col_index = base_model.fields.index('data_acquisto') #type: ignore
                        self.setItemDelegateForColumn(col, ScadenzaContrattoDelegate(base_model, data_acquisto_col_index))
                    elif field == 'inizio_prestito':
                        self.setItemDelegateForColumn(col, InizioPrestitoDelegate())
                    elif field == 'fine_prestito':
                        inizio_prestito_col_index = base_model.fields.index('inizio_prestito') #type: ignore
                        self.setItemDelegateForColumn(col, FinePrestitoDelegate(base_model, inizio_prestito_col_index))
    
    def currentChanged(self, current, previous):
        """Intercetta il cambio di selezione e lo comunica al modello"""
        super().currentChanged(current, previous)
        
        if current.isValid():
            model = self.model()
            
            # Supporto universale: gestisce sia il modello diretto che il ProxyModel di ricerca
            from PySide6.QtCore import QSortFilterProxyModel
            if isinstance(model, QSortFilterProxyModel):
                source_index = model.mapToSource(current)
                source_row = source_index.row()
                base_model = model.sourceModel()
            else:
                source_row = current.row()
                base_model = model
                
            # Comunica al modello quale riga evidenziare
            if hasattr(base_model, 'set_current_row'):
                base_model.set_current_row(source_row) #type: ignore

    def keyPressEvent(self, event):
        key = event.key()
        index = self.currentIndex()

        arrows = (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down
        )

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_enter(index)
            return

        if key in arrows:
            dx, dy = 0, 0
            if key == Qt.Key.Key_Left: dx = -1
            elif key == Qt.Key.Key_Right: dx = 1
            elif key == Qt.Key.Key_Up: dy = -1
            elif key == Qt.Key.Key_Down: dy = 1

            self._commit_and_move(index, dx, dy)
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse clicks on action buttons"""
        index = self.indexAt(event.pos())
        
        if index.isValid():
            model = self.model()
            base_model = self.get_base_model()
            
            # Last column handling
            if index.column() == model.columnCount() - 1:
                row = index.row()
                
                # Creation row: ➕ button
                if row == 0:
                    model.create_from_row() #type: ignore
                    return
                
                # Normal rows: 🗑️ or 🗑️✓❌ buttons
                if row > 0:
                    # Map to source row to check inside 'edited_cells' correctly
                    source_row = row
                    if isinstance(model, QSortFilterProxyModel):
                        source_row = model.mapToSource(model.index(row, 0)).row()

                    # Check if row has pending changes
                    has_edits = source_row in base_model.edited_cells and len(base_model.edited_cells[source_row]) > 0 #type: ignore
                    
                    if has_edits:
                        self._show_action_menu(event.pos(), row, model)
                        return
                    else:
                        model.soft_delete_row(row) #type: ignore
                        self.item_deleted.emit()
                        return
            
            # For other columns: open editor on single left-click if editable
            if event.button() == Qt.MouseButton.LeftButton:
                flags = self.model().flags(index)
                if flags & Qt.ItemFlag.ItemIsEditable:
                    self.setCurrentIndex(index)
                    self.edit(index)
                    return
        
        super().mousePressEvent(event)

    def _show_action_menu(self, pos, row, model):
        """Show menu to choose between confirm changes, cancel changes, or delete"""
        from PySide6.QtWidgets import QMenu
        
        menu = QMenu(self)
        confirm_action = menu.addAction("✓ Conferma modifiche riga")
        cancel_action = menu.addAction("❌ Cancella modifiche riga")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Elimina riga")
        
        global_pos = self.viewport().mapToGlobal(pos)
        action = menu.exec(global_pos)
        
        if action == confirm_action:
            try:
                model.commit_row_changes(row)
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Errore", f"Errore durante il salvataggio:\n{str(e)}")
                self.get_base_model().refresh() #type: ignore
        elif action == cancel_action:
            model.cancel_row_changes(row)
        elif action == delete_action:
            model.soft_delete_row(row)
            self.item_deleted.emit()

    def _handle_enter(self, index):
        if not index.isValid():
            return

        model = self.model()
        base_model = self.get_base_model()

        # Last column handling
        if index.column() == model.columnCount() - 1:
            row = index.row()
            
            if row == 0:
                model.create_from_row() #type: ignore
                return
            
            if row > 0:
                # Mappiamo l'indice del proxy su quello base per la verifica
                source_row = row
                if isinstance(model, QSortFilterProxyModel):
                    source_row = model.mapToSource(model.index(row, 0)).row()

                has_edits = source_row in base_model.edited_cells and len(base_model.edited_cells[source_row]) > 0 #type: ignore
                
                if has_edits:
                    rect = self.visualRect(index)
                    pos = rect.center()
                    self._show_action_menu(pos, row, model)
                else:
                    model.soft_delete_row(row) #type: ignore
                    self.item_deleted.emit()
                return

        # normal cell → commit + move right
        self._commit_and_move(index, dx=1, dy=0)

    def _commit_and_move(self, index, dx=0, dy=0):
        if not index.isValid():
            return

        model = self.model()
        row = index.row()
        col = index.column()

        new_row = row + dy
        new_col = col + dx

        if not (0 <= new_row < model.rowCount()):
            return
        if not (0 <= new_col < model.columnCount()):
            return

        next_index = model.index(new_row, new_col)
        
        if self.state() == QTableView.State.EditingState:
            QTimer.singleShot(0, lambda: self._move_to(next_index))
        else:
            self._move_to(next_index)

    def _move_to(self, index):
        self.setCurrentIndex(index)
        flags = self.model().flags(index)
        if flags & Qt.ItemFlag.ItemIsEditable:
            self.edit(index)