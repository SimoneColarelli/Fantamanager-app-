from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QWidget, QLineEdit
from search_proxy_model import SearchProxyModel
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from database import SessionLocal, engine
from models import Giocatore, Fantasquadra
from repository import Repository
from editable_table_model import EditableTableModel
from constants import *
from editable_table_view import EditableTableView
from deleted_items_widget import DeletedItemsWidget
from table_with_edit_buttons import TableWithEditButtons
from data_manager import DataManagerUI


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
        self.g_model = EditableTableModel(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)

        # 1. Setup Proxy Model for Live Searching
        self.g_proxy_model = SearchProxyModel()
        self.g_proxy_model.setSourceModel(self.g_model)
        try:
            nome_idx = GIOCATORI_FIELDS.index("nome")
            self.g_proxy_model.set_filter_column(nome_idx)
        except ValueError:
            pass

        self.g_view = EditableTableView()
        # Set the Proxy Model on the view, NOT the g_model directly
        self.g_view.setModel(self.g_proxy_model)

        # Wrap view with edit buttons
        g_table_widget = TableWithEditButtons(self.g_view)

        # 2. Create the Search Bar UI
        self.g_search_bar = QLineEdit()
        self.g_search_bar.setPlaceholderText("🔍 Cerca giocatore per nome...")
        self.g_search_bar.setClearButtonEnabled(True)
        self.g_search_bar.setStyleSheet("padding: 5px; font-size: 14px; margin-bottom: 5px;")
        
        # Connect typing in the search bar to the filter text
        self.g_search_bar.textChanged.connect(self.g_proxy_model.set_search_text)

        # 3. Combine Search Bar and Table together in a layout
        g_main_widget = QWidget()
        g_main_layout = QVBoxLayout(g_main_widget)
        g_main_layout.setContentsMargins(0, 0, 0, 0)
        g_main_layout.addWidget(self.g_search_bar)
        g_main_layout.addWidget(g_table_widget)

        self.g_deleted_widget = DeletedItemsWidget(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)
        
        self.g_view.item_deleted.connect(self.g_deleted_widget.refresh)
        self.g_view.item_deleted.connect(self.g_model.refresh)
        self.g_deleted_widget.items_restored.connect(self.g_model.refresh)

        # Create splitter for main table and deleted items
        g_splitter = QSplitter(Qt.Orientation.Vertical)
        # Add our new combined widget (search bar + table) to the splitter
        g_splitter.addWidget(g_main_widget) 
        g_splitter.addWidget(self.g_deleted_widget)
        g_splitter.setStretchFactor(0, 3) 
        g_splitter.setStretchFactor(1, 1)

        # ========== FANTASQUADRE TAB ==========
        f_repo = Repository(session, Fantasquadra, FANTASQUADRE_FIELDS)
        self.f_model = EditableTableModel(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)

        self.f_view = EditableTableView()
        self.f_view.setModel(self.f_model)

        # Wrap view with edit buttons
        f_table_widget = TableWithEditButtons(self.f_view)

        self.f_deleted_widget = DeletedItemsWidget(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)
        
        # Connect delete signal to refresh deleted items
        self.f_view.item_deleted.connect(self.f_deleted_widget.refresh)
        self.f_view.item_deleted.connect(self.f_model.refresh)
        
        # Connect restore signal to refresh main table
        self.f_deleted_widget.items_restored.connect(self.f_model.refresh)

        # Create splitter for main table and deleted items
        f_splitter = QSplitter(Qt.Orientation.Vertical)
        f_splitter.addWidget(f_table_widget)
        f_splitter.addWidget(self.f_deleted_widget)
        f_splitter.setStretchFactor(0, 3)  # Main table gets more space
        f_splitter.setStretchFactor(1, 1)  # Deleted items gets less space

        # ========== ADD TABS ==========
        self.tabs.addTab(g_splitter, "Giocatori")
        self.tabs.addTab(f_splitter, "Fantasquadre")

        self.setCentralWidget(self.tabs)

        # Initialize data manager with global refresh callback
        self.data_manager_ui = DataManagerUI(self, refresh_callback=self.refresh_all_data)
        self.setup_import_export_menu()

    def refresh_all_data(self):
        """Refresh all tables and deleted items widgets"""
        # Refresh Giocatori
        self.g_model.refresh()
        self.g_deleted_widget.refresh()
        
        # Refresh Fantasquadre
        self.f_model.refresh()
        self.f_deleted_widget.refresh()

    def setup_import_export_menu(self):
        # Access the existing menu bar (assuming generated by UI file or standard QMainWindow)
        menubar = self.menuBar()

        # Create a new "Data" menu
        data_menu = menubar.addMenu("Data")

        export_menu = data_menu.addMenu("Export")

        # Export Actions
        export_all_action = QAction("Export All Data...", self)
        export_all_action.triggered.connect(self.data_manager_ui.export_all)
        export_menu.addAction(export_all_action)

        export_table_action = QAction("Export Single Table...", self)
        export_table_action.triggered.connect(self.data_manager_ui.export_single_table)
        export_menu.addAction(export_table_action)

        data_menu.addSeparator()

        import_menu = data_menu.addMenu("Import")

        # Import Actions
        import_all_action = QAction("Import All Data...", self)
        import_all_action.triggered.connect(self.data_manager_ui.import_all)
        import_menu.addAction(import_all_action)

        import_table_action = QAction("Import Single Table...", self)
        import_table_action.triggered.connect(self.data_manager_ui.import_single_table)
        import_menu.addAction(import_table_action)