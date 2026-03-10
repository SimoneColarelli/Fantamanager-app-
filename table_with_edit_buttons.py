from typing import cast
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal, Qt, QTimer, QSortFilterProxyModel
from PySide6.QtGui import QIcon
from editable_table_model import EditableTableModel
from editable_table_view import EditableTableView


class TableWithEditButtons(QWidget):
    """Widget that combines a table view with edit confirmation buttons and a floating refresh button"""
    
    def __init__(self, view: EditableTableView):
        super().__init__()
        self.view = view
        self.setup_ui()
        
        # Connect model signals
        model = self.get_source_model()
        if model:
            model.has_pending_changes.connect(self.update_buttons_visibility)
            model.editing_locked_changed.connect(self._on_lock_changed)

    def get_source_model(self) -> EditableTableModel:
        """Helper to extract the base model safely even if wrapped in a ProxyModel"""
        model = self.view.model()
        if isinstance(model, QSortFilterProxyModel):
            return cast(EditableTableModel, model.sourceModel())
        return cast(EditableTableModel, model)  
      
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Top bar: lock toggle on the left, save/cancel on the right
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        # ── Lock / Unlock button ──────────────────────────────────────────
        self.lock_btn = QPushButton("🔒 Sblocca modifiche")
        self.lock_btn.setCheckable(True)
        self.lock_btn.setChecked(True)  # Default to locked
        self.lock_btn.setStyleSheet(self._lock_btn_style(locked=True))
        self.lock_btn.setToolTip("Sblocca / blocca la modifica delle righe esistenti")
        self.lock_btn.clicked.connect(self._toggle_lock)
        buttons_layout.addWidget(self.lock_btn)
        # ─────────────────────────────────────────────────────────────────

        buttons_layout.addStretch()
        
        self.confirm_btn = QPushButton("Conferma modifiche")
        self.confirm_btn.setStyleSheet("background-color: #28a745; color: white; padding: 5px 15px;")
        self.confirm_btn.clicked.connect(self.confirm_changes)
        self.confirm_btn.hide()
        buttons_layout.addWidget(self.confirm_btn)
        
        self.cancel_btn = QPushButton("Cancella modifiche")
        self.cancel_btn.setStyleSheet("background-color: #ffc107; color: black; padding: 5px 15px;")
        self.cancel_btn.clicked.connect(self.cancel_changes)
        self.cancel_btn.hide()
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # Table
        layout.addWidget(self.view)
        
        # Floating refresh button (bottom right)
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(50, 50)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        self.refresh_btn.setToolTip("Aggiorna tabella")
        self.refresh_btn.clicked.connect(self.refresh_table)
        self.refresh_btn.setParent(self.view)
        
        # Position the refresh button
        QTimer.singleShot(0, self.position_refresh_button)
        
        self.setLayout(layout)

    # ── Lock helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _lock_btn_style(locked: bool) -> str:
        if not locked:
            return (
                "QPushButton {"
                "  background-color: #dc3545;"
                "  color: white;"
                "  padding: 5px 15px;"
                "  border-radius: 3px;"
                "}"
                "QPushButton:hover { background-color: #c82333; }"
            )
        else:
            return (
                "QPushButton {"
                "  background-color: #6c757d;"
                "  color: white;"
                "  padding: 5px 15px;"
                "  border-radius: 3px;"
                "}"
                "QPushButton:hover { background-color: #5a6268; }"
            )

    def _toggle_lock(self):
        model = self.get_source_model()
        if not model:
            return
        new_locked = self.lock_btn.isChecked()
        model.set_editing_locked(new_locked)

    def _on_lock_changed(self, locked: bool):
        """Update button appearance to reflect the current lock state."""
        self.lock_btn.setChecked(locked)
        if locked:
            self.lock_btn.setText("🔓 Sblocca modifiche")
        else:
            self.lock_btn.setText("🔒 Blocca modifiche")
        self.lock_btn.setStyleSheet(self._lock_btn_style(locked))

    # ── Resize / positioning ──────────────────────────────────────────────

    def resizeEvent(self, event):
        """Reposition refresh button when widget is resized"""
        super().resizeEvent(event)
        self.position_refresh_button()
    
    def position_refresh_button(self):
        """Position the refresh button at bottom right corner of the table"""
        if self.view and self.refresh_btn:
            x = self.view.width() - self.refresh_btn.width() - 10
            y = self.view.height() - self.refresh_btn.height() - 40
            self.refresh_btn.move(x, y)
            self.refresh_btn.raise_()

    # ── Visibility / save / cancel ────────────────────────────────────────

    def update_buttons_visibility(self, has_changes):
        self.confirm_btn.setVisible(has_changes)
        self.cancel_btn.setVisible(has_changes)
    
    def confirm_changes(self):
        model = self.get_source_model()
        if model:
            try:
                model.commit_all_changes()
            except Exception as e:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(
                    self, 
                    "Errore", 
                    f"Errore durante il salvataggio delle modifiche:\n{str(e)}"
                )
                model.refresh()
        
    def cancel_changes(self):
        model = self.get_source_model()
        if model:
            model.cancel_all_changes()
    
    def refresh_table(self):
        model = self.get_source_model()
        if model:
            if model.has_changes():
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self,
                    "Modifiche non salvate",
                    "Ci sono modifiche non salvate. L'aggiornamento le cancellerà. Continuare?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No:
                    return
            
            model.refresh()

            # Invalidate proxy so it re-filters and re-sorts with fresh data
            proxy = self.view.model()
            if isinstance(proxy, QSortFilterProxyModel):
                proxy.invalidate()
            
            # Visual feedback: briefly change button colour
            original_style = self.refresh_btn.styleSheet()
            self.refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #28a745;
                    color: white;
                    border-radius: 25px;
                    font-size: 20px;
                    font-weight: bold;
                }
            """)
            QTimer.singleShot(200, lambda: self.refresh_btn.setStyleSheet(original_style))