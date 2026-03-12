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

    Normal layout:   [name ──stretch──]  [Q spinbox]  [VS label]  [×]
    Prestito layout: [name ──stretch──]  [Q spinbox]  [VS label]  [fine prestito date]  [×]

    • quotazione is editable (QSpinBox)
    • valore_svincolo is read-only
    • fine_prestito date picker is shown only when show_fine_prestito=True
    • × removes the row
    """
    removed = Signal(int)   # giocatore_id

    def __init__(
        self,
        giocatore_id: int,
        name: str,
        quotazione: Optional[int],
        valore_svincolo: Optional[float],
        show_fine_prestito: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.giocatore_id = giocatore_id
        self._show_fine_prestito = show_fine_prestito

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
        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(f"color: {NAVY}; font-size: 12px; font-weight: bold; background: transparent;")
        row.addWidget(self._name_lbl, stretch=1)

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

        # Fine prestito date picker — only for prestito mode
        self.fine_prestito_edit: Optional[QDateEdit] = None
        if show_fine_prestito:
            fp_lbl = QLabel("fine:")
            fp_lbl.setStyleSheet("color: #c8960c; font-size: 10px; font-weight: bold; background: transparent;")
            fp_lbl.setFixedWidth(28)
            row.addWidget(fp_lbl)

            self.fine_prestito_edit = QDateEdit()
            self.fine_prestito_edit.setCalendarPopup(True)
            self.fine_prestito_edit.setDate(QDate.currentDate())
            self.fine_prestito_edit.setFixedWidth(95)
            self.fine_prestito_edit.setStyleSheet("""
                QDateEdit {
                    border: 1px solid #c8960c;
                    border-radius: 3px;
                    padding: 1px 4px;
                    background: #fff3cd;
                    font-size: 11px;
                    color: #7a4f00;
                    font-weight: bold;
                }
                QDateEdit::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 18px;
                    border-left: 1px solid #c8960c;
                    border-top-right-radius: 3px;
                    border-bottom-right-radius: 3px;
                    background: #f5d97a;
                }
                QDateEdit::down-arrow {
                    image: none;
                    width: 0;
                    height: 0;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 6px solid #7a4f00;
                }
            """)
            # Style the calendar popup explicitly — without this Qt renders
            # it with a black background that swallows most of the day numbers.
            cal = self.fine_prestito_edit.calendarWidget()
            cal.setStyleSheet("""
                QCalendarWidget {
                    background-color: #ffffff;
                    color: #1a1a1a;
                }
                /* Navigation bar (month/year + arrows) */
                QCalendarWidget QWidget#qt_calendar_navigationbar {
                    background-color: #fff3cd;
                    padding: 4px;
                }
                QCalendarWidget QToolButton {
                    color: #7a4f00;
                    background-color: transparent;
                    font-size: 12px;
                    font-weight: bold;
                    border: none;
                    padding: 2px 6px;
                }
                QCalendarWidget QToolButton:hover {
                    background-color: #f5d97a;
                    border-radius: 3px;
                }
                QCalendarWidget QToolButton::menu-indicator {
                    image: none;
                }
                QCalendarWidget QSpinBox {
                    color: #7a4f00;
                    background-color: #ffffff;
                    border: 1px solid #c8960c;
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 11px;
                }
                /* Day-of-week header row */
                QCalendarWidget QWidget { 
                    alternate-background-color: #fffbf0;
                }
                QCalendarWidget QAbstractItemView {
                    background-color: #ffffff;
                    color: #1a1a1a;
                    selection-background-color: #c8960c;
                    selection-color: #ffffff;
                    outline: none;
                    font-size: 11px;
                }
                QCalendarWidget QAbstractItemView:enabled {
                    color: #1a1a1a;
                    background-color: #ffffff;
                }
                QCalendarWidget QAbstractItemView:disabled {
                    color: #b0b0b0;
                }
            """)
            row.addWidget(self.fine_prestito_edit)

        # Remove button
        x = QToolButton()
        x.setText("×")
        x.setFixedSize(18, 18)
        font = x.font()
        font.setPointSize(10)
        x.setFont(font)
        x.setStyleSheet(f"""
            QToolButton {{
                color: {MUTED}; background: transparent;
                border: none; padding: 0;
            }}
            QToolButton:hover {{ color: {RED}; }}
        """)
        x.clicked.connect(lambda: self.removed.emit(self.giocatore_id))
        row.addWidget(x)

    def name(self) -> str:
        return self._name_lbl.text()

    def quotazione_value(self) -> Optional[int]:
        v = self.quotazione_spin.value()
        return v if v > 0 else None

    def fine_prestito_value(self) -> Optional[datetime.date]:
        """Returns the fine_prestito date, or None if not in prestito mode."""
        if self.fine_prestito_edit is None:
            return None
        qd = self.fine_prestito_edit.date()
        return datetime.date(qd.year(), qd.month(), qd.day())


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

    def player_data_prestito(self) -> List[tuple]:
        """Return [(giocatore_id, quotazione_override_or_None, fine_prestito_date_or_None), ...]"""
        return [(r.giocatore_id, r.quotazione_value(), r.fine_prestito_value()) for r in self._rows]

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
        self._fantasquadre: list = []          # kept for FM balance lookup
        self._show_fine_prestito: bool = False
        self._build()

    def set_fine_prestito_mode(self, enabled: bool):
        """Switch all existing rows and future rows to show/hide the fine prestito picker."""
        if self._show_fine_prestito == enabled:
            return
        self._show_fine_prestito = enabled
        # Rebuild existing rows in-place to add/remove the date picker
        # Simplest approach: remember current selections, clear, re-add
        existing = [
            (r.giocatore_id, r.name(), r.quotazione_value(),
             next((g.valore_svincolo for g in self._available_giocatori if g.id == r.giocatore_id), None))
            for r in self.player_list._rows
        ]
        self.player_list.clear()
        for gid, name, quot, vs in existing:
            row = PlayerRow(
                giocatore_id=gid,
                name=name,
                quotazione=quot,
                valore_svincolo=vs,
                show_fine_prestito=enabled,
            )
            row.removed.connect(self.player_list.remove_row)
            self.player_list.add_row(row)

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

        # Small hint label: shows available FM balance and any floor warning
        self.fm_hint_lbl = QLabel("")
        self.fm_hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px; background: transparent;")
        self.fm_hint_lbl.setVisible(False)
        root.addWidget(self.fm_hint_lbl)

    # ── Club combo handler ───────────────────────────────────────────────

    def _on_club_changed(self):
        club_id = self.club_combo.currentData()
        club_name = self.club_combo.currentText()
        has_club = club_id is not None and club_name not in ("", "— nessuna —")
        self.add_btn.setVisible(has_club)
        self.player_list.clear()
        self._available_giocatori = []
        self.club_changed_to.emit(club_name if has_club else "")
        self.fm_changed.emit()   # recalculate FM cap for new club

    # ── Public API ──────────────────────────────────────────────────────

    def set_fantasquadre(self, fqs: list, with_empty=False):
        self._fantasquadre = fqs
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

    def player_data_prestito(self) -> List[tuple]:
        """Return [(giocatore_id, quotazione_override_or_None, fine_prestito_or_None), ...]"""
        return self.player_list.player_data_prestito()

    def update_fm_hint(self, vs_floor: Optional[int] = None):
        """Update the small hint label below the FM spin.
        Shows available balance and, for cessione, the minimum required amount."""
        balance = self.fq_fm()
        if balance is None or not self.fm_spin.isEnabled():
            self.fm_hint_lbl.setVisible(False)
            return
        current = self.fm_spin.value()
        parts = [f"Disponibili: {balance} FM"]
        if vs_floor is not None and vs_floor > 0:
            parts.append(f"Minimo richiesto: {vs_floor} FM")
            if current > 0 and current < vs_floor:
                self.fm_hint_lbl.setStyleSheet("color: #b52a2a; font-size: 9px; background: transparent;")
            else:
                self.fm_hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px; background: transparent;")
        else:
            self.fm_hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px; background: transparent;")
        self.fm_hint_lbl.setText("  " + "  |  ".join(parts))
        self.fm_hint_lbl.setVisible(True)

    def fq_fm(self) -> Optional[int]:
        """Return the current FM balance of the selected fantasquadra, or None."""
        fq_id = self.club_id()
        if fq_id is None:
            return None
        for fq in self._fantasquadre:
            if fq.id == fq_id:
                return fq.fm
        return None

    def total_vs(self) -> float:
        """Sum of valore_svincolo of all players currently added to this panel."""
        total = 0.0
        for r in self.player_list._rows:
            g = next((g for g in self._available_giocatori if g.id == r.giocatore_id), None)
            total += (g.valore_svincolo or 0.0) if g else 0.0
        return total

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
            meta = {g.id: g for g in self._available_giocatori}
            for pid, name in dlg.picked():
                g = meta.get(pid)
                row = PlayerRow(
                    giocatore_id=pid,
                    name=name,
                    quotazione=g.quotazione if g else None,
                    valore_svincolo=g.valore_svincolo if g else None,
                    show_fine_prestito=self._show_fine_prestito,
                )
                row.removed.connect(self.player_list.remove_row)
                row.removed.connect(lambda _: self.fm_changed.emit())  # update VS floor
                self.player_list.add_row(row)
            self.fm_changed.emit()   # update VS floor after batch add


# ── Exchange card (storico) ──────────────────────────────────────────────────

class OperazioneCard(QFrame):
    delete_requested = Signal(int)

    def __init__(self, op, parent=None):
        super().__init__(parent)
        self.op_id = op.id
        self._build(op)

    def _build(self, op):
        badge_fg, badge_bg = TIPO_META.get(op.tipo_operazione, ("#333", "#eee"))
        tipo = op.tipo_operazione

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

        tl = QLabel(tipo.upper())
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

        # ── Body ─────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        br = QHBoxLayout(body)
        br.setContentsMargins(12, 10, 12, 12)
        br.setSpacing(8)

        fq_a_name = op.fantasquadra_a.nome if op.fantasquadra_a else "—"
        fq_b_name = op.fantasquadra_b.nome if op.fantasquadra_b else None
        fm        = op.conguaglio or 0
        payer_id  = op.conguaglio_da_id

        is_svincolo       = (tipo == "svincolo")
        is_prestito       = (tipo in ("prestito", "scambio prestiti"))
        is_scambio        = (tipo in ("scambio definitivo", "scambio prestiti"))
        is_cessione       = (tipo == "cessione definitiva")

        if is_svincolo:
            # Players are deleted from DB after svincolo — read from snapshot
            import json as _json
            snapshot = []
            if op.giocatori_snapshot:
                try:
                    snapshot = _json.loads(op.giocatori_snapshot)
                except Exception:
                    pass
            col = self._svincolo_col(fq_a_name, op.giocatori or snapshot, fm, from_snapshot=not op.giocatori)
            br.addWidget(col)
        else:
            # Assign players to the side they LEFT from:
            # - cessione/prestito: all players left fq_a → arrive at fq_b
            # - scambio: players whose current squadra == fq_b.nome left fq_a,
            #            players whose current squadra == fq_a.nome left fq_b
            if is_scambio and fq_b_name:
                left_a  = [g for g in op.giocatori
                           if (g.squadra == fq_b_name)
                           or (is_prestito and g.in_prestito_a == fq_b_name)]
                left_b  = [g for g in op.giocatori
                           if (g.squadra == fq_a_name)
                           or (is_prestito and g.in_prestito_a == fq_a_name)]
            else:
                # cessione / prestito: all players left fq_a
                left_a = list(op.giocatori)
                left_b = []

            # FM signs: payer gets −, receiver gets +
            fm_a = (-fm if payer_id == op.fantasquadra_a_id else
                    +fm if fm > 0 else 0)
            fm_b = (-fm if payer_id == op.fantasquadra_b_id else
                    +fm if fm > 0 else 0)

            left_col  = self._side_col(
                fq_name      = fq_a_name,
                leaving      = left_a,      # players leaving fq_a
                arriving     = left_b,      # players arriving at fq_a (from fq_b)
                fm_signed    = fm_a,
                badge_fg     = badge_fg,
                is_prestito  = is_prestito,
                align        = "left",
            )
            right_col = self._side_col(
                fq_name      = fq_b_name or "—",
                leaving      = left_b,      # players leaving fq_b
                arriving     = left_a,      # players arriving at fq_b (from fq_a)
                fm_signed    = fm_b,
                badge_fg     = badge_fg,
                is_prestito  = is_prestito,
                align        = "right",
            )

            br.addWidget(left_col, stretch=1)
            br.addWidget(self._arrow_sep(badge_fg, is_prestito), stretch=0)
            br.addWidget(right_col, stretch=1)

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

    # ── helpers ──────────────────────────────────────────────────────────

    def _lbl(self, text, bold=False, size=10, color="#333", align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
        l = QLabel(text)
        f = l.font()
        f.setBold(bold)
        f.setPointSize(size)
        l.setFont(f)
        l.setStyleSheet(f"color: {color}; background: transparent;")
        l.setAlignment(align)
        return l

    def _side_col(self, fq_name, leaving, arriving, fm_signed,
                  badge_fg, is_prestito, align) -> QWidget:
        """
        One side of the card.
        Top half:   players leaving this club  (smaller, muted VS/date)
        Thin sep
        Bottom half: players arriving at this club (bigger, green VS/date)
        FM line at the bottom with sign
        """
        qa = Qt.AlignmentFlag.AlignLeft if align == "left" else Qt.AlignmentFlag.AlignRight
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # Club name
        v.addWidget(self._lbl(fq_name, bold=True, size=11, color=NAVY, align=qa))
        edited_arriving = arriving
        edited_leaving = leaving        

        if len(arriving) == 0: 
            spacing_num = len(leaving)
            edited_arriving = []
            for i in range(spacing_num): edited_arriving.append(" ")
        if len(leaving) == 0:
            spacing_num = len(arriving)
            edited_leaving = []
            for i in range(spacing_num): edited_leaving.append(" ")

        # Top half — leaving players (old VS, smaller)
        for g in edited_leaving:
            v.addWidget(self._player_row_lbl(g, is_prestito, role="leaving", align=qa))

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        # Bottom half — arriving players (new VS, bigger)
        for g in edited_arriving:
            v.addWidget(self._player_row_lbl(g, is_prestito, role="arriving", align=qa))

        # FM line
        if fm_signed != 0:
            sign  = "−" if fm_signed < 0 else "+"
            color = RED if fm_signed < 0 else "#1a7a3a"
            fm_lbl = self._lbl(
                f"💰 {sign}{abs(fm_signed)} FM",
                bold=True, size=10, color=color, align=qa,
            )
            fm_lbl.setStyleSheet(f"color: {color}; background: transparent; font-weight: bold;")
            v.addWidget(fm_lbl)

        v.addStretch()
        return w

    def _player_row_lbl(self, g, is_prestito: bool, role: str, align) -> QLabel:
        """Single player line: name + secondary info (VS or loan date).
        'leaving' = smaller, muted.  'arriving' = bigger, coloured."""
        is_arriving = (role == "arriving")
        name_size   = 10
        name_bold = "font-weight: bold;" if is_arriving else ""

        if g == " ":
            return QLabel(f"<span>{g}</span>")

        if is_prestito:
            fine = g.fine_prestito
            secondary = fine.strftime("%d/%m/%Y") if fine else "—"
            secondary_str = f"fino al {secondary}"
            sec_color = "#7a4f00" if is_arriving else MUTED
        else:
            vs = g.valore_svincolo
            secondary_str = ""
            if is_arriving:
                secondary_str = f"{int(vs) if vs is not None else '—'} FM"
            sec_color = "#1a7a3a" if is_arriving else MUTED

        lbl = QLabel(
            f"<span style='font-size:{name_size}pt; {name_bold} color:#1a1a1a'>{g.nome}</span>"
            f"  <span style='color:{sec_color}; font-size:9pt'>{secondary_str}</span>"
        )
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setStyleSheet("background: transparent;")
        lbl.setAlignment(align)
        return lbl

    def _arrow_sep(self, badge_fg: str, is_prestito: bool) -> QWidget:
        """Vertical centre column: just the big ⇄ arrow."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 4, 0)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sym = "⇌" if is_prestito else "⇄"
        lbl = QLabel(sym)
        f = QFont(); f.setPointSize(18)
        lbl.setFont(f)
        lbl.setStyleSheet(f"color: {badge_fg}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(lbl)
        return w

    def _svincolo_col(self, fq_name: str, giocatori, fm: int, from_snapshot=False) -> QWidget:
        """Single-column layout for svincolo: name | VS per player, then total.
        giocatori can be ORM Giocatore objects or snapshot dicts."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        v.addWidget(self._lbl(fq_name, bold=True, size=11, color=NAVY))

        total = 0
        for g in giocatori:
            # Support both ORM objects and snapshot dicts
            nome = g["nome"] if isinstance(g, dict) else g.nome
            vs   = int((g["valore_svincolo"] or 0) if isinstance(g, dict) else (g.valore_svincolo or 0))
            total += vs
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            row_h.setSpacing(6)
            giocatore_lbl = QLabel(f"<span style='background: transparent; font-size: 10pt; font-weight: bold; color: #1a1a1a;'>{nome}</span>"
                              f"  <span style='background: transparent; font-size: 9pt; color: {MUTED};'>{vs} FM</span>")
            giocatore_lbl.setTextFormat(Qt.TextFormat.RichText)
            row_h.addWidget(giocatore_lbl, stretch=1)
            v.addWidget(row_w)

        # Thin separator before total
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        total_lbl = QLabel(f"💰 +{total} FM")
        f = total_lbl.font(); f.setBold(True); f.setPointSize(11)
        total_lbl.setFont(f)
        total_lbl.setStyleSheet("background: transparent; color: #1a7a3a;")
        v.addWidget(total_lbl)

        v.addStretch()
        return w


# ── Main widget ───────────────────────────────────────────────────────────────

class MercatoWidget(QWidget):

    # Emitted after a cessione is committed so MainWindow can refresh tables
    cessione_committed = Signal()

    def __init__(self, repo: OperazioneRepository, parent=None):
        super().__init__(parent)
        self.repo = repo
        # MainWindow populates this with persistent repo sessions so
        # calcola_cessione can expire them before writing (releases SQLite read locks)
        self.sibling_sessions: list = []
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
        is_svincolo  = (tipo == "svincolo")
        is_prestito  = (tipo == "prestito")
        is_scambio_p = (tipo == "scambio prestiti")
        self.panel_b.setVisible(not is_svincolo)
        self._vsep_widget.setVisible(not is_svincolo)
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
          3. Cessione floor: for cessione definitiva the FM must be ≥ sum of
             valore_svincolo of the players added by the buying panel.
        """
        a = self.panel_a.fm_spin.value()
        b = self.panel_b.fm_spin.value()
        tipo = self.tipo_combo.currentText()

        # ── Mutex: lock out the idle panel ──────────────────────────────
        if a > 0:
            self.panel_b.set_fm_enabled(False)
        elif b > 0:
            self.panel_a.set_fm_enabled(False)
        else:
            self.panel_a.set_fm_enabled(True)
            self.panel_b.set_fm_enabled(True)

        # ── Cap each panel's FM spin to the club's actual balance ────────
        for panel in (self.panel_a, self.panel_b):
            if not panel.fm_spin.isEnabled():
                panel.fm_hint_lbl.setVisible(False)
                continue
            balance = panel.fq_fm()
            if balance is None:
                panel.fm_spin.setMaximum(999999)
                panel.fm_hint_lbl.setVisible(False)
                continue

            # For cessione definitiva the buyer (the FM payer) must also cover
            # the total valore_svincolo of the players they are buying.
            # The buyer is the panel that has FM (no players in cessione).
            if tipo == "cessione definitiva":
                # In cessione: seller has players, buyer has FM.
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

    # ── Submit ────────────────────────────────────────────────────────────

    def _submit(self):
        tipo = self.tipo_combo.currentText()

        # ── Common field reads ───────────────────────────────────────────
        fq_a_id   = self.panel_a.club_id()
        fq_b_id   = self.panel_b.club_id() if tipo != "svincolo" else None
        ids_a     = self.panel_a.player_ids()
        ids_b     = self.panel_b.player_ids()
        fm_a      = self.panel_a.fm_value()
        fm_b      = self.panel_b.fm_value()
        qd        = self.data_edit.date()
        data      = datetime.date(qd.year(), qd.month(), qd.day())
        clausole  = self.clausole_edit.text().strip() or None

        # ── Shared basic validation ──────────────────────────────────────
        if fq_a_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra A."); return
        if tipo != "svincolo" and fq_b_id is None:
            QMessageBox.warning(self, "Attenzione", "Seleziona la Squadra B."); return
        if tipo != "svincolo" and fq_a_id == fq_b_id:
            QMessageBox.warning(self, "Attenzione", "Squadra A e B devono essere diverse."); return
        if not ids_a and not ids_b:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore."); return

        # ── Route by tipo ────────────────────────────────────────────────
        if tipo == "cessione definitiva":
            self._submit_cessione(
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

    # ── Cessione definitiva ───────────────────────────────────────────────

    def _submit_cessione(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate cessione-specific rules, show confirmation summary,
        then call repo.calcola_cessione().

        Rules:
          • Players must be on exactly ONE side (the seller's side).
          • FM must be on the OTHER side (the buyer's side).
          • FM must be > 0.
        """
        # ── Cessione-specific validation ─────────────────────────────────
        has_a = bool(ids_a)
        has_b = bool(ids_b)

        if has_a and has_b:
            QMessageBox.warning(
                self, "Attenzione",
                "Per una cessione definitiva i giocatori devono essere\n"
                "aggiunti solo da UNA delle due squadre (il venditore)."
            )
            return

        if fm_a > 0 and fm_b > 0:
            QMessageBox.warning(
                self, "Attenzione",
                "Solo la squadra acquirente può inserire un importo FM."
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
                f"Disponibili: {buyer_balance} FM  —  Richiesti: {fm} FM"
            )
            return

        # FM must cover total valore_svincolo of sold players
        vs_floor = int(seller_panel.total_vs())
        if vs_floor > 0 and fm < vs_floor:
            QMessageBox.warning(
                self, "Attenzione",
                f"L'importo FM ({fm}) è inferiore al valore di svincolo totale\n"
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
                "Uno o più giocatori hanno quotazione 0.\n"
                "Verifica le quotazioni nella lista prima di procedere."
            )
            return

        # ── Resolve names for confirmation dialog ────────────────────────
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_venditrice  = fqs.get(fq_venditrice_id, str(fq_venditrice_id))
        nome_acquirente  = fqs.get(fq_acquirente_id, str(fq_acquirente_id))

        # Build player summary lines
        tot_quot = sum(d["quotazione"] for d in giocatori_data)
        lines = []
        for d in giocatori_data:
            spesa_i = round(fm * d["quotazione"] / tot_quot, 2)
            # find name from form data
            nome = next(
                (name for pid, name in
                 (self.panel_a.player_data() if fq_venditrice_id == fq_a_id
                  else self.panel_b.player_data())
                 if pid == d["id"]),
                f"ID {d['id']}"
            )
            lines.append(
                f"  • {nome}  —  Q: {d['quotazione']}  →  Spesa: {spesa_i:.0f} FM"
            )

        data_norm = data.replace(day=1)
        if data_norm.month in (1, 2):
            scadenza = datetime.date(data_norm.year + 2, 7, 1)
        else:
            scadenza = datetime.date(data_norm.year + 3, 7, 1)

        summary = (
            f"Confermi la seguente cessione definitiva?\n\n"
            f"  Venditore :  {nome_venditrice}  (+{fm} FM)\n"
            f"  Acquirente:  {nome_acquirente}  (−{fm} FM)\n"
            f"  Data acquisto:  {data_norm.strftime('%d/%m/%Y')}\n"
            f"  Scadenza contratto:  {scadenza.strftime('%d/%m/%Y')}\n\n"
            f"Giocatori ceduti:\n"
            + "\n".join(lines)
        )

        if clausole:
            summary += f"\n\nClausole: {clausole}"

        reply = QMessageBox.question(
            self, "Conferma Cessione Definitiva", summary,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # ── Execute ──────────────────────────────────────────────────────
        try:
            self.repo.calcola_cessione(
                giocatori_data=giocatori_data,
                fq_venditrice_id=fq_venditrice_id,
                fq_acquirente_id=fq_acquirente_id,
                fm=fm,
                data_acquisto=data,
                clausole=clausole,
                sessions_to_expire=self.sibling_sessions,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire la cessione:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.cessione_committed.emit()
        QMessageBox.information(self, "Successo", "Cessione definitiva registrata correttamente.")

    # ── Scambio definitivo ────────────────────────────────────────────────

    def _submit_scambio(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate scambio-specific rules, show confirmation summary,
        then call repo.calcola_scambio().

        Rules:
          • Both sides must have at least one player.
          • FM is optional and can only be on one side (the payer).
          • FM payer = fq_b by convention (if fm_a > 0, we swap roles so
            the panel that paid always ends up as fq_b in the repo call).
        """
        # ── Validation ───────────────────────────────────────────────────
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
                "Solo una delle due squadre può inserire un conguaglio FM."
            ); return

        # ── Determine who pays FM (fq_b = payer by convention) ──────────
        if fm_a > 0:
            # Panel A pays → swap: treat A as the receiver, B as the payer
            fq_a_id_eff, fq_b_id_eff = fq_b_id, fq_a_id
            data_a_eff = self.panel_b.player_data()   # players from original B → go to original A
            data_b_eff = self.panel_a.player_data()   # players from original A → go to original B
            fm = fm_a
        else:
            fq_a_id_eff, fq_b_id_eff = fq_a_id, fq_b_id
            data_a_eff = self.panel_a.player_data()
            data_b_eff = self.panel_b.player_data()
            fm = fm_b  # may be 0 — that's fine

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
                "Uno o più giocatori hanno quotazione 0.\n"
                "Verifica le quotazioni nella lista prima di procedere."
            ); return

        # ── Resolve names for confirmation dialog ────────────────────────
        fqs = {fq.id: fq.nome for fq in self.repo.active_fantasquadre()}
        nome_a = fqs.get(fq_a_id_eff, str(fq_a_id_eff))
        nome_b = fqs.get(fq_b_id_eff, str(fq_b_id_eff))

        # Need valore_svincolo from DB for amount computation preview
        all_vs: dict = {}
        for glist in (
            self.repo.giocatori_by_squadra(nome_a),
            self.repo.giocatori_by_squadra(nome_b),
        ):
            for g in glist:
                all_vs[g.id] = g.valore_svincolo or 0.0

        amount_A = sum(all_vs.get(d["id"], 0.0) for d in giocatori_data_a)
        amount_B = sum(all_vs.get(d["id"], 0.0) for d in giocatori_data_b) + fm

        data_norm = data.replace(day=1)
        if data_norm.month in (1, 2):
            scadenza = datetime.date(data_norm.year + 2, 7, 1)
        else:
            scadenza = datetime.date(data_norm.year + 3, 7, 1)

        tot_quotA = sum(d["quotazione"] for d in giocatori_data_a)
        tot_quotB = sum(d["quotazione"] for d in giocatori_data_b)

        # Build id→name map from all rows currently in both panels
        name_map: dict = {}
        for panel in (self.panel_a, self.panel_b):
            for row in panel.player_list._rows:
                from PySide6.QtWidgets import QLabel
                labels = row.findChildren(QLabel)
                if labels:
                    name_map[row.giocatore_id] = labels[0].text()

        def _player_lines(gdata, amount_in, tot_quot, dest_nome):
            lines = []
            for d in gdata:
                spesa = round(amount_in * d["quotazione"] / tot_quot, 2) if tot_quot else 0.0
                name = name_map.get(d["id"], f"ID {d['id']}")
                lines.append(
                    f"  • {name}  Q:{d['quotazione']}  →  {dest_nome}  Spesa:{spesa:.0f} FM"
                )
            return lines

        lines_a = _player_lines(giocatori_data_a, amount_B, tot_quotA, nome_b)
        lines_b = _player_lines(giocatori_data_b, amount_A, tot_quotB, nome_a)

        summary = (
            f"Confermi il seguente scambio definitivo?\n\n"
            f"  {nome_a}  ←→  {nome_b}\n"
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

        # ── Execute ──────────────────────────────────────────────────────
        try:
            self.repo.calcola_scambio(
                giocatori_data_a=giocatori_data_a,
                giocatori_data_b=giocatori_data_b,
                fq_a_id=fq_a_id_eff,
                fq_b_id=fq_b_id_eff,
                fm=fm,
                data_acquisto=data,
                clausole=clausole,
                sessions_to_expire=self.sibling_sessions,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire lo scambio:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.cessione_committed.emit()   # reuse same signal — refreshes all tables
        QMessageBox.information(self, "Successo", "Scambio definitivo registrato correttamente.")

    # ── Prestito ──────────────────────────────────────────────────────────

    def _submit_prestito(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate prestito rules, show confirmation, then call repo.calcola_prestito().

        Rules:
          • Players must be on exactly ONE side (the lender, fq_a).
          • FM is optional (can be 0) and must be on the OTHER side (fq_b).
          • Each player in panel_a must have a fine_prestito date set.
        """
        # ── Validation ───────────────────────────────────────────────────
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
                self, "Attenzione", "Solo la squadra che riceve il prestito può inserire FM."
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
            # panel_b has the players, panel_a has the FM → already handled above
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

        # ── Resolve names for confirmation ───────────────────────────────
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
            lines.append(f"  • {name}  fine prestito: {fp}")

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

        # ── Execute ──────────────────────────────────────────────────────
        try:
            self.repo.calcola_prestito(
                giocatori_data=giocatori_data,
                fq_prestante_id=fq_prestante_id,
                fq_ricevente_id=fq_ricevente_id,
                fm=fm,
                inizio_prestito=data,
                clausole=clausole,
                sessions_to_expire=self.sibling_sessions,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile registrare il prestito:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.cessione_committed.emit()
        QMessageBox.information(self, "Successo", "Prestito registrato correttamente.")

    # ── Scambio prestiti ──────────────────────────────────────────────────

    def _submit_scambio_prestiti(self, fq_a_id, fq_b_id, ids_a, ids_b, fm_a, fm_b, data, clausole):
        """
        Validate scambio prestiti rules, show confirmation, then call
        repo.calcola_scambio_prestiti().

        Rules:
          • Both sides must have at least one player (each lends to the other).
          • FM is optional (can be 0) and on at most one side.
          • Every player on both sides needs a fine_prestito date.
        """
        # ── Validation ───────────────────────────────────────────────────
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
                self, "Attenzione", "Solo una delle due squadre può inserire un conguaglio FM."
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

        # ── Resolve names for confirmation ───────────────────────────────
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
                lines.append(f"  • {name}  fine prestito: {fp}  →  {dest}")
            return lines

        summary = (
            f"Confermi il seguente scambio prestiti?\n\n"
            f"  {nome_a}  ↔  {nome_b}\n"
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

        # ── Execute ──────────────────────────────────────────────────────
        try:
            self.repo.calcola_scambio_prestiti(
                giocatori_data_a=giocatori_data_a,
                giocatori_data_b=giocatori_data_b,
                fq_a_id=fq_a_id_eff,
                fq_b_id=fq_b_id_eff,
                fm=fm,
                inizio_prestito=data,
                clausole=clausole,
                sessions_to_expire=self.sibling_sessions,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile registrare lo scambio prestiti:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.cessione_committed.emit()
        QMessageBox.information(self, "Successo", "Scambio prestiti registrato correttamente.")

    # ── Svincolo ──────────────────────────────────────────────────────────

    def _submit_svincolo(self, fq_id, ids, data, clausole):
        """
        Sum valore_svincolo of all selected players, credit it to the
        fantasquadra's FM, then hard-delete the players from the DB.
        """
        if not ids:
            QMessageBox.warning(self, "Attenzione", "Seleziona almeno un giocatore da svincolare."); return

        # ── Resolve names & values for confirmation ───────────────────────
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
            (giocatori_db[pid].valore_svincolo or 0.0) for pid in ids if pid in giocatori_db
        )

        lines = []
        for pid in ids:
            name = name_map.get(pid, f"ID {pid}")
            vs   = giocatori_db[pid].valore_svincolo if pid in giocatori_db else 0.0
            lines.append(f"  • {name}  VS: {int(vs or 0)} FM")

        summary = (
            f"Confermi il seguente svincolo?\n\n"
            f"  Squadra  : {nome_fq}\n"
            f"  FM totale accreditato: +{int(total_vs)} FM\n\n"
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

        # ── Execute ──────────────────────────────────────────────────────
        try:
            self.repo.calcola_svincolo(
                giocatore_ids=ids,
                fq_id=fq_id,
                data=data,
                clausole=clausole,
                sessions_to_expire=self.sibling_sessions,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Impossibile eseguire lo svincolo:\n{e}")
            return

        self._reset_form()
        self._refresh_history()
        self.cessione_committed.emit()
        QMessageBox.information(self, "Successo", f"Svincolo completato. +{int(total_vs)} FM accreditati a {nome_fq}.")

    # ── Generic (non-cessione) submit ─────────────────────────────────────

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