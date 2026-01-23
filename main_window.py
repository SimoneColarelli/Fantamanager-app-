from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt
from database import SessionLocal, engine
from models import Giocatore, Fantasquadra
from repository import Repository
from editable_table_model import EditableTableModel
from constants import *
from editable_table_view import EditableTableView
from deleted_items_widget import DeletedItemsWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fantamanager – Phase 3")
        self.resize(1000, 600)

        Giocatore.metadata.create_all(engine)
        Fantasquadra.metadata.create_all(engine)

        session = SessionLocal()

        self.tabs = QTabWidget()

        # ========== GIOCATORI TAB ==========
        g_repo = Repository(session, Giocatore, GIOCATORI_FIELDS)
        g_model = EditableTableModel(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)

        g_view = EditableTableView()
        g_view.setModel(g_model)
        g_view.clicked.connect(self._handle_click)

        g_deleted_widget = DeletedItemsWidget(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)
        
        # Connect delete signal to refresh deleted items
        g_view.item_deleted.connect(g_deleted_widget.refresh)
        g_view.item_deleted.connect(g_model.refresh)
        
        # Connect restore signal to refresh main table
        g_deleted_widget.items_restored.connect(g_model.refresh)

        # Create splitter for main table and deleted items
        g_splitter = QSplitter(Qt.Orientation.Vertical)
        g_splitter.addWidget(g_view)
        g_splitter.addWidget(g_deleted_widget)
        g_splitter.setStretchFactor(0, 3)  # Main table gets more space
        g_splitter.setStretchFactor(1, 1)  # Deleted items gets less space

        # ========== FANTASQUADRE TAB ==========
        f_repo = Repository(session, Fantasquadra, FANTASQUADRE_FIELDS)
        f_model = EditableTableModel(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)

        f_view = EditableTableView()
        f_view.setModel(f_model)
        f_view.clicked.connect(self._handle_click)

        f_deleted_widget = DeletedItemsWidget(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)
        
        # Connect delete signal to refresh deleted items
        f_view.item_deleted.connect(f_deleted_widget.refresh)
        f_view.item_deleted.connect(f_model.refresh)
        
        # Connect restore signal to refresh main table
        f_deleted_widget.items_restored.connect(f_model.refresh)

        # Create splitter for main table and deleted items
        f_splitter = QSplitter(Qt.Orientation.Vertical)
        f_splitter.addWidget(f_view)
        f_splitter.addWidget(f_deleted_widget)
        f_splitter.setStretchFactor(0, 3)  # Main table gets more space
        f_splitter.setStretchFactor(1, 1)  # Deleted items gets less space

        # ========== ADD TABS ==========
        self.tabs.addTab(g_splitter, "Giocatori")
        self.tabs.addTab(f_splitter, "Fantasquadre")

        self.setCentralWidget(self.tabs)

    def _handle_click(self, index):
        model = index.model()
        
        # Last column handling
        if index.column() == model.columnCount() - 1:
            # ➕ button click (row 0)
            if index.row() == 0:
                model.create_from_row()
            
            # 🗑️ button click (other rows)
            elif index.row() > 0:
                model.soft_delete_row(index.row())
                # Get the view and emit the signal
                sender = self.sender()
                if isinstance(sender, EditableTableView):
                    sender.item_deleted.emit()