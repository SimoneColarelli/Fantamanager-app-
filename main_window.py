from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter
from PySide6.QtCore import Qt
from database import SessionLocal, engine
from models import Giocatore, Fantasquadra
from repository import Repository
from editable_table_model import EditableTableModel
from constants import *
from editable_table_view import EditableTableView
from deleted_items_widget import DeletedItemsWidget
from table_with_edit_buttons import TableWithEditButtons


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

        # Wrap view with edit buttons
        g_table_widget = TableWithEditButtons(g_view)

        g_deleted_widget = DeletedItemsWidget(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)
        
        # Connect delete signal to refresh deleted items
        g_view.item_deleted.connect(g_deleted_widget.refresh)
        g_view.item_deleted.connect(g_model.refresh)
        
        # Connect restore signal to refresh main table
        g_deleted_widget.items_restored.connect(g_model.refresh)

        # Create splitter for main table and deleted items
        g_splitter = QSplitter(Qt.Orientation.Vertical)
        g_splitter.addWidget(g_table_widget)
        g_splitter.addWidget(g_deleted_widget)
        g_splitter.setStretchFactor(0, 3)  # Main table gets more space
        g_splitter.setStretchFactor(1, 1)  # Deleted items gets less space

        # ========== FANTASQUADRE TAB ==========
        f_repo = Repository(session, Fantasquadra, FANTASQUADRE_FIELDS)
        f_model = EditableTableModel(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)

        f_view = EditableTableView()
        f_view.setModel(f_model)

        # Wrap view with edit buttons
        f_table_widget = TableWithEditButtons(f_view)

        f_deleted_widget = DeletedItemsWidget(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)
        
        # Connect delete signal to refresh deleted items
        f_view.item_deleted.connect(f_deleted_widget.refresh)
        f_view.item_deleted.connect(f_model.refresh)
        
        # Connect restore signal to refresh main table
        f_deleted_widget.items_restored.connect(f_model.refresh)

        # Create splitter for main table and deleted items
        f_splitter = QSplitter(Qt.Orientation.Vertical)
        f_splitter.addWidget(f_table_widget)
        f_splitter.addWidget(f_deleted_widget)
        f_splitter.setStretchFactor(0, 3)  # Main table gets more space
        f_splitter.setStretchFactor(1, 1)  # Deleted items gets less space

        # ========== ADD TABS ==========
        self.tabs.addTab(g_splitter, "Giocatori")
        self.tabs.addTab(f_splitter, "Fantasquadre")

        self.setCentralWidget(self.tabs)