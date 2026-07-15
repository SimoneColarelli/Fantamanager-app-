"""
MercatoWidget - Mercato tab of Fantamanager.

Layout:
- Top half: operation form.
- Bottom half: operation history.
"""
from __future__ import annotations
import datetime
import json
from typing import List, Optional, Dict, cast

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QDateEdit, QSpinBox, QSplitter, QToolButton,
    QDialog, QDialogButtonBox, QFileDialog, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont

from models import TIPI_OPERAZIONE
from operazione_repository import OperazioneRepository, contract_expiry_date
from services.mercato_commands import (
    AcquistoDefinitivoCommand,
    AstaManualeCommand,
    AstaPlayerCommand,
    AumentoContrattoCommand,
    ImportaAstaCommand,
    PlayerLoanCommand,
    PlayerQuoteCommand,
    PrestitoCommand,
    RegistraOperazioneCommand,
    ScambioDefinitivoCommand,
    ScambioPrestitiCommand,
    SvincoloCommand,
)
from services.mercato_service import MercatoService
from services.stagione_service import StagioneService


#
from widgets.mercato.auction_row import AstaPlayerRow
from widgets.mercato.common import (
    BORDER,
    COMBO_STYLE,
    CREAM,
    GOLD,
    INPUT_STYLE,
    MUTED,
    NAVY,
    RED,
    WHITE,
    _hsep,
    _lbl,
    _vsep,
)
from widgets.mercato.history import OperazioneCard
from widgets.mercato.player_widgets import ClubPanel, PlayerPickerDialog


MANUAL_TIPI_OPERAZIONE = [
    tipo for tipo in TIPI_OPERAZIONE if tipo != "svincolo fine contratto"
]


class MercatoWidget(QWidget):

    # Emitted after an acquisto is committed so MainWindow can refresh tables
    operazione_committed = Signal()

    def __init__(
        self,
        repo: OperazioneRepository,
        stagione_service: StagioneService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.repo = repo
        self.stagione_service = stagione_service
        self.service = MercatoService.from_repository(repo)
        # MainWindow populates this with persistent repo sessions so
        # calcola_acquisto can expire them before writing (releases SQLite read locks)
        self.sibling_sessions: list = []  # kept for legacy compat
        self.sibling_repos: list = []  # repos to close/reopen around writes
        self._asta_rows: list = []  # AstaPlayerRow list
        self._aumento_player_rows: list = []  # aumento contratto row widgets
        self._aumento_available: list = []  # giocatori available for aumento
        self._build_ui()
        self.refresh_combos()

    @staticmethod
    def _allocate_integer_amount(total: int, weights: dict[int, int]) -> dict[int, int]:
        return OperazioneRepository._allocate_integer_amount(total, weights)
        self._refresh_history()

    #

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_asta_import())
        root.addWidget(_hsep())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_storico())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)

    #

    def _build_asta_import(self) -> QWidget:
        """
        Top bar: [xlsx button] [csv button] [date picker] [Importa Asta button]
        File paths are shown as truncated labels next to each button.
        """
        w = QWidget()
        w.setStyleSheet(f"background: {NAVY};")
        outer = QHBoxLayout(w)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(12)

        #
        self._asta_xlsx_path: Optional[str] = None
        self._asta_csv_path:  Optional[str] = None

        #
        title = _lbl("Importa Asta", bold=True, size=11, color=GOLD)
        outer.addWidget(title)

        sep = _vsep()
        sep.setStyleSheet(f"color: {GOLD}55;")
        outer.addWidget(sep)

        #
        self._xlsx_btn = QPushButton("Quotazioni (.xlsx)")
        self._xlsx_btn.setStyleSheet(self._asta_btn_style())
        self._xlsx_btn.clicked.connect(self._pick_xlsx)
        outer.addWidget(self._xlsx_btn)

        self._xlsx_lbl = QLabel("nessun file")
        self._xlsx_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        self._xlsx_lbl.setMaximumWidth(160)
        outer.addWidget(self._xlsx_lbl)

        sep2 = _vsep()
        sep2.setStyleSheet(f"color: {GOLD}55;")
        outer.addWidget(sep2)

        #
        self._csv_btn = QPushButton("File Asta (.csv)")
        self._csv_btn.setStyleSheet(self._asta_btn_style())
        self._csv_btn.clicked.connect(self._pick_csv)
        outer.addWidget(self._csv_btn)

        self._csv_lbl = QLabel("nessun file")
        self._csv_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        self._csv_lbl.setMaximumWidth(160)
        outer.addWidget(self._csv_lbl)

        sep3 = _vsep()
        sep3.setStyleSheet(f"color: {GOLD}55;")
        outer.addWidget(sep3)

        #
        outer.addWidget(_lbl("Data asta:", size=10, color=CREAM))
        self._asta_data_edit = QDateEdit()
        self._asta_data_edit.setCalendarPopup(True)
        self._asta_data_edit.setDate(QDate.currentDate())
        self._asta_data_edit.setFixedWidth(110)
        self._asta_data_edit.setStyleSheet(f"""
            QDateEdit {{
                border: 1px solid {GOLD};
                border-radius: 4px;
                padding: 3px 6px;
                background: #1a3060;
                font-size: 11px;
                color: {CREAM};
            }}
            QDateEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid {GOLD};
                background: #243870;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
        """)
        outer.addWidget(self._asta_data_edit)

        outer.addStretch()

        #
        self._importa_btn = QPushButton("Importa Asta")
        self._importa_btn.setFixedHeight(34)
        self._importa_btn.setStyleSheet(f"""
            QPushButton {{
                background: {GOLD};
                color: {NAVY};
                border-radius: 5px;
                padding: 0 18px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background: #e0bc60; }}
            QPushButton:pressed {{ background: #b8903a; }}
        """)
        self._importa_btn.clicked.connect(self._importa_asta)
        outer.addWidget(self._importa_btn)

        return w

    @staticmethod
    def _asta_btn_style() -> str:
        return f"""
            QPushButton {{
                background: #1a3060;
                color: {CREAM};
                border: 1px solid {GOLD}88;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: #243870;
                border-color: {GOLD};
            }}
        """

    def _pick_xlsx(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file Quotazioni", "", "Excel files (*.xlsx *.xls)"
        )
        if path:
            self._asta_xlsx_path = path
            import os
            self._xlsx_lbl.setText(os.path.basename(path))
            self._xlsx_lbl.setStyleSheet(f"color: {GOLD}; font-size: 10px; background: transparent;")

    def _pick_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file Asta", "", "CSV files (*.csv *.txt)"
        )
        if path:
            self._asta_csv_path = path
            import os
            self._csv_lbl.setText(os.path.basename(path))
            self._csv_lbl.setStyleSheet(f"color: {GOLD}; font-size: 10px; background: transparent;")

    def _importa_asta(self):
        """
        Parse xlsx + csv, build asta_data list, call repo.importa_asta().
        """
        if not self._asta_xlsx_path:
            QMessageBox.warning(self, "Attenzione", "Seleziona il file Quotazioni (.xlsx)."); return
        if not self._asta_csv_path:
            QMessageBox.warning(self, "Attenzione", "Seleziona il file Asta (.csv)."); return

        #
        try:
            from openpyxl.worksheet.worksheet import Worksheet
            import openpyxl
            wb = openpyxl.load_workbook(self._asta_xlsx_path, read_only=True, data_only=True)
            ws = cast(Worksheet, wb.active)
            quot_map: dict = {}   # ext_id -> {"nome": str, "quotazione": int}
            # Row 1 = title, Row 2 = headers, data starts at Row 3
            for row in ws.iter_rows(min_row=3, values_only=True):
                ext_id = None
                # control of ext_id type is needed because some files have non-numeric garbage in that column (e.g. "ID: 1234")
                if isinstance(row[0], (int, float)):
                    ext_id = int(row[0])  # col 1
                nome   = row[3]   # col 4
                quot   = None
                # control of quot type is needed because some files have non-numeric garbage in that column (e.g. "Q: 12")
                if isinstance(row[8], (int, float)):
                    quot = int(row[8])  # col 9 (Qt.A M)
                if ext_id is not None and nome is not None:
                    quot_map[int(ext_id)] = {
                        "nome":      str(nome),
                        "quotazione": int(quot) if quot is not None else 0,
                    }
            wb.close()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile leggere il file Quotazioni:\n{e}"); return

        #
        try:
            asta_rows: list = []
            with open(self._asta_csv_path, encoding="utf-8-sig", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("$"):
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 3:
                        continue
                    fq_nome = parts[0]
                    try:
                        ext_id = int(parts[1])
                        spesa  = int(parts[2])
                    except ValueError:
                        continue
                    asta_rows.append({"ext_id": ext_id, "fq_nome": fq_nome, "spesa": spesa})
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile leggere il file Asta:\n{e}"); return

        if not asta_rows:
            QMessageBox.warning(self, "Attenzione", "Il file Asta non contiene righe valide."); return

        #
        missing_ids: list = []
        asta_data: list = []
        for row in asta_rows:
            info = quot_map.get(row["ext_id"])
            if info is None:
                missing_ids.append(row["ext_id"])
                continue
            asta_data.append({
                "ext_id":    row["ext_id"],
                "nome":      info["nome"],
                "quotazione": info["quotazione"],
                "fq_nome":   row["fq_nome"],
                "spesa":     row["spesa"],
            })

        # Report missing ids but don't block import of found players
        if missing_ids:
            QMessageBox.warning(
                self, "ID non trovati",
                f"{len(missing_ids)} ID non trovati nel file Quotazioni e verranno saltati:\n"
                + ", ".join(str(i) for i in missing_ids[:20])
                + ("..." if len(missing_ids) > 20 else "")
            )

        if not asta_data:
            QMessageBox.warning(self, "Attenzione", "Nessun giocatore valido da importare."); return

        #
        from collections import Counter
        fq_counts = Counter(r["fq_nome"] for r in asta_data)
        lines = [f"  - {nome}: {n} giocatori" for nome, n in sorted(fq_counts.items())]
        qd = self._asta_data_edit.date()
        data_asta = datetime.date(qd.year(), qd.month(), qd.day())

        reply = QMessageBox.question(
            self, "Conferma Importazione Asta",
            f"Importare {len(asta_data)} giocatori per {len(fq_counts)} squadre?\n"
            f"Data asta: {data_asta.strftime('%d/%m/%Y')}\n\n"
            + "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self._apply_operation_context(data_asta)
            self.service.importa_asta(
                ImportaAstaCommand(
                    asta_data=asta_data,
                    data_asta=data_asta,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile importare l'asta:\n{e}"); return

        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(
            self, "Successo",
            f"Asta importata: {len(asta_data)} giocatori per {len(fq_counts)} squadre."
        )

    #

    def _build_aumento_panel(self) -> QWidget:
        """
        Panel for aumento contratto:
          - Club selector
          - Multi-select player picker (only players of that club)
          - Read-only cost preview per player
        """
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px;")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        outer.addWidget(_lbl("Squadra", bold=True, size=11, color=NAVY))

        self.aumento_club_combo = QComboBox()
        self.aumento_club_combo.setStyleSheet(COMBO_STYLE)
        self.aumento_club_combo.currentIndexChanged.connect(self._on_aumento_club_changed)
        outer.addWidget(self.aumento_club_combo)

        # FM hint
        self.aumento_fm_hint = QLabel("")
        self.aumento_fm_hint.setStyleSheet(f"color: {MUTED}; font-size: 9px; background: transparent;")
        outer.addWidget(self.aumento_fm_hint)

        # Scrollable player list
        self._aumento_list_scroll = QScrollArea()
        self._aumento_list_scroll.setWidgetResizable(True)
        self._aumento_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._aumento_list_scroll.setMinimumHeight(120)
        self._aumento_list_scroll.setStyleSheet("background: transparent;")

        self._aumento_rows_widget = QWidget()
        self._aumento_rows_widget.setStyleSheet("background: transparent;")
        self._aumento_rows_vbox = QVBoxLayout(self._aumento_rows_widget)
        self._aumento_rows_vbox.setContentsMargins(0, 0, 0, 0)
        self._aumento_rows_vbox.setSpacing(4)
        self._aumento_rows_vbox.addStretch()

        self._aumento_list_scroll.setWidget(self._aumento_rows_widget)
        outer.addWidget(self._aumento_list_scroll)

        add_btn = QPushButton("Seleziona giocatori")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CREAM}; color: {NAVY};
                border: 1px dashed {NAVY}77; border-radius: 5px;
                padding: 5px 10px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {NAVY}; color: {WHITE}; border-style: solid; }}
        """)
        add_btn.clicked.connect(self._pick_aumento_players)
        outer.addWidget(add_btn)

        return w

    def _on_aumento_club_changed(self):
        """Clear player rows and reload available giocatori when club changes."""
        self._clear_aumento_rows()
        self._aumento_available: list = []
        fq_id = self.aumento_club_combo.currentData()
        if fq_id is None:
            self.aumento_fm_hint.setText("")
            return
        fq_nome = self.aumento_club_combo.currentText()
        self._aumento_available = self.repo.giocatori_by_squadra(fq_nome)
        # Show FM balance
        fqs = {fq.id: fq for fq in self.repo.active_fantasquadre()}
        fq = fqs.get(fq_id)
        if fq:
            self.aumento_fm_hint.setText(f"  FM disponibili: {fq.fm}")
        else:
            self.aumento_fm_hint.setText("")

    def _pick_aumento_players(self):
        avail = getattr(self, "_aumento_available", [])
        already = {r.giocatore_id for r in self._aumento_player_rows}
        avail = [g for g in avail if g.id not in already]
        if not avail:
            QMessageBox.information(self, "Info", "Nessun giocatore disponibile.")
            return
        dlg = PlayerPickerDialog(avail, self)
        if dlg.exec():
            for pid, name in dlg.picked():
                g = next((x for x in avail if x.id == pid), None)
                if g:
                    self._add_aumento_row(g)
            self._update_aumento_total()

    def _add_aumento_row(self, giocatore):
        """Add a read-only preview row for one player."""
        try:
            costo, anni_extra, nuova_scadenza = self.repo.calcola_costo_aumento(giocatore)
        except ValueError as e:
            QMessageBox.warning(self, "Aumento contratto non valido", str(e))
            return False

        months = ["gen","feb","mar","apr","mag","giu",
                  "lug","ago","set","ott","nov","dic"]
        scad_str = f"{months[nuova_scadenza.month-1]}-{str(nuova_scadenza.year)[2:]}"
        pct_str  = "30%" if anni_extra == 1 else "35%"

        row_w = QFrame()
        row_w.setStyleSheet(f"""
            QFrame {{
                background: {WHITE}; border: 1px solid {BORDER}; border-radius: 5px;
            }}
        """)
        row_w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row_w._giocatore_id = giocatore.id
        row_w._costo = costo

        hl = QHBoxLayout(row_w)
        hl.setContentsMargins(8, 4, 6, 4)
        hl.setSpacing(8)


        # Remove button
        x = QToolButton()
        x.setText("x")
        x.setFixedSize(18, 18)
        f2 = x.font(); f2.setPointSize(10); x.setFont(f2)
        x.setStyleSheet(f"""
            QToolButton {{ color: {MUTED}; background: transparent; border: none; padding: 0; }}
            QToolButton:hover {{ color: {RED}; }}
        """)
        x.clicked.connect(lambda checked=False, r=row_w: self._remove_aumento_row(r))
        hl.addWidget(x)

        name_lbl = QLabel(giocatore.nome)
        name_lbl.setStyleSheet(f"color: {NAVY}; font-size: 11px; font-weight: bold; background: transparent;")
        hl.addWidget(name_lbl, stretch=1)

        info_lbl = QLabel(f"{pct_str}  ->  -{costo} FM  *  scad. {scad_str}")
        info_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        hl.addWidget(info_lbl)

        self._aumento_player_rows.append(row_w)
        self._aumento_rows_vbox.insertWidget(
            self._aumento_rows_vbox.count() - 1, row_w
        )
        self._aumento_rows_widget.updateGeometry()

    def _remove_aumento_row(self, row_w):
        if row_w in self._aumento_player_rows:
            self._aumento_player_rows.remove(row_w)
            self._aumento_rows_vbox.removeWidget(row_w)
            row_w.deleteLater()
            self._aumento_rows_widget.updateGeometry()
            self._update_aumento_total()

    def _clear_aumento_rows(self):
        for r in list(self._aumento_player_rows):
            self._aumento_rows_vbox.removeWidget(r)
            r.deleteLater()
        self._aumento_player_rows.clear()
        self._aumento_rows_widget.updateGeometry()
        self._update_aumento_total()

    def _update_aumento_total(self):
        total = sum(r._costo for r in self._aumento_player_rows)
        fq_id = self.aumento_club_combo.currentData()
        fqs = {fq.id: fq for fq in self.repo.active_fantasquadre()}
        fq = fqs.get(fq_id) if fq_id else None
        fm = fq.fm if fq else 0
        if self._aumento_player_rows:
            color = RED if total > fm else MUTED
            self.aumento_fm_hint.setStyleSheet(
                f"color: {color}; font-size: 9px; background: transparent;"
            )
            self.aumento_fm_hint.setText(
                f"  FM disponibili: {fm}  |  Costo totale: {total} FM"
            )
        else:
            self.aumento_fm_hint.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; background: transparent;"
            )
            self.aumento_fm_hint.setText(f"  FM disponibili: {fm}" if fq else "")

    #

    def _build_asta_panel(self) -> QWidget:
        """
        Panel shown when tipo == 'asta':
          - Club selector (single fantasquadra)
          - Scrollable list of AstaPlayerRow
          - '+ Aggiungi giocatore' button
        """
        w = QWidget()
        w.setStyleSheet(f"background: {WHITE}; border: 1px solid {BORDER}; border-radius: 8px;")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)

        outer.addWidget(_lbl("Squadra", bold=True, size=11, color=NAVY))

        self.asta_club_combo = QComboBox()
        self.asta_club_combo.setStyleSheet(COMBO_STYLE)
        outer.addWidget(self.asta_club_combo)

        # Scrollable list of rows
        self._asta_list_scroll = QScrollArea()
        self._asta_list_scroll.setWidgetResizable(True)
        self._asta_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._asta_list_scroll.setMinimumHeight(120)
        self._asta_list_scroll.setStyleSheet("background: transparent;")

        self._asta_rows_widget = QWidget()
        self._asta_rows_widget.setStyleSheet("background: transparent;")
        self._asta_rows_vbox = QVBoxLayout(self._asta_rows_widget)
        self._asta_rows_vbox.setContentsMargins(0, 0, 0, 0)
        self._asta_rows_vbox.setSpacing(4)
        self._asta_rows_vbox.addStretch()

        self._asta_list_scroll.setWidget(self._asta_rows_widget)
        outer.addWidget(self._asta_list_scroll)

        add_btn = QPushButton("Aggiungi acquisto")
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CREAM}; color: {NAVY};
                border: 1px dashed {NAVY}77; border-radius: 5px;
                padding: 5px 10px; font-size: 11px;
            }}
            QPushButton:hover {{
                background: {NAVY}; color: {WHITE}; border-style: solid;
            }}
        """)
        add_btn.clicked.connect(self._add_asta_row)
        outer.addWidget(add_btn)

        return w

    def _add_asta_row(self):
        """Add a new AstaPlayerRow to the asta panel."""
        row = AstaPlayerRow(show_estendi=True)
        row.removed.connect(lambda r=row: self._remove_asta_row(r))
        self._asta_rows.append(row)
        # Insert before the trailing stretch
        self._asta_rows_vbox.insertWidget(self._asta_rows_vbox.count() - 1, row)
        self._asta_rows_widget.updateGeometry()

    def _remove_asta_row(self, row):
        if row in self._asta_rows:
            self._asta_rows.remove(row)
            self._asta_rows_vbox.removeWidget(row)
            row.deleteLater()
            self._asta_rows_widget.updateGeometry()

    def _clear_asta_rows(self):
        for row in list(self._asta_rows):
            self._asta_rows_vbox.removeWidget(row)
            row.deleteLater()
        self._asta_rows.clear()
        self._asta_rows_widget.updateGeometry()

    #

    def _build_form(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {CREAM};")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 14, 16, 10)
        outer.setSpacing(10)

        # Title
        outer.addWidget(_lbl("Nuova Operazione", bold=True, size=13, color=NAVY))
        outer.addWidget(_hsep())

        # Tipo row
        tipo_row = QHBoxLayout()
        tipo_row.addWidget(_lbl("Tipo operazione:", size=11, color=MUTED))
        self.tipo_combo = QComboBox()
        self.tipo_combo.addItems(MANUAL_TIPI_OPERAZIONE)
        self.tipo_combo.setStyleSheet(COMBO_STYLE)
        self.tipo_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tipo_combo.currentTextChanged.connect(self._on_tipo_changed)
        tipo_row.addWidget(self.tipo_combo)
        outer.addLayout(tipo_row)

        # Club panels row
        panels = QHBoxLayout()
        panels.setSpacing(10)
        self.panel_a = ClubPanel("Squadra A")
        self.panel_b = ClubPanel("Squadra B")
        self.panel_a.fm_changed.connect(self._on_fm_mutex)
        self.panel_b.fm_changed.connect(self._on_fm_mutex)
        # When club selection changes, load that club's players from the repo
        self.panel_a.club_changed_to.connect(lambda nome: self._load_players_for_panel(self.panel_a, nome))
        self.panel_b.club_changed_to.connect(lambda nome: self._load_players_for_panel(self.panel_b, nome))
        panels.addWidget(self.panel_a)
        self._vsep_widget = _vsep()
        panels.addWidget(self._vsep_widget)
        panels.addWidget(self.panel_b)
        outer.addLayout(panels)

        #
        self._asta_panel = self._build_asta_panel()
        self._asta_panel.setVisible(False)
        outer.addWidget(self._asta_panel)

        #
        self._aumento_panel = self._build_aumento_panel()
        self._aumento_panel.setVisible(False)
        outer.addWidget(self._aumento_panel)

        # Bottom strip
        outer.addWidget(_hsep())
        bottom = QHBoxLayout()
        bottom.setSpacing(14)

        date_col = QVBoxLayout()
        date_col.addWidget(_lbl("Data:", size=10, color=MUTED))
        self.data_edit = QDateEdit()
        self.data_edit.setCalendarPopup(True)
        self.data_edit.setDate(QDate.currentDate())
        self.data_edit.setStyleSheet(INPUT_STYLE)
        date_col.addWidget(self.data_edit)
        bottom.addLayout(date_col)

        cl_col = QVBoxLayout()
        cl_col.addWidget(_lbl("Clausole / Note:", size=10, color=MUTED))
        self.clausole_edit = QLineEdit()
        self.clausole_edit.setPlaceholderText("Eventuali clausole o note...")
        self.clausole_edit.setStyleSheet(INPUT_STYLE)
        cl_col.addWidget(self.clausole_edit)
        bottom.addLayout(cl_col, stretch=1)

        self.submit_btn = QPushButton("Registra")
        self.submit_btn.setFixedHeight(36)
        self.submit_btn.setStyleSheet(f"""
            QPushButton {{
                background: {NAVY}; color: {WHITE};
                border-radius: 5px; padding: 0 20px;
                font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #1a3460; }}
            QPushButton:pressed {{ background: #0a1228; }}
        """)
        self.submit_btn.clicked.connect(self._submit)
        bottom.addWidget(self.submit_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        outer.addLayout(bottom)
        return w

    #

    def _build_storico(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: #f0f2f5;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(_lbl("Storico Operazioni", bold=True, size=13, color=NAVY))
        hdr.addStretch()
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Tutte")
        self.filter_combo.addItems(TIPI_OPERAZIONE)
        self.filter_combo.setStyleSheet(COMBO_STYLE)
        self.filter_combo.currentTextChanged.connect(self._refresh_history)
        hdr.addWidget(self.filter_combo)
        layout.addLayout(hdr)
        layout.addWidget(_hsep())

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.history_scroll.setStyleSheet("background: transparent;")

        self.cards_w = QWidget()
        self.cards_w.setStyleSheet("background: transparent;")
        self.cards_vbox = QVBoxLayout(self.cards_w)
        self.cards_vbox.setContentsMargins(0, 0, 4, 0)
        self.cards_vbox.setSpacing(8)
        self.cards_vbox.addStretch()

        self.history_scroll.setWidget(self.cards_w)
        layout.addWidget(self.history_scroll)
        return w

    #

    def refresh_combos(self):
        fqs = self.repo.active_fantasquadre()
        self.panel_a.set_fantasquadre(fqs, with_empty=True)
        self.panel_b.set_fantasquadre(fqs, with_empty=True)
        # Populate asta club combo
        self.asta_club_combo.blockSignals(True)
        self.asta_club_combo.clear()
        self.asta_club_combo.addItem("- seleziona squadra -", userData=None)
        for fq in fqs:
            if isinstance(fq.nome, str):
                self.asta_club_combo.addItem(fq.nome, userData=fq.id)
        self.asta_club_combo.blockSignals(False)
        # Populate aumento contratto club combo
        self.aumento_club_combo.blockSignals(True)
        self.aumento_club_combo.clear()
        self.aumento_club_combo.addItem("- seleziona squadra -", userData=None)
        for fq in fqs:
            self.aumento_club_combo.addItem(fq.nome, userData=fq.id)
        self.aumento_club_combo.blockSignals(False)
        self._on_tipo_changed(self.tipo_combo.currentText())

    def _apply_operation_context(self, operation_date: datetime.date | None) -> None:
        if not self.stagione_service:
            self.repo.clear_operation_context()
            return
        context = self.stagione_service.get_market_operation_context(operation_date)
        self.repo.set_operation_context(context.as_dict() if context else None)

    def _load_players_for_panel(self, panel: ClubPanel, squadra_nome: str):
        """Fetch players for the selected squadra and hand them to the panel."""
        if not squadra_nome:
            panel.set_giocatori_for_squadra([])
            return
        giocatori = self.repo.giocatori_by_squadra(squadra_nome)
        panel.set_giocatori_for_squadra(giocatori)

    #

    def _on_tipo_changed(self, tipo: str):
        is_svincolo  = (tipo == "svincolo")
        is_prestito  = (tipo == "prestito")
        is_scambio_p = (tipo == "scambio prestiti")
        is_asta      = (tipo == "asta")
        is_aumento   = (tipo == "aumento contratto")

        # Show/hide standard panels vs special panels
        self.panel_a.setVisible(not is_asta and not is_aumento)
        self.panel_b.setVisible(not is_svincolo and not is_asta and not is_aumento)
        self._vsep_widget.setVisible(not is_svincolo and not is_asta and not is_aumento)
        self._asta_panel.setVisible(is_asta)
        self._aumento_panel.setVisible(is_aumento)

        # Show estendi contratto per-player checkbox for acquisto/scambio
        is_estendi = tipo in ("acquisto definitivo", "scambio definitivo")
        self.panel_a.set_estendi_mode(is_estendi)
        self.panel_b.set_estendi_mode(is_estendi)

        if not is_asta and not is_aumento:
            # prestito: only panel_a (the lender) shows fine_prestito per player
            # scambio prestiti: both panels show it
            self.panel_a.set_fine_prestito_mode(is_prestito or is_scambio_p)
            self.panel_b.set_fine_prestito_mode(is_scambio_p)

    def _on_fm_mutex(self):
        """
        Called whenever either panel's FM spin changes.

        Enforces three rules reactively via spin range:
          1. Mutex: only one panel may have FM > 0 at a time.
          2. Cap: the FM entered cannot exceed the paying panel's current FM balance.
          3. Acquisto floor: for acquisto definitivo the FM must be >= sum of
             valore_svincolo of the players added by the buying panel.
        """
        a = self.panel_a.fm_spin.value()
        b = self.panel_b.fm_spin.value()
        tipo = self.tipo_combo.currentText()

        #
        if a > 0:
            self.panel_b.set_fm_enabled(False)
        elif b > 0:
            self.panel_a.set_fm_enabled(False)
        else:
            self.panel_a.set_fm_enabled(True)
            self.panel_b.set_fm_enabled(True)

        #
        for panel in (self.panel_a, self.panel_b):
            if not panel.fm_spin.isEnabled():
                panel.fm_hint_lbl.setVisible(False)
                continue
            balance = panel.fq_fm()
            if balance is None:
                panel.fm_spin.setMaximum(999999)
                panel.fm_hint_lbl.setVisible(False)
                continue

            # For acquisto definitivo the buyer (the FM payer) must also cover
            # the total valore_svincolo of the players they are buying.
            # The buyer is the panel that has FM (no players in acquisto).
            if tipo == "acquisto definitivo":
                # In acquisto: seller has players, buyer has FM.
                # The opposite panel's VS is the floor.
                other = self.panel_b if panel is self.panel_a else self.panel_a
                vs_floor = int(other.total_vs())
                maximum = balance
                panel.fm_spin.blockSignals(True)
                panel.fm_spin.setMinimum(0)
                panel.fm_spin.setMaximum(max(0, maximum))
                panel.fm_spin.blockSignals(False)
                panel.update_fm_hint(vs_floor=vs_floor)
            else:
                panel.fm_spin.blockSignals(True)
                panel.fm_spin.setMinimum(0)
                panel.fm_spin.setMaximum(balance)
                panel.fm_spin.blockSignals(False)
                panel.update_fm_hint()

    #

    def _submit(self):
        tipo = self.tipo_combo.currentText()

        #
        fq_a_id   = self.panel_a.club_id()
        fq_b_id   = self.panel_b.club_id() if tipo != "svincolo" else None
        ids_a     = self.panel_a.player_ids()
        ids_b     = self.panel_b.player_ids()
        fm_a      = self.panel_a.fm_value()
        fm_b      = self.panel_b.fm_value()
        qd        = self.data_edit.date()
        data      = datetime.date(qd.year(), qd.month(), qd.day())
        clausole  = self.clausole_edit.text().strip() or None
        self._apply_operation_context(data)

        #
        if tipo == "asta":
            self._submit_asta()
            return
        if tipo == "aumento contratto":
            self._submit_aumento_contratto()
            return

        #
        if fq_a_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra A."); return
        if tipo != "svincolo" and fq_b_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra B."); return
        if tipo != "svincolo" and fq_a_id == fq_b_id:
            QMessageBox.warning(self, "Attenzione", "Squadra A e B devono essere diverse."); return
        if not ids_a and not ids_b:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore."); return

        #
        if tipo == "acquisto definitivo":
            self._submit_acquisto(
                fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole
            )
        elif tipo == "scambio definitivo":
            self._submit_scambio(
                fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole
            )
        elif tipo == "prestito":
            self._submit_prestito(
                fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole
            )
        elif tipo == "scambio prestiti":
            self._submit_scambio_prestiti(
                fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole
            )
        elif tipo == "svincolo":
            self._submit_svincolo(fq_a_id, ids_a, data, clausole)
        else:
            self._submit_generic(
                tipo, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole
            )

    #

    def _submit_acquisto(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate acquisto-specific rules, show confirmation summary,
        then call repo.calcola_acquisto().

        Rules:
          - Players must be on exactly ONE side (the seller's side).
          - FM must be on the OTHER side (the buyer's side).
          - FM must be > 0.
        """
        #
        has_a = bool(ids_a)
        has_b = bool(ids_b)

        if has_a and has_b:
            QMessageBox.warning(
                self, "Attenzione",
                "Per un acquisto definitivo i giocatori devono essere\n"
                "aggiunti solo da UNA delle due squadre (il venditore)."
            )
            return

        if fm_a > 0 and fm_b > 0:
            QMessageBox.warning(
                self, "Attenzione",
                "Solo la squadra acquirente puo inserire un importo FM."
            )
            return

        if fm_a == 0 and fm_b == 0:
            QMessageBox.warning(
                self, "Attenzione",
                "Inserisci l'importo FM pagato dalla squadra acquirente."
            )
            return

        # Determine seller / buyer
        if has_a and fm_b > 0:
            fq_venditrice_id = fq_a_id
            fq_acquirente_id = fq_b_id
            fm = fm_b
            giocatori_form_data = self.panel_a.player_data()
            buyer_panel  = self.panel_b
            seller_panel = self.panel_a
        elif has_b and fm_a > 0:
            fq_venditrice_id = fq_b_id
            fq_acquirente_id = fq_a_id
            fm = fm_a
            giocatori_form_data = self.panel_b.player_data()
            buyer_panel  = self.panel_a
            seller_panel = self.panel_b
        else:
            QMessageBox.warning(
                self, "Attenzione",
                "I giocatori devono essere nella squadra venditrice\n"
                "e il pagamento FM nella squadra acquirente."
            )
            return

        # FM must not exceed buyer's balance
        buyer_balance = buyer_panel.fq_fm()
        if buyer_balance is not None and fm > buyer_balance:
            QMessageBox.warning(
                self, "Attenzione",
                f"La squadra acquirente non ha abbastanza FM.\n"
                f"Disponibili: {buyer_balance} FM - Richiesti: {fm} FM"
            )
            return

        # FM must cover total valore_svincolo of sold players
        vs_floor = int(seller_panel.total_vs())
        if vs_floor > 0 and fm < vs_floor:
            QMessageBox.warning(
                self, "Attenzione",
                f"L'importo FM ({fm}) e inferiore al valore di svincolo totale\n"
                f"dei giocatori ceduti ({vs_floor} FM)."
            )
            return

        # Build the giocatori_data list for the repo
        giocatori_data = [
            {"id": pid, "quotazione": q if q is not None else 0}
            for pid, q in giocatori_form_data
        ]

        if any(d["quotazione"] == 0 for d in giocatori_data):
            QMessageBox.warning(
                self, "Attenzione",
                "Uno o piu giocatori hanno quotazione 0.\n"
                "Verifica le quotazioni nella lista prima di procedere."
            )
            return

        #
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_venditrice  = fqs.get(fq_venditrice_id, str(fq_venditrice_id))
        nome_acquirente  = fqs.get(fq_acquirente_id, str(fq_acquirente_id))

        # Build player summary lines
        tot_quot = sum(d["quotazione"] for d in giocatori_data)
        preview_spese = self._allocate_integer_amount(
            int(fm), {d["id"]: d["quotazione"] for d in giocatori_data}
        )
        lines = []
        for d in giocatori_data:
            spesa_i = preview_spese.get(d["id"], 0)
            # find name from form data
            nome = next(
                (name for pid, name in
                 (self.panel_a.player_data() if fq_venditrice_id == fq_a_id
                  else self.panel_b.player_data())
                 if pid == d["id"]),
                f"ID {d['id']}"
            )
            lines.append(
                f"  - {nome} - Q: {d['quotazione']} - Spesa: {spesa_i:.0f} FM"
            )

        data_norm = data.replace(day=1)
        scadenza = contract_expiry_date(data_norm)

        summary = (
            f"Confermi il seguente acquisto definitivo?\n\n"
            f"  Venditore :  {nome_venditrice}  (+{fm} FM)\n"
            f"  Acquirente:  {nome_acquirente}  (-{fm} FM)\n"
            f"  Data acquisto:  {data_norm.strftime('%d/%m/%Y')}\n"
            f"  Scadenza contratto:  {scadenza.strftime('%d/%m/%Y')}\n\n"
            f"Giocatori ceduti:\n"
            + "\n".join(lines)
        )

        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Acquisto Definitivo", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self.service.registra_acquisto_definitivo(
                AcquistoDefinitivoCommand(
                    giocatori=[
                        PlayerQuoteCommand(id=d["id"], quotazione=d["quotazione"])
                        for d in giocatori_data
                    ],
                    fq_venditrice_id=fq_venditrice_id,
                    fq_acquirente_id=fq_acquirente_id,
                    fm=fm,
                    data_acquisto=data,
                    clausole=clausole,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire l'acquisto:\n{e}")
            return

        # Extend contratto for players whose per-row checkbox is checked
        estendi_ids = [
            r.giocatore_id for r in
            (self.panel_a.player_list._rows if fq_venditrice_id == fq_a_id
             else self.panel_b.player_list._rows)
            if r.estendi_value()
        ]
        if estendi_ids:
            self._maybe_estendi_contratto(fq_acquirente_id, estendi_ids)
        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(self, "Successo", "Acquisto definitivo registrato correttamente.")

    #

    def _submit_scambio(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate scambio-specific rules, show confirmation summary,
        then call repo.calcola_scambio().

        Rules:
          - Both sides must have at least one player.
          - FM is optional and can only be on one side (the payer).
          - FM payer = fq_b by convention (if fm_a > 0, we swap roles so
            the panel that paid always ends up as fq_b in the repo call).
        """
        #
        if not ids_a:
            QMessageBox.warning(
                self, "Attenzione",
                "Per uno scambio definitivo la Squadra A deve avere almeno un giocatore."
            ); return
        if not ids_b:
            QMessageBox.warning(
                self, "Attenzione",
                "Per uno scambio definitivo la Squadra B deve avere almeno un giocatore."
            ); return
        if fm_a > 0 and fm_b > 0:
            QMessageBox.warning(
                self, "Attenzione",
                "Solo una delle due squadre puo inserire un conguaglio FM."
            ); return

        #
        if fm_a > 0:
            #
            fq_a_id_eff, fq_b_id_eff = fq_b_id, fq_a_id
            data_a_eff = self.panel_b.player_data()   # players from original B go to original A
            data_b_eff = self.panel_a.player_data()   # players from original A go to original B
            fm = fm_a
        else:
            fq_a_id_eff, fq_b_id_eff = fq_a_id, fq_b_id
            data_a_eff = self.panel_a.player_data()
            data_b_eff = self.panel_b.player_data()
            fm = fm_b  # may be 0; that's fine

        giocatori_data_a = [
            {"id": pid, "quotazione": q if q is not None else 0}
            for pid, q in data_a_eff
        ]
        giocatori_data_b = [
            {"id": pid, "quotazione": q if q is not None else 0}
            for pid, q in data_b_eff
        ]

        if any(d["quotazione"] == 0 for d in giocatori_data_a + giocatori_data_b):
            QMessageBox.warning(
                self, "Attenzione",
                "Uno o piu giocatori hanno quotazione 0.\n"
                "Verifica le quotazioni nella lista prima di procedere."
            ); return

        #
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_a = cast(str, fqs.get(fq_a_id_eff, str(fq_a_id_eff)))
        nome_b = cast(str, fqs.get(fq_b_id_eff, str(fq_b_id_eff)))

        # Need valore_svincolo from DB for amount computation preview
        all_vs: dict = {}
        for glist in (
            self.repo.giocatori_by_squadra(nome_a),
            self.repo.giocatori_by_squadra(nome_b),
        ):
            for g in glist:
                all_vs[g.id] = int(g.valore_svincolo or 0)

        amount_A = sum(all_vs.get(d["id"], 0) for d in giocatori_data_a)
        amount_B = sum(all_vs.get(d["id"], 0) for d in giocatori_data_b) + fm

        data_norm = data.replace(day=1)
        scadenza = contract_expiry_date(data_norm)

        tot_quotA = sum(d["quotazione"] for d in giocatori_data_a)
        tot_quotB = sum(d["quotazione"] for d in giocatori_data_b)

        #
        name_map: dict = {}
        for panel in (self.panel_a, self.panel_b):
            for row in panel.player_list._rows:
                from PySide6.QtWidgets import QLabel
                labels = row.findChildren(QLabel)
                if labels:
                    name_map[row.giocatore_id] = labels[0].text()

        def _player_lines(gdata, amount_in, tot_quot, dest_nome):
            lines = []
            preview_spese = self._allocate_integer_amount(
                int(amount_in), {d["id"]: d["quotazione"] for d in gdata}
            ) if tot_quot else {}
            for d in gdata:
                spesa = preview_spese.get(d["id"], 0)
                name = name_map.get(d["id"], f"ID {d['id']}")
                lines.append(
                    f"  - {name}  Q:{d['quotazione']}  ->  {dest_nome}  Spesa:{spesa:.0f} FM"
                )
            return lines

        lines_a = _player_lines(giocatori_data_a, amount_B, tot_quotA, nome_b)
        lines_b = _player_lines(giocatori_data_b, amount_A, tot_quotB, nome_a)

        summary = (
            f"Confermi il seguente scambio definitivo?\n\n"
            f"  {nome_a}  <->  {nome_b}\n"
            f"  Data acquisto:  {data_norm.strftime('%d/%m/%Y')}\n"
            f"  Scadenza contratto:  {scadenza.strftime('%d/%m/%Y')}\n"
        )
        if fm > 0:
            summary += f"  Conguaglio: {nome_b} paga {fm} FM a {nome_a}\n"
        summary += f"\nGiocatori ceduti da {nome_a}:\n" + "\n".join(lines_a)
        summary += f"\n\nGiocatori ceduti da {nome_b}:\n" + "\n".join(lines_b)
        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Scambio Definitivo", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self.service.registra_scambio_definitivo(
                ScambioDefinitivoCommand(
                    giocatori_a=[
                        PlayerQuoteCommand(id=d["id"], quotazione=d["quotazione"])
                        for d in giocatori_data_a
                    ],
                    giocatori_b=[
                        PlayerQuoteCommand(id=d["id"], quotazione=d["quotazione"])
                        for d in giocatori_data_b
                    ],
                    fq_a_id=fq_a_id_eff,
                    fq_b_id=fq_b_id_eff,
                    fm=fm,
                    data_acquisto=data,
                    clausole=clausole,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire lo scambio:\n{e}")
            return

        # Extend contratto for players whose per-row checkbox is checked
        #
        # (after possible swap when fm_a > 0)
        if fm_a > 0:  # panels were swapped
            rows_to_b = self.panel_b.player_list._rows
            rows_to_a = self.panel_a.player_list._rows
        else:
            rows_to_b = self.panel_a.player_list._rows
            rows_to_a = self.panel_b.player_list._rows
        estendi_to_b = [r.giocatore_id for r in rows_to_b if r.estendi_value()]
        estendi_to_a = [r.giocatore_id for r in rows_to_a if r.estendi_value()]
        if estendi_to_b:
            self._maybe_estendi_contratto(fq_b_id_eff, estendi_to_b)
        if estendi_to_a:
            self._maybe_estendi_contratto(fq_a_id_eff, estendi_to_a)
        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()   # reuse same signal; refreshes all tables
        QMessageBox.information(self, "Successo", "Scambio definitivo registrato correttamente.")

    #

    def _submit_prestito(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate prestito rules, show confirmation, then call repo.calcola_prestito().

        Rules:
          - Players must be on exactly ONE side (the lender, fq_a).
          - FM is optional (can be 0) and must be on the OTHER side (fq_b).
          - Each player in panel_a must have a fine_prestito date set.
        """
        #
        has_a = bool(ids_a)
        has_b = bool(ids_b)

        if has_a and has_b:
            QMessageBox.warning(
                self, "Attenzione",
                "Per un prestito i giocatori devono essere aggiunti\n"
                "solo da UNA delle due squadre (il prestante)."
            ); return
        if not has_a and not has_b:
            QMessageBox.warning(
                self, "Attenzione", "Seleziona almeno un giocatore da prestare."
            ); return
        if fm_a > 0 and fm_b > 0:
            QMessageBox.warning(
                self, "Attenzione", "Solo la squadra che riceve il prestito puo inserire FM."
            ); return

        # Determine lender / borrower
        if has_a:
            fq_prestante_id  = fq_a_id
            fq_ricevente_id  = fq_b_id
            fm               = fm_b
            pdata            = self.panel_a.player_data_prestito()
        else:
            fq_prestante_id  = fq_b_id
            fq_ricevente_id  = fq_a_id
            fm               = fm_a
            pdata            = self.panel_b.player_data_prestito()

        if fm_a > 0 and has_b:
            #
            pass

        giocatori_data = [
            {"id": pid, "fine_prestito": fp}
            for pid, _q, fp in pdata
        ]

        # fine_prestito must be set for every player
        missing_dates = [d for d in giocatori_data if d["fine_prestito"] is None]
        if missing_dates:
            QMessageBox.warning(
                self, "Attenzione",
                "Imposta la data di fine prestito per ogni giocatore."
            ); return

        #
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_prestante  = fqs.get(fq_prestante_id,  str(fq_prestante_id))
        nome_ricevente  = fqs.get(fq_ricevente_id, str(fq_ricevente_id))

        # Build name_map from rows
        name_map: dict = {}
        for panel in (self.panel_a, self.panel_b):
            for r in panel.player_list._rows:
                name_map[r.giocatore_id] = r.name()

        data_norm = data.replace(day=1)
        lines = []
        for d in giocatori_data:
            name = name_map.get(d["id"], f"ID {d['id']}")
            fp   = d["fine_prestito"].strftime("%d/%m/%Y")
            lines.append(f"  - {name}  fine prestito: {fp}")

        summary = (
            f"Confermi il seguente prestito?\n\n"
            f"  Prestante : {nome_prestante}\n"
            f"  Ricevente : {nome_ricevente}\n"
            f"  Inizio    : {data_norm.strftime('%d/%m/%Y')}\n"
        )
        if fm > 0:
            summary += f"  Conguaglio: {nome_ricevente} paga {fm} FM a {nome_prestante}\n"
        summary += f"\nGiocatori:\n" + "\n".join(lines)
        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Prestito", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self.service.registra_prestito(
                PrestitoCommand(
                    giocatori=[
                        PlayerLoanCommand(id=d["id"], fine_prestito=d["fine_prestito"])
                        for d in giocatori_data
                    ],
                    fq_prestante_id=fq_prestante_id,
                    fq_ricevente_id=fq_ricevente_id,
                    fm=fm,
                    inizio_prestito=data,
                    clausole=clausole,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile registrare il prestito:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(self, "Successo", "Prestito registrato correttamente.")

    #

    def _submit_scambio_prestiti(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate scambio prestiti rules, show confirmation, then call
        repo.calcola_scambio_prestiti().

        Rules:
          - Both sides must have at least one player (each lends to the other).
          - FM is optional (can be 0) and on at most one side.
          - Both sides needs a fine_prestito date.
        """
        #
        if not ids_a:
            QMessageBox.warning(
                self, "Attenzione",
                "Per uno scambio prestiti la Squadra A deve avere almeno un giocatore."
            ); return
        if not ids_b:
            QMessageBox.warning(
                self, "Attenzione",
                "Per uno scambio prestiti la Squadra B deve avere almeno un giocatore."
            ); return
        if fm_a > 0 and fm_b > 0:
            QMessageBox.warning(
                self, "Attenzione", "Solo una delle due squadre puo inserire un conguaglio FM."
            ); return

        # Determine FM payer (fq_b by convention; swap if panel_a paid)
        if fm_a > 0:
            fq_a_id_eff, fq_b_id_eff = fq_b_id, fq_a_id
            pdata_a = self.panel_b.player_data_prestito()   # players from original B
            pdata_b = self.panel_a.player_data_prestito()   # players from original A
            fm = fm_a
        else:
            fq_a_id_eff, fq_b_id_eff = fq_a_id, fq_b_id
            pdata_a = self.panel_a.player_data_prestito()
            pdata_b = self.panel_b.player_data_prestito()
            fm = fm_b  # may be 0

        giocatori_data_a = [{"id": pid, "fine_prestito": fp} for pid, _q, fp in pdata_a]
        giocatori_data_b = [{"id": pid, "fine_prestito": fp} for pid, _q, fp in pdata_b]

        # All players must have a fine_prestito date
        all_data = giocatori_data_a + giocatori_data_b
        if any(d["fine_prestito"] is None for d in all_data):
            QMessageBox.warning(
                self, "Attenzione",
                "Imposta la data di fine prestito per ogni giocatore."
            ); return

        #
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_a = fqs.get(fq_a_id_eff, str(fq_a_id_eff))
        nome_b = fqs.get(fq_b_id_eff, str(fq_b_id_eff))

        name_map: dict = {}
        for panel in (self.panel_a, self.panel_b):
            for r in panel.player_list._rows:
                name_map[r.giocatore_id] = r.name()

        data_norm = data.replace(day=1)

        def _lines(gdata, dest):
            lines = []
            for d in gdata:
                gid = d["id"]
                name = name_map.get(gid, f"ID {gid}")
                fp = d["fine_prestito"].strftime("%d/%m/%Y")
                lines.append(f"  - {name}  fine prestito: {fp}  ->  {dest}")
            return lines

        summary = (
            f"Confermi il seguente scambio prestiti?\n\n"
            f"  {nome_a}  <->  {nome_b}\n"
            f"  Inizio: {data_norm.strftime('%d/%m/%Y')}\n"
        )
        if fm > 0:
            summary += f"  Conguaglio: {nome_b} paga {fm} FM a {nome_a}\n"
        summary += f"\nGiocatori prestati da {nome_a}:\n" + "\n".join(_lines(giocatori_data_a, nome_b))
        summary += f"\n\nGiocatori prestati da {nome_b}:\n" + "\n".join(_lines(giocatori_data_b, nome_a))
        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Scambio Prestiti", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self.service.registra_scambio_prestiti(
                ScambioPrestitiCommand(
                    giocatori_a=[
                        PlayerLoanCommand(id=d["id"], fine_prestito=d["fine_prestito"])
                        for d in giocatori_data_a
                    ],
                    giocatori_b=[
                        PlayerLoanCommand(id=d["id"], fine_prestito=d["fine_prestito"])
                        for d in giocatori_data_b
                    ],
                    fq_a_id=fq_a_id_eff,
                    fq_b_id=fq_b_id_eff,
                    fm=fm,
                    inizio_prestito=data,
                    clausole=clausole,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile registrare lo scambio prestiti:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(self, "Successo", "Scambio prestiti registrato correttamente.")

    #

    def _submit_svincolo(self, fq_id, ids, data, clausole):
        """
        Sum valore_svincolo of all selected players, credit it to the
        fantasquadra's FM, then hard-delete the players from the DB.
        """
        if not ids:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore da svincolare."); return

        #
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_fq = fqs.get(fq_id, str(fq_id))

        name_map: dict = {}
        for r in self.panel_a.player_list._rows:
            name_map[r.giocatore_id] = r.name()

        # Fetch current valore_svincolo from DB
        giocatori_db = {
            g.id: g for g in self.repo.giocatori_by_squadra(
                self.panel_a.club_combo.currentText()
            )
        }
        total_vs = sum(
            int(giocatori_db[pid].valore_svincolo or 0) for pid in ids if pid in giocatori_db
        )

        lines = []
        for pid in ids:
            name = name_map.get(pid, f"ID {pid}")
            vs   = int(giocatori_db[pid].valore_svincolo or 0) if pid in giocatori_db else 0
            lines.append(f"  - {name}  VS: {int(vs or 0)} FM")

        summary = (
            f"Confermi il seguente svincolo?\n\n"
            f"  Squadra  : {nome_fq}\n"
            f"  FM totale accreditato: +{total_vs} FM\n\n"
            f"Giocatori svincolati (verranno eliminati dal DB):\n"
            + "\n".join(lines)
        )
        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Svincolo", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        #
        try:
            self.service.registra_svincolo(
                SvincoloCommand(
                    giocatore_ids=ids,
                    fq_id=fq_id,
                    data=data,
                    clausole=clausole,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire lo svincolo:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(self, "Successo", f"Svincolo completato. +{total_vs} FM accreditati a {nome_fq}.")

    #

    def _submit_asta(self):
        """
        Validate and commit a manual asta entry for one fantasquadra.
        Each AstaPlayerRow provides: nome, quotazione, spesa, data_acquisto.
        """
        fq_id = self.asta_club_combo.currentData()
        if fq_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la squadra."); return

        if not self._asta_rows:
            QMessageBox.warning(self, "Attenzione", "Aggiungi almeno un giocatore."); return

        # Collect and validate rows
        giocatori_data = []
        for i, row in enumerate(self._asta_rows, 1):
            d = row.get_data()
            if not d["nome"]:
                QMessageBox.warning(
                    self, "Attenzione",
                    f"Il giocatore alla riga {i} non ha un nome."
                ); return
            if d["quotazione"] == 0:
                QMessageBox.warning(
                    self, "Attenzione",
                    f"La quotazione del giocatore '{d['nome']}' e 0."
                ); return
            giocatori_data.append(d)

        # Read the single shared date from the form
        qd = self.data_edit.date()
        data_asta = datetime.date(qd.year(), qd.month(), qd.day())

        total_fm = sum(d["spesa"] for d in giocatori_data)
        extension_total = 0
        extension_lines = []
        data_norm = data_asta.replace(day=1)
        base_scadenza = contract_expiry_date(data_norm)
        for d in giocatori_data:
            if not d.get("estendi"):
                continue
            from types import SimpleNamespace
            preview_player = SimpleNamespace(
                valore_svincolo=d["spesa"],
                data_acquisto=data_norm,
                scadenza_contratto=base_scadenza,
            )
            try:
                costo, anni_extra, nuova_scadenza = self.repo.calcola_costo_aumento(preview_player)
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    "Aumento contratto non valido",
                    "Impossibile estendere il contratto di '" + d["nome"] + "':\n" + str(e),
                )
                return
            extension_total += costo
            extension_lines.append(
                "  + " + d["nome"] + " aumento: -" + str(costo) +
                " FM, +" + str(anni_extra) + " anni, scad. " +
                nuova_scadenza.strftime("%d/%m/%Y")
            )
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_fq = fqs.get(fq_id, str(fq_id))

        lines = [
            f"  - {d['nome']}  Q:{d['quotazione']}  FM:{d['spesa']}" +
            ("  + aumento contratto" if d.get("estendi") else "")
            for d in giocatori_data
        ]
        summary = (
            f"Confermi l'importazione asta per {nome_fq}?\n\n"
            f"Data asta: {data_asta.strftime('%d/%m/%Y')}\n"
            f"Giocatori: {len(giocatori_data)}\n"
            f"Totale FM asta: -{total_fm} FM\n"
            f"Totale aumento contratto: -{extension_total} FM\n"
            f"Totale complessivo: -{total_fm + extension_total} FM\n\n"
            + "\n".join(lines)
        )
        if extension_lines:
            summary += "\n\nAumenti contratto:\n" + "\n".join(extension_lines)

        reply = QMessageBox.question(
            self, "Conferma Asta", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.registra_asta_manuale(
                AstaManualeCommand(
                    fq_id=fq_id,
                    giocatori=[
                        AstaPlayerCommand(
                            nome=d["nome"],
                            quotazione=d["quotazione"],
                            spesa=d["spesa"],
                            estendi=d.get("estendi", False),
                        )
                        for d in giocatori_data
                    ],
                    data_asta=data_asta,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile registrare l'asta:\n{e}"); return

        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(
            self, "Successo",
            f"Asta registrata: {len(giocatori_data)} giocatori, -{total_fm + extension_total} FM da {nome_fq}."
        )

    #

    def _maybe_estendi_contratto(self, fq_id: int, giocatore_ids: list):
        """
        Run calcola_aumento_contratto for the given player IDs.
        Called only for players whose per-row estendi checkbox is checked.
        Shows a warning and returns False if FM is insufficient, True otherwise.
        """
        if not giocatore_ids:
            return True

        # Preview costs using fresh DB data
        gs = self.repo.active_giocatori()
        giocatori = [g for g in gs if g.id in set(giocatore_ids)]

        if not giocatori:
            return True

        total_costo = sum(
            self.repo.calcola_costo_aumento(g)[0] for g in giocatori
        )

        fqs = {fq.id: fq for fq in self.repo.active_fantasquadre()}
        fq  = fqs.get(fq_id)
        if fq and fq.fm < total_costo:
            QMessageBox.warning(
                self, "Estendi contratto",
                "FM insufficienti per l'estensione contratto.\n"
                "Disponibili: " + str(fq.fm) + " FM  -  Costo: " + str(total_costo) + " FM\n"
                "L'estensione non verra eseguita."
            )
            return False

        try:
            self.service.registra_aumento_contratto(
                AumentoContrattoCommand(
                    fq_id=fq_id,
                    giocatore_ids=giocatore_ids,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Estendi contratto",
                "Operazione principale OK, ma estensione contratto fallita:\n" + str(e)
            )
            return False

        return True

    #

    def _submit_aumento_contratto(self):
        """Validate and commit an aumento contratto operation."""
        fq_id = self.aumento_club_combo.currentData()
        if fq_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la squadra."); return

        rows = self._aumento_player_rows
        if not rows:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore."); return

        giocatore_ids = [r._giocatore_id for r in rows]
        total_costo   = sum(r._costo for r in rows)

        # FM check
        fqs = {fq.id: fq for fq in self.repo.active_fantasquadre()}
        fq  = fqs.get(fq_id)
        if fq and fq.fm < total_costo:
            QMessageBox.warning(
                self, "Attenzione",
                "FM insufficienti.\nDisponibili: " + str(fq.fm) +
                " FM  -  Costo totale: " + str(total_costo) + " FM"
            )
            return

        nome_fq = fq.nome if fq else str(fq_id)
        n = len(rows)

        # Build confirmation lines from row widgets
        lines_txt = []
        for r in rows:
            hl = r.layout()
            name_w = hl.itemAt(1).widget() if hl and hl.count() > 1 else None
            info_w = hl.itemAt(2).widget() if hl and hl.count() > 2 else None
            name_t = name_w.text() if name_w else str(r._giocatore_id)
            info_t = info_w.text() if info_w else ""
            lines_txt.append("  - " + name_t + "  " + info_t)

        msg = (
            "Confermi l'aumento contratto per " + nome_fq + "?\n\n"
            "Giocatori: " + str(n) + "\n"
            "Costo totale: -" + str(total_costo) + " FM\n\n"
            + "\n".join(lines_txt)
        )
        reply = QMessageBox.question(
            self, "Conferma Aumento Contratto", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.registra_aumento_contratto(
                AumentoContrattoCommand(
                    fq_id=fq_id,
                    giocatore_ids=giocatore_ids,
                    sessions_to_expire=self.sibling_repos,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore",
                "Impossibile registrare l'aumento contratto:\n" + str(e))
            return

        self._reset_form()
        self._refresh_history()
        self.operazione_committed.emit()
        QMessageBox.information(
            self, "Successo",
            "Aumento contratto registrato. -" + str(total_costo) + " FM da " + nome_fq + "."
        )

    #

    def _submit_generic(self, tipo, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """For operation types that don't yet have business-logic side effects."""
        all_ids = ids_a + ids_b
        conguaglio    = fm_a or fm_b
        cong_da_id    = fq_a_id if fm_a > 0 else (fq_b_id if fm_b > 0 else None)

        # Confirmation
        reply = QMessageBox.question(
            self, "Conferma operazione",
            f"Confermi di registrare l'operazione '{tipo}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.registra_operazione_generica(
                RegistraOperazioneCommand(
                    fantasquadra_a_id=fq_a_id,
                    tipo_operazione=tipo,
                    giocatore_ids=all_ids,
                    fantasquadra_b_id=fq_b_id,
                    conguaglio=conguaglio,
                    conguaglio_da_id=cong_da_id,
                    data=data,
                    clausole=clausole,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare:\n{e}"); return

        self._reset_form()
        self._refresh_history()

    def _reset_form(self):
        self.panel_a.reset()
        self.panel_b.reset()
        self._clear_asta_rows()
        self.asta_club_combo.setCurrentIndex(0)
        self._clear_aumento_rows()
        if hasattr(self, "aumento_club_combo"):
            self.aumento_club_combo.setCurrentIndex(0)
        self.tipo_combo.setCurrentIndex(0)
        self.data_edit.setDate(QDate.currentDate())
        self.clausole_edit.clear()


    #

    def _refresh_history(self):
        while self.cards_vbox.count() > 1:
            item = self.cards_vbox.takeAt(0)
            widget = item.widget() if item else None
            if widget is not None:
                widget.deleteLater()

        tipo_f = self.filter_combo.currentText()
        ops = self.repo.all()
        if tipo_f != "Tutte":
            ops = [o for o in ops if cast(bool,o.tipo_operazione) == tipo_f]

        if not ops:
            el = _lbl("Nessuna operazione registrata.", color=MUTED)
            el.setAlignment(Qt.AlignmentFlag.AlignCenter)
            el.setStyleSheet(f"color: {MUTED}; padding: 24px;")
            self.cards_vbox.insertWidget(0, el)
            return

        for op in ops:
            card = OperazioneCard(op)
            card.delete_requested.connect(self._delete_op)
            self.cards_vbox.insertWidget(self.cards_vbox.count() - 1, card)

    def _delete_op(self, op_id: int):
        if QMessageBox.question(
            self, "Conferma",
            "Eliminare questa operazione?\nL'azione non e reversibile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.repo.delete(op_id)
            self._refresh_history()
