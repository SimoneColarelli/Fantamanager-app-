from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import Signal
from editable_table_model import EditableTableModel
from editable_table_view import EditableTableView
from typing import cast


class TableWithEditButtons(QWidget):
    """Widget that combines a table view with edit confirmation buttons"""
    
    def __init__(self, view: EditableTableView):
        super().__init__()
        self.view = view
        self.setup_ui()
        
        # Connect model signal
        model = cast(EditableTableModel, self.view.model())
        if model:
            model.has_pending_changes.connect(self.update_buttons_visibility)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Buttons layout (top right)
        buttons_layout = QHBoxLayout()
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
        
        self.setLayout(layout)
    
    def update_buttons_visibility(self, has_changes):
        self.confirm_btn.setVisible(has_changes)
        self.cancel_btn.setVisible(has_changes)
    
    def confirm_changes(self):
        model = cast(EditableTableModel, self.view.model())
        if model:
            model.commit_all_changes()
    
    def cancel_changes(self):
        model = cast(EditableTableModel, self.view.model())
        if model:
            model.cancel_all_changes()