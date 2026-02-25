import openpyxl
from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox, QFileDialog, QPushButton, QLabel, QMessageBox
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

        # === VARIABILE DI STATO DELLE QUOTAZIONI ===
        # Dizionario che avrà come chiave il Nome (4a colonna) e come valore la Quotazione (9a colonna)
        self.quotazioni_data = {} 
        
        # === BARRA GRAFICA QUOTAZIONI ===
        self.quotazioni_bar = QWidget()
        quotazioni_layout = QHBoxLayout(self.quotazioni_bar)
        quotazioni_layout.setContentsMargins(10, 5, 10, 5) # Piccoli margini
        
        # Bottone Upload
        self.btn_upload_quotazioni = QPushButton("📂 Carica file Quotazioni (.xlsx)")
        self.btn_upload_quotazioni.clicked.connect(self._upload_quotazioni)
        
        # Etichetta di Stato
        self.lbl_quotazioni_status = QLabel("Stato: 🔴 Non Caricate")
        self.lbl_quotazioni_status.setStyleSheet("color: red; font-weight: bold;")
        
        # Bottone Pulisci Dati
        self.btn_clear_quotazioni = QPushButton("🗑️ Svuota Quotazioni")
        self.btn_clear_quotazioni.clicked.connect(self._clear_quotazioni)
        self.btn_clear_quotazioni.setEnabled(False) # Disabilitato all'inizio
        
        # Aggiungo i widget al layout orizzontale
        quotazioni_layout.addWidget(self.btn_upload_quotazioni)
        quotazioni_layout.addWidget(self.lbl_quotazioni_status)
        quotazioni_layout.addStretch() # Spinge il bottone 'Svuota' verso destra
        quotazioni_layout.addWidget(self.btn_clear_quotazioni)

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
        g_main_layout.addWidget(self.quotazioni_bar)  # Aggiungi la barra delle quotazioni sopra
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
    def _upload_quotazioni(self):
        """Apre un file dialog, legge l'Excel e popola la variabile di stato"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "Seleziona file Quotazioni", 
            "", 
            "File Excel (*.xlsx)"
        )
        
        if not filepath:
            return # L'utente ha annullato
            
        try:
            # Apriamo il file Excel (usando data_only per leggere i valori, non le formule)
            workbook = openpyxl.load_workbook(filepath, data_only=True)
            
            # Prendiamo il foglio attivo (solitamente "Tutti")
            sheet = workbook.active
            
            self.quotazioni_data.clear()
            
            # Iteriamo le righe. sheet.iter_rows parte da 1. 
            # I dati reali partono solitamente dalla riga 3 (riga 1: titolo, riga 2: headers)
            for row in sheet.iter_rows(min_row=3, values_only=True): #type: ignore
                # Assicuriamoci che la riga abbia abbastanza colonne (almeno 9)
                if len(row) >= 9:
                    nome = row[3]  # 4a cella (indice 3): Nome
                    quotazione = row[8] # 9a cella (indice 8): Qt.A M
                    
                    if nome and isinstance(nome, str): # Controllo di sicurezza
                        # Salviamo nel dizionario
                        self.quotazioni_data[nome.strip()] = quotazione

            # Se abbiamo caricato dati con successo, aggiorniamo l'interfaccia
            print(self.quotazioni_data) # Debug: stampa le quotazioni caricate
            if self.quotazioni_data:
                conteggio = len(self.quotazioni_data)
                self.lbl_quotazioni_status.setText(f"Stato: 🟢 Caricate ({conteggio} giocatori)")
                self.lbl_quotazioni_status.setStyleSheet("color: green; font-weight: bold;")
                self.btn_clear_quotazioni.setEnabled(True)
                
                QMessageBox.information(self, "Successo", f"Dati caricati! Letti {conteggio} giocatori.")
            else:
                QMessageBox.warning(self, "Attenzione", "File elaborato, ma non è stato trovato alcun giocatore.")

        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile leggere il file:\n{str(e)}")

    def _clear_quotazioni(self):
        """Svuota la variabile di stato previa conferma e ripristina l'interfaccia"""
        
        # 1. Chiediamo conferma all'utente
        risposta = QMessageBox.question(
            self,
            "Conferma Svuotamento",
            "Sei sicuro di voler svuotare le quotazioni attualmente in memoria?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Tasto predefinito di sicurezza
        )
        
        # 2. Se l'utente clicca su "Yes", procediamo con la pulizia
        if risposta == QMessageBox.StandardButton.Yes:
            self.quotazioni_data.clear()
            
            self.lbl_quotazioni_status.setText("Stato: 🔴 Non Caricate")
            self.lbl_quotazioni_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_clear_quotazioni.setEnabled(False)
            
            QMessageBox.information(self, "Dati Cancellati", "Le quotazioni sono state rimosse correttamente.")