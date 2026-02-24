from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox
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
            squadra_idx = GIOCATORI_FIELDS.index("squadra")
            self.g_proxy_model.set_filter_columns(nome_idx, squadra_idx)
        except ValueError:
            pass

        self.g_view = EditableTableView()
        self.g_view.setModel(self.g_proxy_model)
        
        # ABILITA L'ORDINAMENTO SULLE COLONNE!
        self.g_view.setSortingEnabled(True)

        # Wrap view with edit buttons
        g_table_widget = TableWithEditButtons(self.g_view)

        # 2. Create the Search Bar UI
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.g_search_bar = QLineEdit()
        self.g_search_bar.setPlaceholderText("🔍 Cerca giocatore per nome...")
        self.g_search_bar.setClearButtonEnabled(True)
        self.g_search_bar.setStyleSheet("padding: 5px; font-size: 14px;")
        
        self.g_squadra_combo = QComboBox()
        # Applichiamo uno stile specifico per forzare uno sfondo non trasparente
        self.g_squadra_combo.setStyleSheet("""
            QComboBox {
                padding: 5px; 
                font-size: 14px;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QComboBox QAbstractItemView {
                background-color: white;
                border: 1px solid #ccc;
                selection-background-color: #e0e0e0;
                color: black;
            }
        """)
        self.update_squadra_combo()  # Popola la combo box
        
        filter_layout.addWidget(self.g_search_bar)
        filter_layout.addWidget(self.g_squadra_combo)
        
        # Connect signals
        self.g_search_bar.textChanged.connect(self.g_proxy_model.set_search_text)
        self.g_squadra_combo.currentTextChanged.connect(self.g_proxy_model.set_squadra_filter)

        # 3. Combine Search Bar and Table together in a layout
        g_main_widget = QWidget()
        g_main_layout = QVBoxLayout(g_main_widget)
        g_main_layout.setContentsMargins(0, 0, 0, 0)
        g_main_layout.addLayout(filter_layout)
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
            
            # Refresh Squadra filter combo
            self.update_squadra_combo()

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

    def update_squadra_combo(self):
            """Popola o aggiorna il menu a tendina delle squadre"""
            session = SessionLocal()
            # Ottieni tutte le fantasquadre attive
            squadre = session.query(Fantasquadra.nome).filter_by(deleted=False).all()
            session.close()
            
            current_text = self.g_squadra_combo.currentText()
            
            self.g_squadra_combo.blockSignals(True)
            self.g_squadra_combo.clear()
            self.g_squadra_combo.addItem("Tutte le squadre")
            for sq in squadre:
                self.g_squadra_combo.addItem(sq[0])
                
            # Ripristina la selezione precedente se ancora esistente
            idx = self.g_squadra_combo.findText(current_text)
            if idx >= 0:
                self.g_squadra_combo.setCurrentIndex(idx)
            else:
                self.g_squadra_combo.setCurrentIndex(0)
                
            self.g_squadra_combo.blockSignals(False)

    def mousePressEvent(self, event):
        """Deselect the active table when the user clicks outside of it."""
        super().mousePressEvent(event)

        # Determine which view is currently active (based on selected tab)
        current_tab = self.tabs.currentIndex()
        active_view = self.g_view if current_tab == 0 else self.f_view

        # Map the click position to the viewport of the active table
        pos_in_viewport = active_view.viewport().mapFromGlobal(event.globalPosition().toPoint())
        clicked_on_table = active_view.viewport().rect().contains(pos_in_viewport)

        if not clicked_on_table:
            active_view.deselect()