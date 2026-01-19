from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QFileDialog, QMessageBox,
    QTabWidget, QTableView
)
from PySide6.QtCore import Qt, QEvent
from database import SessionLocal
from excel_loader import load_excel
from updater import update_completo, update_solo_quotazioni
from backup import export_db, import_db
from models import Giocatore, Fantasquadra
from tables import EditableTableModel
from constants import (
    GIOCATORI_FIELDS, FANTASQUADRE_FIELDS,
    GIOCATORI_HEADERS, FANTASQUADRE_HEADERS
)
from undo import UndoManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fantacalcio Manager")
        self.resize(1200, 600)

        self.session = SessionLocal()
        self.undo = UndoManager(self.session)
        self.excel_data = None

        self.tabs = QTabWidget()
        self.tab_giocatori = QWidget()
        self.tab_fantasquadre = QWidget()

        self.tabs.addTab(self.tab_giocatori, "Giocatori")
        self.tabs.addTab(self.tab_fantasquadre, "Fantasquadre")

        self._init_giocatori_tab()
        self._init_fantasquadre_tab()

        self.btn_load_excel = QPushButton("📂 Carica Excel")
        self.btn_update_full = QPushButton("🔄 Update completo")
        self.btn_update_quotes = QPushButton("🔄 Update quotazioni")
        self.btn_undo = QPushButton("⏪ Undo")
        self.btn_export = QPushButton("💾 Export DB")
        self.btn_import = QPushButton("📥 Import DB")

        layout = QVBoxLayout()
        for b in (
            self.btn_load_excel,
            self.btn_update_full,
            self.btn_update_quotes,
            self.btn_undo,
            self.btn_export,
            self.btn_import,
        ):
            layout.addWidget(b)

        layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # SIGNALS
        self.btn_load_excel.clicked.connect(self.load_excel)
        self.btn_update_full.clicked.connect(self.run_update_full)
        self.btn_update_quotes.clicked.connect(self.run_update_quotes)
        self.btn_undo.clicked.connect(self.run_undo)
        self.btn_export.clicked.connect(self.export_db)
        self.btn_import.clicked.connect(self.import_db)

        self.refresh_tables()

    # ---------------- TABS ----------------

    def _init_giocatori_tab(self):
        layout = QVBoxLayout()
        self.giocatori_view = QTableView()
        self.giocatori_view.setMouseTracking(True)
        layout.addWidget(self.giocatori_view)
        self.tab_giocatori.setLayout(layout)

    def _init_fantasquadre_tab(self):
        layout = QVBoxLayout()
        self.fantasquadre_view = QTableView()
        self.fantasquadre_view.setMouseTracking(True)
        layout.addWidget(self.fantasquadre_view)
        self.tab_fantasquadre.setLayout(layout)

    # ---------------- TABLES ----------------

    def refresh_tables(self):
        self.g_model = EditableTableModel(
            self.session,
            Giocatore,
            GIOCATORI_FIELDS,
            GIOCATORI_HEADERS,
            self.undo
        )
        self.giocatori_view.setModel(self.g_model)

        self.f_model = EditableTableModel(
            self.session,
            Fantasquadra,
            FANTASQUADRE_FIELDS,
            FANTASQUADRE_HEADERS,
            self.undo
        )
        self.fantasquadre_view.setModel(self.f_model)

        # Install event filters on viewports
        self.giocatori_view.viewport().installEventFilter(self)
        self.fantasquadre_view.viewport().installEventFilter(self)

    # ---------------- EVENTS ----------------

    def eventFilter(self, source, event):
        # Process giocatori table events
        if source is self.giocatori_view.viewport():
            return self._handle_table_event(self.giocatori_view, self.g_model, event)
        
        # Process fantasquadre table events
        if source is self.fantasquadre_view.viewport():
            return self._handle_table_event(self.fantasquadre_view, self.f_model, event)
        
        return super().eventFilter(source, event)

    def _handle_table_event(self, view, model, event):
        etype = event.type()
        
        # Handle mouse move for hover effect
        if etype == QEvent.Type.MouseMove:
            index = view.indexAt(event.position().toPoint())
            model.set_hovered_row(index.row() if index.isValid() else None)
            return False
        
        # Handle mouse clicks
        if etype == QEvent.Type.MouseButtonPress:
            index = view.indexAt(event.position().toPoint())
            if (
                index.isValid()
                and index.column() == len(model.fields)  # Delete column
                and index.row() != 0  # Not the creation row
            ):
                if self._confirm_delete():
                    model.delete_row(index.row())
                return True
        
        return False

    def _confirm_delete(self):
        return (
            QMessageBox.question(
                self,
                "Conferma eliminazione",
                "Sei sicuro di voler eliminare questo record?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    # ---------------- ACTIONS ----------------

    def load_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica Excel", "", "Excel (*.xlsx)")
        if path:
            try:
                self.excel_data = load_excel(path)
                QMessageBox.information(self, "OK", "Excel caricato.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Errore caricamento Excel: {e}")

    def run_update_full(self):
        if not self.excel_data:
            QMessageBox.warning(self, "Errore", "Carica prima Excel.")
            return
        try:
            self.undo.snapshot()
            update_completo(self.session, self.excel_data)
            self.refresh_tables()
            QMessageBox.information(self, "OK", "Update completo completato.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore durante update: {e}")

    def run_update_quotes(self):
        if not self.excel_data:
            QMessageBox.warning(self, "Errore", "Carica prima Excel.")
            return
        try:
            self.undo.snapshot()
            update_solo_quotazioni(self.session, self.excel_data)
            self.refresh_tables()
            QMessageBox.information(self, "OK", "Update quotazioni completato.")
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore durante update: {e}")

    def run_undo(self):
        if self.undo.undo():
            self.refresh_tables()
            QMessageBox.information(self, "OK", "Undo completato.")
        else:
            QMessageBox.warning(self, "Errore", "Nessuno stato da ripristinare.")

    def export_db(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export DB", "backup.json", "JSON (*.json)")
        if path:
            try:
                export_db(self.session, path)
                QMessageBox.information(self, "OK", "Database esportato.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Errore durante export: {e}")

    def import_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import DB", "", "JSON (*.json)")
        if path:
            try:
                import_db(self.session, path)
                self.refresh_tables()
                QMessageBox.information(self, "OK", "Database importato.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Errore durante import: {e}")

    def closeEvent(self, event):
        self.session.close()
        event.accept()