"""
MercatoWidget — Mercato tab of Fantamanager.

Layout (vertical splitter)
──────────────────────────
TOP HALF  : operation form
  • full-width tipo dropdown
  • two-column panel: Squadra A (left) | Squadra B (right)
      each column: club dropdown → add-player button → player chips → FM box
  • FM mutual-exclusion: only one side can carry FM
  • bottom strip: data + clausole + submit (full width)

BOTTOM HALF : storico operazioni
  • each operation rendered as a visual "exchange card"
"""
from __future__ import annotations

import datetime
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QDateEdit, QSpinBox, QSplitter, QToolButton,
    QDialog, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont

from models import TIPI_OPERAZIONE
from operazione_repository import OperazioneRepository


# ── Palette ─────────────────────────────────────────────────────────────────
NAVY   = "#0f1f3d"
CREAM  = "#f5f0e8"
WHITE  = "#ffffff"
GOLD   = "#c9a84c"
MUTED  = "#8892a4"
BORDER = "#d0d7e3"
RED    = "#b52a2a"

TIPO_META: Dict[str, tuple] = {
    "cessione definitiva": ("#1a7a4a", "#d4edda"),
    "scambio definitivo":  ("#0d4f8a", "#d0e8ff"),
    "prestito":            ("#7a4f00", "#fff3cd"),
    "scambio prestiti":    ("#5a007a", "#f0d6ff"),
    "svincolo":            ("#8a1500", "#ffe0db"),
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _lbl(text: str, bold=False, size: int = 12, color: str = "#212529") -> QLabel:
    w = QLabel(text)
    f = QFont()
    f.setPointSize(size)
    f.setBold(bold)
    w.setFont(f)
    w.setStyleSheet(f"color: {color};")
    return w


def _hsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {BORDER};")
    return f


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet(f"color: {BORDER};")
    return f


def _month_it(m: int) -> str:
    return ["gen","feb","mar","apr","mag","giu","lug","ago","set","ott","nov","dic"][m - 1]


COMBO_STYLE = f"""
    QComboBox {{
        border: 1px solid {BORDER};
        border-radius: 5px;
        padding: 4px 8px;
        background: {WHITE};
        font-size: 12px;
        color: {NAVY};
        min-width: 140px;
    }}
    QComboBox QAbstractItemView {{
        background: {WHITE};
        selection-background-color: {NAVY};
        color: {NAVY};
    }}
"""

INPUT_STYLE = f"""
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
    background: {WHITE};
    font-size: 12px;
    color: {NAVY};
"""


# ── Player row (one added player in the list) ────────────────────────────────

class PlayerRow(QFrame):
    """
    A single horizontal row inside the added-players list.

    Layout:  [name ──stretch──]  [quotazione spinbox]  [svincolo label]  [×]

    • quotazione is editable (QSpinBox)
    • valore_svincolo is read-only
    • × removes the row
    """
    removed = Signal(int)   # giocatore_id

    def __init__(
        self,
        giocatore_id: int,
        name: str,
        quotazione: Optional[int],
        valore_svincolo: Optional[float],
        parent=None,
    ):
        super().__init__(parent)
        self.giocatore_id = giocatore_id

        self.setStyleSheet(f"""
            PlayerRow {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 5px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 6, 4)
        row.setSpacing(8)

        # Name — stretches to fill available width
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color: {NAVY}; font-size: 12px; font-weight: bold; background: transparent;")
        row.addWidget(name_lbl, stretch=1)

        # Quotazione label + editable spinbox
        q_lbl = QLabel("Q:")
        q_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        q_lbl.setFixedWidth(16)
        row.addWidget(q_lbl)

        self.quotazione_spin = QSpinBox()
        self.quotazione_spin.setRange(0, 9999)
        self.quotazione_spin.setValue(quotazione if quotazione is not None else 0)
        self.quotazione_spin.setSpecialValueText("—")
        self.quotazione_spin.setFixedWidth(62)
        self.quotazione_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER};
                border-radius: 3px;
                padding: 1px 4px;
                background: {CREAM};
                font-size: 11px;
                color: {NAVY};
            }}
        """)
        row.addWidget(self.quotazione_spin)

        # Valore svincolo label + read-only value
        vs_lbl = QLabel("VS:")
        vs_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        vs_lbl.setFixedWidth(22)
        row.addWidget(vs_lbl)

        svincolo_str = str(int(valore_svincolo)) if valore_svincolo is not None else "—"
        vs_val = QLabel(svincolo_str)
        vs_val.setFixedWidth(40)
        vs_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vs_val.setStyleSheet(f"color: {NAVY}; font-size: 11px; background: transparent;")
        row.addWidget(vs_val)

        # Remove button
        x = QToolButton()
        x.setText("×")
        x.setFixedSize(18, 18)
        x.setStyleSheet(f"""
            QToolButton {{
                color: {MUTED}; background: transparent;
                border: none; font-size: 14px; padding: 0;
            }}
            QToolButton:hover {{ color: {RED}; }}
        """)
        x.clicked.connect(lambda: self.removed.emit(self.giocatore_id))
        row.addWidget(x)

    def quotazione_value(self) -> Optional[int]:
        v = self.quotazione_spin.value()
        return v if v > 0 else None


# ── Vertical player list container ───────────────────────────────────────────

class PlayerList(QWidget):
    """Vertical list of PlayerRow widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[PlayerRow] = []
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(4)
        self._vbox.addStretch()

    def add_row(self, row: PlayerRow):
        # Insert before the trailing stretch
        self._rows.append(row)
        self._vbox.insertWidget(self._vbox.count() - 1, row)
        self.updateGeometry()

    def remove_row(self, gid: int):
        for r in self._rows:
            if r.giocatore_id == gid:
                self._rows.remove(r)
                self._vbox.removeWidget(r)
                r.deleteLater()
                self.updateGeometry()
                return

    def ids(self) -> List[int]:
        return [r.giocatore_id for r in self._rows]

    def player_data(self) -> List[tuple]:
        """Return [(giocatore_id, quotazione_override_or_None), ...]"""
        return [(r.giocatore_id, r.quotazione_value()) for r in self._rows]

    def clear(self):
        for r in self._rows:
            self._vbox.removeWidget(r)
            r.deleteLater()
        self._rows.clear()
        self.updateGeometry()


# ── Player picker dialog ──────────────────────────────────────────────────────

class PlayerPickerDialog(QDialog):
    """
    Multi-select player picker showing name + quotazione + valore_svincolo.
    `available` is a list of Giocatore objects (already filtered by squadra).
    """
    def __init__(self, available: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleziona giocatori")
        self.setMinimumWidth(400)
        self.setMinimumHeight(360)
        self._picked: List[tuple] = []  # [(id, name), ...]

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(_lbl("Seleziona uno o più giocatori:", size=11))

        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Giocatore", "Quotazione", "V. Svincolo"])
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setStyleSheet(f"""
            QTreeWidget {{
                border: 1px solid {BORDER};
                border-radius: 4px;
                font-size: 12px;
                alternate-background-color: #f8f9fa;
            }}
            QTreeWidget::item {{
                padding: 4px 6px;
            }}
            QTreeWidget::item:selected {{
                background: {NAVY};
                color: {WHITE};
            }}
            QHeaderView::section {{
                background: {CREAM};
                color: {NAVY};
                font-weight: bold;
                font-size: 11px;
                padding: 4px 6px;
                border: none;
                border-bottom: 1px solid {BORDER};
            }}
        """)

        for g in sorted(available, key=lambda x: x.nome):
            quotazione = str(g.quotazione) if g.quotazione is not None else "—"
            svincolo = str(int(g.valore_svincolo)) if g.valore_svincolo is not None else "—"
            item = QTreeWidgetItem([g.nome, quotazione, svincolo])
            item.setData(0, Qt.ItemDataRole.UserRole, g.id)
            # Right-align numeric columns
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignCenter)
            self._tree.addTopLevelItem(item)

        layout.addWidget(self._tree)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        self._picked = [
            (it.data(0, Qt.ItemDataRole.UserRole), it.text(0))
            for it in self._tree.selectedItems()
        ]
        self.accept()

    def picked(self) -> List[tuple]:
        return self._picked


# ── Club side panel ───────────────────────────────────────────────────────────

class ClubPanel(QWidget):
    fm_changed = Signal()
    club_changed_to = Signal(str)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._available_giocatori: list = []
        self._build()

    def _build(self):
        self.setStyleSheet(f"""
            ClubPanel {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        root.addWidget(_lbl(self._label, bold=True, size=11, color=NAVY))

        # Club dropdown
        self.club_combo = QComboBox()
        self.club_combo.setStyleSheet(COMBO_STYLE)
        self.club_combo.currentIndexChanged.connect(self._on_club_changed)
        root.addWidget(self.club_combo)

        # ── Player list (scrollable, vertical) ──
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setFixedHeight(120)
        self._list_scroll.setStyleSheet("background: transparent;")
        self.player_list = PlayerList()
        self._list_scroll.setWidget(self.player_list)
        root.addWidget(self._list_scroll)

        # ── Add player button — below the list, hidden until club selected ──
        self.add_btn = QPushButton("＋  Aggiungi giocatore")
        self.add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {CREAM};
                color: {NAVY};
                border: 1px dashed {NAVY}77;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background: {NAVY};
                color: {WHITE};
                border-style: solid;
            }}
        """)
        self.add_btn.setVisible(False)
        self.add_btn.clicked.connect(self._pick_players)
        root.addWidget(self.add_btn)

        # FM row
        fm_row = QHBoxLayout()
        fm_row.addWidget(_lbl("FM:", size=11, color=MUTED))
        self.fm_spin = QSpinBox()
        self.fm_spin.setRange(0, 999999)
        self.fm_spin.setSuffix(" FM")
        self.fm_spin.setSpecialValueText("—")
        self.fm_spin.setStyleSheet(INPUT_STYLE)
        self.fm_spin.valueChanged.connect(lambda _: self.fm_changed.emit())
        fm_row.addWidget(self.fm_spin)
        root.addLayout(fm_row)

    # ── Club combo handler ───────────────────────────────────────────────

    def _on_club_changed(self):
        club_id = self.club_combo.currentData()
        club_name = self.club_combo.currentText()
        has_club = club_id is not None and club_name not in ("", "— nessuna —")
        self.add_btn.setVisible(has_club)
        self.player_list.clear()
        self._available_giocatori = []
        self.club_changed_to.emit(club_name if has_club else "")

    # ── Public API ──────────────────────────────────────────────────────

    def set_fantasquadre(self, fqs: list, with_empty=False):
        self.club_combo.blockSignals(True)
        self.club_combo.clear()
        if with_empty:
            self.club_combo.addItem("— nessuna —", userData=None)
        for fq in fqs:
            self.club_combo.addItem(fq.nome, userData=fq.id)
        self.club_combo.blockSignals(False)
        self._on_club_changed()

    def set_giocatori_for_squadra(self, giocatori: list):
        self._available_giocatori = giocatori

    def club_id(self) -> Optional[int]:
        return self.club_combo.currentData()

    def player_ids(self) -> List[int]:
        return self.player_list.ids()

    def player_data(self) -> List[tuple]:
        """Return [(giocatore_id, quotazione_override_or_None), ...]"""
        return self.player_list.player_data()

    def fm_value(self) -> int:
        return self.fm_spin.value()

    def set_fm_enabled(self, enabled: bool):
        if not enabled:
            self.fm_spin.blockSignals(True)
            self.fm_spin.setValue(0)
            self.fm_spin.blockSignals(False)
        self.fm_spin.setEnabled(enabled)

    def reset(self):
        self.club_combo.setCurrentIndex(0)
        self.player_list.clear()
        self.fm_spin.blockSignals(True)
        self.fm_spin.setValue(0)
        self.fm_spin.blockSignals(False)
        self.fm_spin.setEnabled(True)
        self._available_giocatori = []
        self.add_btn.setVisible(False)

    # ── Picker ──────────────────────────────────────────────────────────

    def _pick_players(self):
        already = set(self.player_list.ids())
        avail = [g for g in self._available_giocatori if g.id not in already]
        if not avail:
            QMessageBox.information(self, "Info", "Nessun giocatore disponibile da aggiungere.")
            return
        dlg = PlayerPickerDialog(avail, self)
        if dlg.exec():
            # Build a lookup from the available list for quotazione/valore_svincolo
            meta = {g.id: g for g in self._available_giocatori}
            for pid, name in dlg.picked():
                g = meta.get(pid)
                row = PlayerRow(
                    giocatore_id=pid,
                    name=name,
                    quotazione=g.quotazione if g else None,
                    valore_svincolo=g.valore_svincolo if g else None,
                )
                row.removed.connect(self.player_list.remove_row)
                self.player_list.add_row(row)


# ── Exchange card (storico) ──────────────────────────────────────────────────

class OperazioneCard(QFrame):
    delete_requested = Signal(int)

    def __init__(self, op, parent=None):
        super().__init__(parent)
        self.op_id = op.id
        self._build(op)

    def _build(self, op):
        badge_fg, badge_bg = TIPO_META.get(op.tipo_operazione, ("#333", "#eee"))
        is_svincolo = op.tipo_operazione == "svincolo"

        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            OperazioneCard {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-left: 4px solid {badge_fg};
                border-radius: 6px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top strip ────────────────────────────────────────────────────
        strip = QWidget()
        strip.setStyleSheet(f"background: {badge_bg}; border-radius: 4px 4px 0 0;")
        sr = QHBoxLayout(strip)
        sr.setContentsMargins(12, 5, 10, 5)

        tl = QLabel(op.tipo_operazione.upper())
        tf = QFont(); tf.setBold(True); tf.setPointSize(9)
        tl.setFont(tf)
        tl.setStyleSheet(f"color: {badge_fg}; background: transparent;")
        sr.addWidget(tl)
        sr.addStretch()

        if op.data:
            dl = QLabel(f"{op.data.day} {_month_it(op.data.month)} {op.data.year}")
            dl.setStyleSheet(f"color: {badge_fg}99; font-size: 10px; background: transparent;")
            sr.addWidget(dl)

        db = QPushButton("✕")
        db.setFixedSize(20, 20)
        db.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {MUTED};
                border: none; font-size: 11px; }}
            QPushButton:hover {{ color: {RED}; }}
        """)
        db.clicked.connect(lambda: self.delete_requested.emit(self.op_id))
        sr.addWidget(db)
        outer.addWidget(strip)

        # ── Exchange body ─────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        br = QHBoxLayout(body)
        br.setContentsMargins(12, 10, 12, 12)
        br.setSpacing(0)

        # Determine which players go on which side
        fq_a_id = op.fantasquadra_a_id
        fq_b_id = op.fantasquadra_b_id

        # Players — all stored on the operation; we show them in the centre
        player_names = [g.nome for g in op.giocatori]

        # FM
        fm_a = op.conguaglio if (op.conguaglio and op.conguaglio_da_id == fq_a_id) else 0
        fm_b = op.conguaglio if (op.conguaglio and op.conguaglio_da_id == fq_b_id) else 0

        fq_a_name = op.fantasquadra_a.nome if op.fantasquadra_a else "—"
        fq_b_name = op.fantasquadra_b.nome if op.fantasquadra_b else None

        br.addWidget(self._club_col(fq_a_name, fm_a, "left"), stretch=3)
        br.addWidget(self._centre_col(player_names, is_svincolo), stretch=4)

        if fq_b_name and not is_svincolo:
            br.addWidget(self._club_col(fq_b_name, fm_b, "right"), stretch=3)
        else:
            br.addWidget(QWidget(), stretch=3)

        outer.addWidget(body)

        # ── Clausole ─────────────────────────────────────────────────────
        if op.clausole and op.clausole.strip():
            foot = QWidget()
            foot.setStyleSheet(f"background: {CREAM}; border-radius: 0 0 4px 4px;")
            fl = QHBoxLayout(foot)
            fl.setContentsMargins(12, 4, 12, 6)
            cl = QLabel(f"📋  {op.clausole}")
            cl.setWordWrap(True)
            cl.setStyleSheet(f"color: {MUTED}; font-size: 10px; font-style: italic; background: transparent;")
            fl.addWidget(cl)
            outer.addWidget(foot)

    def _club_col(self, name: str, fm: int, align: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        qa = Qt.AlignmentFlag.AlignLeft if align == "left" else Qt.AlignmentFlag.AlignRight

        nl = QLabel(name)
        nf = QFont(); nf.setBold(True); nf.setPointSize(12)
        nl.setFont(nf)
        nl.setAlignment(qa)
        nl.setStyleSheet(f"color: {NAVY};")
        v.addWidget(nl)

        if fm and fm > 0:
            fl = QLabel(f"💰 {fm} FM")
            fl.setAlignment(qa)
            fl.setStyleSheet(f"""
                color: {GOLD}; font-weight: bold; font-size: 11px;
                background: {NAVY}18; border-radius: 4px; padding: 2px 6px;
            """)
            v.addWidget(fl)

        v.addStretch()
        return w

    def _centre_col(self, players: List[str], is_svincolo: bool) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(8, 0, 8, 0)
        v.setSpacing(2)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Arrow
        arrow_lbl = QLabel("✗" if is_svincolo else "⇄")
        af = QFont(); af.setPointSize(16)
        arrow_lbl.setFont(af)
        arrow_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow_lbl.setStyleSheet(f"color: {MUTED};")
        v.addWidget(arrow_lbl)

        # Player names
        for p in players:
            pl = QLabel(f"• {p}")
            pl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pl.setStyleSheet(f"color: #333; font-size: 11px;")
            v.addWidget(pl)

        v.addStretch()
        return w


# ── Main widget ───────────────────────────────────────────────────────────────

class MercatoWidget(QWidget):

    def __init__(self, repo: OperazioneRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self._build_ui()
        self.refresh_combos()
        self._refresh_history()

    # ── Build ────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_storico())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter)

    # ── Form ─────────────────────────────────────────────────────────────

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
        self.tipo_combo.addItems(TIPI_OPERAZIONE)
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
        self.clausole_edit.setPlaceholderText("Eventuali clausole o note…")
        self.clausole_edit.setStyleSheet(INPUT_STYLE)
        cl_col.addWidget(self.clausole_edit)
        bottom.addLayout(cl_col, stretch=1)

        self.submit_btn = QPushButton("✅  Registra")
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

    # ── Storico ──────────────────────────────────────────────────────────

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

        self.scroll = QScrollArea() 
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent;")

        self.cards_w = QWidget()
        self.cards_w.setStyleSheet("background: transparent;")
        self.cards_vbox = QVBoxLayout(self.cards_w)
        self.cards_vbox.setContentsMargins(0, 0, 4, 0)
        self.cards_vbox.setSpacing(8)
        self.cards_vbox.addStretch()

        self.scroll.setWidget(self.cards_w)
        layout.addWidget(self.scroll)
        return w

    # ── Populate ─────────────────────────────────────────────────────────

    def refresh_combos(self):
        fqs = self.repo.active_fantasquadre()
        self.panel_a.set_fantasquadre(fqs, with_empty=True)
        self.panel_b.set_fantasquadre(fqs, with_empty=True)
        self._on_tipo_changed(self.tipo_combo.currentText())

    def _load_players_for_panel(self, panel: ClubPanel, squadra_nome: str):
        """Fetch players for the selected squadra and hand them to the panel."""
        if not squadra_nome:
            panel.set_giocatori_for_squadra([])
            return
        giocatori = self.repo.giocatori_by_squadra(squadra_nome)
        panel.set_giocatori_for_squadra(giocatori)

    # ── Reactive ──────────────────────────────────────────────────────────

    def _on_tipo_changed(self, tipo: str):
        is_svincolo = (tipo == "svincolo")
        self.panel_b.setVisible(not is_svincolo)
        self._vsep_widget.setVisible(not is_svincolo)

    def _on_fm_mutex(self):
        a = self.panel_a.fm_spin.value()
        b = self.panel_b.fm_spin.value()
        if a > 0:
            self.panel_b.set_fm_enabled(False)
        elif b > 0:
            self.panel_a.set_fm_enabled(False)
        else:
            self.panel_a.set_fm_enabled(True)
            self.panel_b.set_fm_enabled(True)

    # ── Submit ────────────────────────────────────────────────────────────

    def _submit(self):
        tipo = self.tipo_combo.currentText()
        fq_a_id = self.panel_a.club_id()
        fq_b_id = self.panel_b.club_id() if tipo != "svincolo" else None

        if fq_a_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra A."); return
        if tipo != "svincolo" and fq_b_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra B."); return
        if tipo != "svincolo" and fq_a_id == fq_b_id:
            QMessageBox.warning(self, "Attenzione", "Squadra A e B devono essere diverse."); return

        all_ids = self.panel_a.player_ids() + self.panel_b.player_ids()
        if not all_ids:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore."); return

        fm_a = self.panel_a.fm_value()
        fm_b = self.panel_b.fm_value()
        conguaglio = fm_a or fm_b
        cong_da_id = fq_a_id if fm_a > 0 else (fq_b_id if fm_b > 0 else None)

        qd = self.data_edit.date()
        data = datetime.date(qd.year(), qd.month(), qd.day())
        clausole = self.clausole_edit.text().strip() or None

        try:
            self.repo.create(
                fantasquadra_a_id=fq_a_id,
                tipo_operazione=tipo,
                giocatore_ids=all_ids,
                fantasquadra_b_id=fq_b_id,
                conguaglio=conguaglio,
                conguaglio_da_id=cong_da_id,
                data=data,
                clausole=clausole,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile salvare:\n{e}"); return

        self._reset_form()
        self._refresh_history()

    def _reset_form(self):
        self.panel_a.reset()
        self.panel_b.reset()
        self.tipo_combo.setCurrentIndex(0)
        self.data_edit.setDate(QDate.currentDate())
        self.clausole_edit.clear()

    # ── History ───────────────────────────────────────────────────────────

    def _refresh_history(self):
        while self.cards_vbox.count() > 1:
            item = self.cards_vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tipo_f = self.filter_combo.currentText()
        ops = self.repo.all()
        if tipo_f != "Tutte":
            ops = [o for o in ops if o.tipo_operazione == tipo_f]

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
            "Eliminare questa operazione?\nL'azione non è reversibile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.repo.delete(op_id)
            self._refresh_history()