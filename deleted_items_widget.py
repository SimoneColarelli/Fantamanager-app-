from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QLabel
)
from PySide6.QtCore import Qt, Signal


class DeletedItemsWidget(QWidget):
    
    items_restored = Signal()  # Signal when items are restored
    
    def __init__(self, repository, fields, headers):
        super().__init__()
        self.repo = repository
        self.fields = fields
        self.headers = headers
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Elementi eliminati")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(title)
        
        # Buttons layout
        self.buttons_layout = QHBoxLayout()
        
        # Select All button (always visible)
        self.select_all_cb = QCheckBox("Seleziona tutto")
        self.select_all_cb.stateChanged.connect(self.select_deselect_all)
        self.buttons_layout.addWidget(self.select_all_cb)
        
        # Restore button (hidden when no selection)
        self.restore_btn = QPushButton("Ripristina selezionati")
        self.restore_btn.clicked.connect(self.restore_selected)
        self.restore_btn.hide()
        self.buttons_layout.addWidget(self.restore_btn)
        
        # Delete button (hidden when no selection)
        self.delete_btn = QPushButton("Elimina definitivamente")
        self.delete_btn.setStyleSheet("background-color: #dc3545; color: white;")
        self.delete_btn.clicked.connect(self.hard_delete_selected)
        self.delete_btn.hide()
        self.buttons_layout.addWidget(self.delete_btn)
        
        self.buttons_layout.addStretch()
        
        # Create container widget for buttons
        self.buttons_widget = QWidget()
        self.buttons_widget.setLayout(self.buttons_layout)
        layout.addWidget(self.buttons_widget)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.fields) + 1)  # +1 for checkbox
        self.table.setHorizontalHeaderLabels([""] + self.headers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        layout.addWidget(self.table)
        
        self.setLayout(layout)
        self.refresh()
    
    def refresh(self):
        deleted_items = self.repo.all_deleted()
        self.table.setRowCount(len(deleted_items))
        
        self.checkboxes = []
        
        for row, obj in enumerate(deleted_items):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.stateChanged.connect(self.update_buttons_visibility)
            self.checkboxes.append((checkbox, obj))
            self.table.setCellWidget(row, 0, checkbox)
            
            # Data fields
            for col, field in enumerate(self.fields):
                value = getattr(obj, field)
                item = QTableWidgetItem(str(value) if value else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col + 1, item)
        
        # Resize first column to fit checkbox
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
        self.update_buttons_visibility()
        self.select_all_cb.setChecked(False)
    
    def update_buttons_visibility(self):
        has_selection = any(cb.isChecked() for cb, _ in self.checkboxes)
        self.restore_btn.setVisible(has_selection)
        self.delete_btn.setVisible(has_selection)
    
    def get_selected_objects(self):
        return [obj for cb, obj in self.checkboxes if cb.isChecked()]
    
    def select_deselect_all(self):
        for cb, _ in self.checkboxes:
            if self.select_all_cb.isChecked():
                cb.setChecked(True)
            else:
                cb.setChecked(False)
    
    def restore_selected(self):
        selected = self.get_selected_objects()
        for obj in selected:
            self.repo.restore(obj)
        self.refresh()
        self.items_restored.emit()  # Emit signal to refresh main table
    
    def hard_delete_selected(self):
        selected = self.get_selected_objects()
        for obj in selected:
            self.repo.hard_delete(obj)
        self.refresh()