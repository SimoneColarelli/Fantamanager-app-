from typing import cast

import openpyxl
from sqlalchemy import func
from PySide6.QtWidgets import QMainWindow, QTabWidget, QSplitter, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QComboBox, QFileDialog, QPushButton, QLabel, QMessageBox, QInputDialog
from search_proxy_model import SearchProxyModel
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from database import SessionLocal, engine, Base
from models import Giocatore, Fantasquadra, Operazione
from repository import Repository
from editable_table_model import EditableTableModel
from constants import *
from editable_table_view import EditableTableView
from deleted_items_widget import DeletedItemsWidget
from table_with_edit_buttons import TableWithEditButtons
from data_manager import DataManagerUI
from operazione_repository import OperazioneRepository
from mercato_widget import MercatoWidget
from undo_manager import UndoManager
from migration_runner import run_migrations
from persistence import (
    SemanticUndoConflict,
    create_hybrid_persistence_from_env,
    list_undoable_transactions,
    undo_transaction,
)


def _resolve_nome(fantasquadra) -> str:
    """
    Safely read fantasquadra.nome without touching a potentially broken session.
    Uses SQLAlchemy's instance state to read the value from the identity map
    (already loaded dict) before falling back to a fresh DB query by PK.
    """
    from sqlalchemy import inspect as sa_inspect
    try:
        state = sa_inspect(fantasquadra)
        # If 'nome' is already in the loaded dict, return it directly
        if 'nome' in state.dict:
            return state.dict['nome']
        # Otherwise query fresh by primary key
        fq_id = state.identity[0] if state.identity else None
        if fq_id is not None:
            session = SessionLocal()
            try:
                fq = session.query(Fantasquadra).filter_by(id=fq_id).one_or_none()
                return cast(str, fq.nome) if fq else ""
            finally:
                session.close()
    except Exception:
        pass
    return ""


def _count_in_rosa(fantasquadra):
    """Count players effectively in this team's rosa:
      - registered to this team AND not on loan elsewhere
      - OR on loan TO this team from another team
    """
    from sqlalchemy import or_
    nome = _resolve_nome(fantasquadra)
    if not nome:
        return 0
    session = SessionLocal()
    try:
        return session.query(func.count(Giocatore.id)).filter(
            Giocatore.in_serie_a == True,
            Giocatore.deleted == False,
            or_(
                (Giocatore.squadra == nome) & (
                    (Giocatore.in_prestito_a == None) |
                    (Giocatore.in_prestito_a == "")
                ),
                Giocatore.in_prestito_a == nome,
            )
        ).scalar() or 0
    finally:
        session.close()


def _count_convocati(fantasquadra):
    """Count convocated players effectively in this team's rosa (same logic as in_rosa)."""
    from sqlalchemy import or_
    nome = _resolve_nome(fantasquadra)
    if not nome:
        return 0
    session = SessionLocal()
    try:
        return session.query(func.count(Giocatore.id)).filter(
            Giocatore.deleted == False,
            Giocatore.convocato == True,
            Giocatore.in_serie_a == True,
            or_(
                (Giocatore.squadra == nome) & (
                    (Giocatore.in_prestito_a == None) |
                    (Giocatore.in_prestito_a == "")
                ),
                Giocatore.in_prestito_a == nome,
            )
        ).scalar() or 0
    finally:
        session.close()



def _valore_rosa(fantasquadra):
    """Sum of valore_svincolo of all players registered to this team (squadra == nome),
    regardless of loan status."""
    nome = _resolve_nome(fantasquadra)
    if not nome:
        return 0
    session = SessionLocal()
    try:
        result = session.query(func.sum(Giocatore.valore_svincolo)).filter(
            Giocatore.squadra == nome,
            Giocatore.deleted == False,
        ).scalar()
        return int(result or 0)
    finally:
        session.close()


def _patrimonio(fantasquadra):
    """fm balance + valore_rosa."""
    nome = _resolve_nome(fantasquadra)
    if not nome:
        return 0
    session = SessionLocal()
    try:
        fq = session.query(Fantasquadra).filter_by(nome=nome, deleted=False).one_or_none()
        fm = cast(int, fq.fm if fq else 0)
        valore = session.query(func.sum(Giocatore.valore_svincolo)).filter(
            Giocatore.squadra == nome,
            Giocatore.deleted == False,
        ).scalar()
        return int(fm + (valore or 0))
    finally:
        session.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fantamanager – Phase 3")
        self.resize(1200, 700)

        # Create all tables (including the new ones for Operazione)
        Base.metadata.create_all(engine)
        run_migrations(engine)
        self.hybrid_persistence = create_hybrid_persistence_from_env(SessionLocal, engine)
        self.hybrid_persistence.start()

        # === VARIABILE DI STATO DELLE QUOTAZIONI ===
        self.quotazioni_data = {}
        
        # === BARRA GRAFICA QUOTAZIONI ===
        self.quotazioni_bar = QWidget()
        quotazioni_layout = QHBoxLayout(self.quotazioni_bar)
        quotazioni_layout.setContentsMargins(10, 5, 10, 5)
        
        self.btn_upload_quotazioni = QPushButton("📂 Carica file Quotazioni (.xlsx)")
        self.btn_upload_quotazioni.clicked.connect(self._upload_quotazioni)
        
        self.lbl_quotazioni_status = QLabel("Stato: 🔴 Non Caricate")
        self.lbl_quotazioni_status.setStyleSheet("color: red; font-weight: bold;")
        
        self.btn_clear_quotazioni = QPushButton("🗑️ Svuota Quotazioni")
        self.btn_clear_quotazioni.clicked.connect(self._clear_quotazioni)
        self.btn_clear_quotazioni.setEnabled(False)
        
        quotazioni_layout.addWidget(self.btn_upload_quotazioni)
        quotazioni_layout.addWidget(self.lbl_quotazioni_status)
        quotazioni_layout.addStretch()
        quotazioni_layout.addWidget(self.btn_clear_quotazioni)

        self.tabs = QTabWidget()

        # ========== GIOCATORI TAB ==========
        g_repo = Repository(SessionLocal, Giocatore, GIOCATORI_FIELDS)
        self.g_model = EditableTableModel(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)

        self.g_proxy_model = SearchProxyModel()
        self.g_proxy_model.setSourceModel(self.g_model)
        try:
            nome_idx         = GIOCATORI_FIELDS.index("nome")
            squadra_idx      = GIOCATORI_FIELDS.index("squadra")
            in_prestito_idx  = GIOCATORI_FIELDS.index("in_prestito_a")
            self.g_proxy_model.set_filter_columns(nome_idx, squadra_idx, in_prestito_idx)
        except ValueError:
            pass

        self.g_view = EditableTableView()
        self.g_view.setModel(self.g_proxy_model)
        self.g_view.setSortingEnabled(True)

        g_table_widget = TableWithEditButtons(self.g_view)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        
        self.g_search_bar = QLineEdit()
        self.g_search_bar.setPlaceholderText("🔍 Cerca giocatore per nome...")
        self.g_search_bar.setClearButtonEnabled(True)
        self.g_search_bar.setStyleSheet("padding: 5px; font-size: 14px;")
        
        self.g_squadra_combo = QComboBox()
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
        self.update_squadra_combo()
        
        filter_layout.addWidget(self.g_search_bar)
        filter_layout.addWidget(self.g_squadra_combo)
        
        self.g_search_bar.textChanged.connect(self.g_proxy_model.set_search_text)
        self.g_squadra_combo.currentTextChanged.connect(self.g_proxy_model.set_squadra_filter)

        # ── Bulk convocato bar ──────────────────────────────────────────────
        self.convocato_bar = QWidget()
        convocato_layout = QHBoxLayout(self.convocato_bar)
        convocato_layout.setContentsMargins(10, 4, 10, 4)
        convocato_layout.setSpacing(8)

        from PySide6.QtWidgets import QLabel as _QL
        convocato_layout.addWidget(_QL("Imposta convocato per tutti i giocatori visualizzati:"))

        self.btn_convocato_si = QPushButton("✅  Tutti Convocati")
        self.btn_convocato_si.setStyleSheet(
            "QPushButton { background-color: #28a745; color: white; padding: 4px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #218838; }"
        )
        self.btn_convocato_si.clicked.connect(lambda: self._set_convocato_bulk(True))
        convocato_layout.addWidget(self.btn_convocato_si)

        self.btn_convocato_no = QPushButton("❌  Tutti Non Convocati")
        self.btn_convocato_no.setStyleSheet(
            "QPushButton { background-color: #dc3545; color: white; padding: 4px 12px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #c82333; }"
        )
        self.btn_convocato_no.clicked.connect(lambda: self._set_convocato_bulk(False))
        convocato_layout.addWidget(self.btn_convocato_no)

        convocato_layout.addStretch()
        # ────────────────────────────────────────────────────────────────────

        g_main_widget = QWidget()
        g_main_layout = QVBoxLayout(g_main_widget)
        g_main_layout.setContentsMargins(0, 0, 0, 0)
        g_main_layout.addWidget(self.quotazioni_bar)
        g_main_layout.addLayout(filter_layout)
        g_main_layout.addWidget(self.convocato_bar)
        g_main_layout.addWidget(g_table_widget)

        self.g_deleted_widget = DeletedItemsWidget(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)
        
        self.g_view.item_deleted.connect(self.g_deleted_widget.refresh)
        self.g_view.item_deleted.connect(self.g_model.refresh)
        self.g_deleted_widget.items_restored.connect(self.g_model.refresh)

        g_splitter = QSplitter(Qt.Orientation.Vertical)
        g_splitter.addWidget(g_main_widget)
        g_splitter.addWidget(self.g_deleted_widget)
        g_splitter.setStretchFactor(0, 3)
        g_splitter.setStretchFactor(1, 1)

        # ========== FANTASQUADRE TAB ==========
        f_repo = Repository(SessionLocal, Fantasquadra, FANTASQUADRE_FIELDS)
        self.f_model = EditableTableModel(
            f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS,
            computed_fields={
            "in_rosa":     _count_in_rosa,
            "convocati":   _count_convocati,
            "valore_rosa": _valore_rosa,
            "patrimonio":  _patrimonio,
        }
        )

        self.f_view = EditableTableView()
        self.f_view.setModel(self.f_model)

        f_table_widget = TableWithEditButtons(self.f_view)

        f_computed = {"in_rosa", "convocati", "valore_rosa", "patrimonio"}
        f_real_fields = [f for f in FANTASQUADRE_FIELDS if f not in f_computed]
        f_real_headers = [h for f, h in zip(FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS) if f not in f_computed]
        self.f_deleted_widget = DeletedItemsWidget(f_repo, f_real_fields, f_real_headers)
        
        self.f_view.item_deleted.connect(self.f_deleted_widget.refresh)
        self.f_view.item_deleted.connect(self.f_model.refresh)
        self.f_deleted_widget.items_restored.connect(self.f_model.refresh)
        self.g_model.rows_committed.connect(self.f_model.refresh)

        f_splitter = QSplitter(Qt.Orientation.Vertical)
        f_splitter.addWidget(f_table_widget)
        f_splitter.addWidget(self.f_deleted_widget)
        f_splitter.setStretchFactor(0, 3)
        f_splitter.setStretchFactor(1, 1)

        # ========== MERCATO TAB ==========
        self.op_repo = OperazioneRepository(SessionLocal)
        self.mercato_widget = MercatoWidget(self.op_repo)

        # When giocatori or fantasquadre change, keep mercato combos in sync
        self.g_model.rows_committed.connect(self.mercato_widget.refresh_combos)
        self.f_model.rows_committed.connect(self.mercato_widget.refresh_combos)
        self.g_deleted_widget.items_restored.connect(self.mercato_widget.refresh_combos)
        self.f_deleted_widget.items_restored.connect(self.mercato_widget.refresh_combos)

        # When a cessione is committed, refresh giocatori + fantasquadre tables
        self.mercato_widget.operazione_committed.connect(self.g_model.refresh)
        self.mercato_widget.operazione_committed.connect(self.f_model.refresh)
        self.mercato_widget.operazione_committed.connect(self.update_squadra_combo)
        self.mercato_widget.operazione_committed.connect(self.mercato_widget.refresh_combos)

        # Give mercato_widget access to the persistent repo sessions so it can
        # expire them (release SQLite read locks) before each write operation.
        self.mercato_widget.sibling_repos = [g_repo, f_repo]

        # ========== ADD TABS ==========
        self.tabs.addTab(g_splitter, "Giocatori")
        self.tabs.addTab(f_splitter, "Fantasquadre")
        self.tabs.addTab(self.mercato_widget, "⚽ Mercato")

        self.setCentralWidget(self.tabs)

        self._repos = [g_repo, f_repo, self.op_repo]

        self.data_manager_ui = DataManagerUI(
            self,
            refresh_callback=self.refresh_all_data,
            repos=self._repos,
        )

        # ── Undo manager ─────────────────────────────────────────────────────
        self._undo_mgr = UndoManager(
            db_path="fantamanager.db",
            engine=engine,
            max_snapshots=5,
        )
        # Register every repository so their sessions are closed and
        # replaced with fresh ones after each undo restore
        self._undo_mgr._repos = self._repos
        self._undo_mgr.register_refresh_callback(self.refresh_all_data)
        self._undo_mgr.register_refresh_callback(self._sync_supabase_after_undo)
        # Dedicated callback: enable the undo action after every commit
        self._undo_mgr.register_snapshot_callback(self._update_undo_action)
        self._undo_mgr.start()
        # ─────────────────────────────────────────────────────────────────────

        self.setup_menu()

    def refresh_all_data(self):
        self.g_model.refresh()
        self.g_deleted_widget.refresh()
        self.f_model.refresh()
        self.f_deleted_widget.refresh()
        self.update_squadra_combo()
        self.mercato_widget.refresh_combos()
        self.mercato_widget._refresh_history()
        # Keep undo action in sync
        if hasattr(self, "_undo_mgr"):
            self._update_undo_action()

    def setup_menu(self):
        menubar = self.menuBar()

        data_menu = menubar.addMenu("Data")
        update_menu = menubar.addMenu("Updates")

        # ── Undo menu ────────────────────────────────────────────────────────
        undo_menu = menubar.addMenu("Modifica")
        self._undo_action = QAction("↩  Annulla ultima operazione", self)
        self._undo_action.setShortcut("Ctrl+Z")
        from PySide6.QtGui import QKeySequence
        from PySide6.QtCore import Qt as _Qt
        self._undo_action.setShortcutContext(_Qt.ShortcutContext.ApplicationShortcut)
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._perform_undo)
        undo_menu.addAction(self._undo_action)

        semantic_undo_action = QAction("Annulla operazione auditata...", self)
        semantic_undo_action.triggered.connect(self._perform_semantic_undo)
        undo_menu.addAction(semantic_undo_action)
        # ─────────────────────────────────────────────────────────────────────

        backup_menu = data_menu.addMenu("Backup")

        export_all_action = QAction("Backup completo...", self)
        export_all_action.triggered.connect(self.data_manager_ui.export_all)
        backup_menu.addAction(export_all_action)

        export_table_action = QAction("Backup singola tabella...", self)
        export_table_action.triggered.connect(self.data_manager_ui.export_single_table)
        backup_menu.addAction(export_table_action)

        data_menu.addSeparator()

        import_menu = data_menu.addMenu("Import")

        import_all_action = QAction("Import All Data...", self)
        import_all_action.triggered.connect(self.data_manager_ui.import_all)
        import_menu.addAction(import_all_action)

        import_table_action = QAction("Import Single Table...", self)
        import_table_action.triggered.connect(self.data_manager_ui.import_single_table)
        import_menu.addAction(import_table_action)

        data_menu.addSeparator()

        supabase_menu = data_menu.addMenu("Supabase")

        push_supabase_action = QAction("Sync locale -> Supabase", self)
        push_supabase_action.setEnabled(self.hybrid_persistence.is_configured)
        push_supabase_action.triggered.connect(self._sync_supabase_push_now)
        supabase_menu.addAction(push_supabase_action)

        pull_supabase_action = QAction("Sync Supabase -> locale", self)
        pull_supabase_action.setEnabled(self.hybrid_persistence.is_configured)
        pull_supabase_action.triggered.connect(self._sync_supabase_pull_now)
        supabase_menu.addAction(pull_supabase_action)

        complete_update_action = QAction("Complete Update", self)
        complete_update_action.triggered.connect(self._complete_update)
        update_menu.addAction(complete_update_action)

        quotazioni_update_action = QAction("Quotazioni Update", self)
        quotazioni_update_action.triggered.connect(self._quotazioni_update)
        update_menu.addAction(quotazioni_update_action)

        serie_a_update_action = QAction("Serie A Update", self)
        serie_a_update_action.triggered.connect(self._serie_a_update)
        update_menu.addAction(serie_a_update_action)

    def _sync_supabase_push_now(self):
        result = self.hybrid_persistence.push_local_to_remote(
            reason="manual_menu",
            raise_on_error=False,
        )
        self._show_sync_result(result)

    def _sync_supabase_pull_now(self):
        reply = QMessageBox.question(
            self,
            "Conferma sync",
            "Sostituire il database SQLite locale con lo snapshot Supabase?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._close_registered_repos()
            result = self.hybrid_persistence.pull_remote_to_local(
                reason="manual_menu",
                raise_on_error=False,
            )
        finally:
            self._reopen_registered_repos()

        self.refresh_all_data()
        self._show_sync_result(result)

    def _sync_supabase_after_undo(self):
        if not self.hybrid_persistence.is_configured:
            return
        if self.hybrid_persistence.sync_mode == "off":
            return
        self.hybrid_persistence.push_local_to_remote(reason="undo_restore")

    def _show_sync_result(self, result):
        if result is None:
            QMessageBox.information(self, "Supabase sync", "Nessun sync eseguito.")
            return

        counts = ", ".join(f"{key}: {value}" for key, value in result.counts.items())
        details = result.message
        if counts:
            details += "\n" + counts
        if result.skipped_links:
            details += "\nRighe ponte saltate: " + str(len(result.skipped_links))

        if result.ok:
            QMessageBox.information(self, "Supabase sync", details)
        else:
            QMessageBox.warning(self, "Supabase sync", details)

    def _close_registered_repos(self):
        for repo in getattr(self, "_repos", []):
            try:
                repo.session.close()
            except Exception:
                pass
        engine.dispose()

    def _reopen_registered_repos(self):
        for repo in getattr(self, "_repos", []):
            try:
                repo.session = repo.session_factory()
            except Exception:
                pass

    def update_squadra_combo(self):
        session = SessionLocal()
        squadre = session.query(Fantasquadra.nome).filter_by(deleted=False).all()
        session.close()
        
        current_text = self.g_squadra_combo.currentText()
        
        self.g_squadra_combo.blockSignals(True)
        self.g_squadra_combo.clear()
        self.g_squadra_combo.addItem("Tutte le squadre")
        for sq in squadre:
            self.g_squadra_combo.addItem(sq[0])
            
        idx = self.g_squadra_combo.findText(current_text)
        if idx >= 0:
            self.g_squadra_combo.setCurrentIndex(idx)
        else:
            self.g_squadra_combo.setCurrentIndex(0)
            
        self.g_squadra_combo.blockSignals(False)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            active_view = self.g_view
        elif current_tab == 1:
            active_view = self.f_view
        else:
            return  # Mercato tab: no deselect logic needed

        pos_in_viewport = active_view.viewport().mapFromGlobal(event.globalPosition().toPoint())
        clicked_on_table = active_view.viewport().rect().contains(pos_in_viewport)

        if not clicked_on_table:
            active_view.deselect()

    def _upload_quotazioni(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file Quotazioni", "", "File Excel (*.xlsx)"
        )
        
        if not filepath:
            return
            
        try:
            workbook = openpyxl.load_workbook(filepath, data_only=True)
            sheet = workbook.active
            
            self.quotazioni_data.clear()
            
            for row in sheet.iter_rows(min_row=3, values_only=True): #type: ignore
                if len(row) >= 9:
                    nome = row[3]
                    quotazione = row[8]
                    if nome and isinstance(nome, str):
                        self.quotazioni_data[nome.strip()] = quotazione

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
        risposta = QMessageBox.question(
            self, "Conferma Svuotamento",
            "Sei sicuro di voler svuotare le quotazioni attualmente in memoria?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if risposta == QMessageBox.StandardButton.Yes:
            self.quotazioni_data.clear()
            self.lbl_quotazioni_status.setText("Stato: 🔴 Non Caricate")
            self.lbl_quotazioni_status.setStyleSheet("color: red; font-weight: bold;")
            self.btn_clear_quotazioni.setEnabled(False)
            QMessageBox.information(self, "Dati Cancellati", "Le quotazioni sono state rimosse correttamente.")

    def _calculate_update_value(self, dq, spesa):
        new_current_value = spesa if spesa is not None else 0
        dq = dq if dq is not None else 0
        delta_abs = abs(dq)
        delta_sign = 1 if dq > 0 else -1
        
        if dq == 0:
            return new_current_value
            
        for i in range(delta_abs, 0, -1):
            if 1 <= new_current_value <= 49:
                if delta_sign == -1:
                    new_current_value = new_current_value - 3 * delta_abs
                    break
                else:
                    new_current_value += 21.5
            elif 50 <= new_current_value <= 99:
                if delta_sign == -1:
                    new_current_value = new_current_value - 8 * delta_abs
                    break
                else:
                    new_current_value += 18
            elif 100 <= new_current_value <= 199:
                if delta_sign == -1:
                    new_current_value = new_current_value - 12 * delta_abs
                    break
                else:
                    new_current_value += 12
            elif 200 <= new_current_value <= 399:
                if delta_sign == -1:
                    new_current_value = new_current_value - 18 * delta_abs
                    break
                else:
                    new_current_value += 8
            elif 400 <= new_current_value <= 599:
                if delta_sign == -1:
                    new_current_value = new_current_value - 21.5 * delta_abs
                    break
                else:
                    new_current_value += 3
            elif 600 <= new_current_value <= 99999:
                if delta_sign == -1:
                    new_current_value = new_current_value - 30 * delta_abs
                    break
                else:
                    new_current_value += 1
                    
        return new_current_value if new_current_value > 0 else 1

    def _check_prerequisites(self):
        if not hasattr(self, 'quotazioni_data') or not self.quotazioni_data:
            QMessageBox.warning(self, "Attenzione", "Devi prima caricare il file delle Quotazioni!")
            return False
        return True

    def _complete_update(self):
        if not self._check_prerequisites(): return
        
        reply = QMessageBox.question(
            self, "Conferma Complete Update",
            "Questa operazione aggiornerà presenze in Serie A, Quotazioni e Valori di Svincolo calcolando il DQ.\nSei sicuro di voler continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes: return

        base_model = self.get_giocatori_base_model()
        session = base_model.repo.session #type: ignore
        giocatori = session.query(Giocatore).all()

        for g in giocatori:
            if g.nome not in self.quotazioni_data:
                g.in_serie_a = False
                g.convocato = False
                continue
            
            g.in_serie_a = True
            nuova_quotazione = self.quotazioni_data[g.nome]
            vecchia_quotazione = g.quotazione if g.quotazione is not None else 0
            partial_dq = nuova_quotazione - vecchia_quotazione
            g.quotazione = nuova_quotazione
            
            if not g.in_prestito_a:
                valore_dq_attuale = g.dq if g.dq is not None else 0
                g.dq = valore_dq_attuale + partial_dq
                spesa = g.spesa if g.spesa is not None else 1
                g.valore_svincolo = self._calculate_update_value(g.dq, spesa)
            
        session.commit()
        base_model.refresh() #type: ignore
        QMessageBox.information(self, "Successo", "Complete Update completato con successo!")

    def _quotazioni_update(self):
        if not self._check_prerequisites(): return
        
        reply = QMessageBox.question(
            self, "Conferma Quotazioni Update",
            "Questa operazione aggiornerà SOLO le Quotazioni, senza ricalcolare Svincoli o DQ.\nSei sicuro di voler continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes: return

        base_model = self.get_giocatori_base_model()
        session = base_model.repo.session #type: ignore
        giocatori = session.query(Giocatore).all()

        for g in giocatori:
            if g.nome not in self.quotazioni_data:
                g.in_serie_a = False
                g.convocato = False
                continue
            g.in_serie_a = True
            g.quotazione = self.quotazioni_data[g.nome]
            
        session.commit()
        base_model.refresh() #type: ignore
        QMessageBox.information(self, "Successo", "Quotazioni Update completato con successo!")

    def _serie_a_update(self):
        if not self._check_prerequisites(): return
        
        reply = QMessageBox.question(
            self, "Conferma Serie A Update",
            "Questa operazione aggiornerà SOLO lo stato 'In Serie A' e 'Convocato' dei giocatori.\nSei sicuro di voler continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes: return

        base_model = self.get_giocatori_base_model()
        session = base_model.repo.session #type: ignore
        giocatori = session.query(Giocatore).all()

        for g in giocatori:
            if g.nome in self.quotazioni_data:
                g.in_serie_a = True
            else:
                g.in_serie_a = False
                g.convocato = False
                
        session.commit()
        base_model.refresh() #type: ignore
        QMessageBox.information(self, "Successo", "Serie A Update completato con successo!")


    def _set_convocato_bulk(self, value: bool):
        """Set convocato=value for every visible giocatore.
        Blocked when editing is locked; requires confirmation.
        """
        source_model = self.g_model

        # Guard: editing must be unlocked
        if source_model.editing_locked:
            QMessageBox.warning(
                self, "Modifiche bloccate",
                "Sblocca le modifiche prima di cambiare lo stato di convocazione."
            )
            return

        proxy = self.g_proxy_model
        session = source_model.repo.session

        # Collect rows that will actually change
        affected_objs = []
        for proxy_row in range(1, proxy.rowCount()):
            source_index = proxy.mapToSource(proxy.index(proxy_row, 0))
            source_row = source_index.row()
            if source_row < 1:
                continue
            obj = source_model.rows[source_row - 1]
            if obj.convocato != value:
                affected_objs.append(obj)

        if not affected_objs:
            QMessageBox.information(
                self, "Nessuna modifica",
                "Tutti i giocatori visualizzati hanno gia il valore selezionato."
            )
            return

        # Confirmation
        label = "Si" if value else "No"
        n = len(affected_objs)
        reply = QMessageBox.question(
            self, "Conferma modifica convocato",
            "Imposta Convocato = " + label + " per " + str(n) + " giocatori?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Apply and commit
        for obj in affected_objs:
            obj.convocato = value

        try:
            session.commit()
            source_model.refresh()
            QMessageBox.information(
                self, "Successo",
                "Convocato impostato a " + label + " per " + str(n) + " giocatori."
            )
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Errore", str(e))


    def _update_undo_action(self):
        """Enable/disable and relabel the undo menu item after each commit."""
        if not hasattr(self, "_undo_action"):
            return
        n = self._undo_mgr.undo_count()
        self._undo_action.setEnabled(n > 0)
        if n > 0:
            self._undo_action.setText("Annulla ultima operazione  [" + str(n) + " disponibili]")
        else:
            self._undo_action.setText("Annulla ultima operazione")

    def _perform_undo(self):
        """Undo the last DB commit by restoring the previous snapshot."""
        if not self._undo_mgr.can_undo():
            QMessageBox.information(self, "Annulla", "Nessuna operazione da annullare.")
            return

        n_before = self._undo_mgr.undo_count()
        reply = QMessageBox.question(
            self, "Conferma Annulla",
            "Annullare l'ultima operazione?\n"
            "Il database verra ripristinato allo stato precedente.\n"
            "Passi disponibili: " + str(n_before),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._undo_mgr.undo()
            self._update_undo_action()
            n = self._undo_mgr.undo_count()
            QMessageBox.information(
                self, "Annullato",
                "Operazione annullata. Passi undo rimanenti: " + str(n) + "."
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore Undo", "Impossibile annullare:\n" + str(e))

    def _perform_semantic_undo(self):
        transactions = list_undoable_transactions(SessionLocal)
        if not transactions:
            QMessageBox.information(
                self,
                "Undo semantico",
                "Nessuna operazione auditata annullabile.",
            )
            return

        labels = []
        by_label = {}
        for item in transactions:
            label = (
                item.created_at + " | " +
                item.operation_type + " | op " +
                str(item.operation_id or "-") + " | " +
                item.transaction_id[:8]
            )
            labels.append(label)
            by_label[label] = item

        label, ok = QInputDialog.getItem(
            self,
            "Undo semantico",
            "Operazione da annullare:",
            labels,
            0,
            False,
        )
        if not ok or not label:
            return

        item = by_label[label]
        reply = QMessageBox.question(
            self,
            "Conferma undo semantico",
            "Annullare semanticamente questa operazione?\n\n" + label,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._close_registered_repos()
            result = undo_transaction(SessionLocal, item.transaction_id)
        except SemanticUndoConflict as e:
            QMessageBox.warning(
                self,
                "Undo semantico bloccato",
                "Operazione non annullata perche' alcuni dati sono cambiati "
                "dopo la transazione.\n\n" + str(e),
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self,
                "Errore undo semantico",
                "Impossibile annullare l'operazione:\n" + str(e),
            )
            return
        finally:
            self._reopen_registered_repos()

        if getattr(self, "hybrid_persistence", None) is not None:
            if self.hybrid_persistence.sync_mode == "manual":
                self.hybrid_persistence.push_local_to_remote(reason="semantic_undo")

        self.refresh_all_data()
        QMessageBox.information(
            self,
            "Undo semantico",
            "Operazione annullata.\n"
            "Tipo: " + result.operation_type + "\n"
            "Entita ripristinate: " + str(result.restored_entities),
        )

    def closeEvent(self, event):
        try:
            if hasattr(self, "hybrid_persistence"):
                self.hybrid_persistence.stop()
        finally:
            super().closeEvent(event)

    def get_giocatori_base_model(self):
        model = self.g_view.model()
        from PySide6.QtCore import QSortFilterProxyModel
        if isinstance(model, QSortFilterProxyModel):
            return model.sourceModel()
        return model
