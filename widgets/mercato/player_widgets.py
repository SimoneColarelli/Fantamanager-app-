from __future__ import annotations

import datetime
from typing import List, Optional

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

from widgets.mercato.common import (
    BORDER,
    COMBO_STYLE,
    CREAM,
    INPUT_STYLE,
    MUTED,
    NAVY,
    RED,
    WHITE,
    _lbl,
)

class PlayerRow(QFrame):
    """
    A single horizontal row inside the added-players list.

    Normal layout: [name] [Q spinbox] [VS label] [remove].
    Prestito layout also shows the fine prestito date picker.
    """
    removed = Signal(int)   # giocatore_id

    def __init__(
        self,
        giocatore_id: int,
        name: str,
        quotazione: Optional[int],
        valore_svincolo: Optional[int],
        show_fine_prestito: bool = False,
        show_estendi: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.giocatore_id = giocatore_id
        self._show_fine_prestito = show_fine_prestito
        self._show_estendi = show_estendi

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

        # Name stretches to fill available width
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
        self.quotazione_spin.setSpecialValueText("-")
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

        svincolo_str = str(int(valore_svincolo)) if valore_svincolo is not None else "-"
        vs_val = QLabel(svincolo_str)
        vs_val.setFixedWidth(40)
        vs_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vs_val.setStyleSheet(f"color: {NAVY}; font-size: 11px; background: transparent;")
        row.addWidget(vs_val)

        #
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
            #
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

        #
        self.estendi_cb = QCheckBox()
        self.estendi_cb.setText("+")
        self.estendi_cb.setToolTip("Estendi contratto")
        self.estendi_cb.setStyleSheet(
            "QCheckBox { color: #6a3d00; font-size: 10px; font-weight: bold; background: transparent; }"
        )
        self.estendi_cb.setVisible(show_estendi)
        row.addWidget(self.estendi_cb)

        # Remove button
        x = QToolButton()
        x.setText("x")
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

    def estendi_value(self) -> bool:
        """Returns True if the estendi contratto checkbox is checked."""
        return self._show_estendi and self.estendi_cb.isChecked()


#

class PlayerList(QWidget):
    """Vertical list of PlayerRow widgets."""

    def __init__(self, show_estendi: bool = False, parent=None):
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


#

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
        layout.addWidget(_lbl("Seleziona uno o piu giocatori:", size=11))

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
            quotazione = str(g.quotazione) if g.quotazione is not None else "-"
            svincolo = str(int(g.valore_svincolo)) if g.valore_svincolo is not None else "-"
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


#

class ClubPanel(QWidget):
    fm_changed = Signal()
    club_changed_to = Signal(str)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._available_giocatori: list = []
        self._fantasquadre: list = []          # kept for FM balance lookup
        self._show_fine_prestito: bool = False
        self._show_estendi: bool = False
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
                show_estendi=self._show_estendi,
            )
            row.removed.connect(self.player_list.remove_row)
            self.player_list.add_row(row)

    def set_estendi_mode(self, enabled: bool):
        """Show/hide the estendi contratto checkbox on all existing and future rows."""
        if self._show_estendi == enabled:
            return
        self._show_estendi = enabled
        for r in self.player_list._rows:
            r.estendi_cb.setVisible(enabled)
            if not enabled:
                r.estendi_cb.setChecked(False)

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

        #
        self._list_scroll = QScrollArea()
        self._list_scroll.setWidgetResizable(True)
        self._list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_scroll.setFixedHeight(120)
        self._list_scroll.setStyleSheet("background: transparent;")
        self.player_list = PlayerList()
        self._list_scroll.setWidget(self.player_list)
        root.addWidget(self._list_scroll)

        #
        self.add_btn = QPushButton("+  Aggiungi giocatore")
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
        self.fm_spin.setSpecialValueText("-")
        self.fm_spin.setStyleSheet(INPUT_STYLE)
        self.fm_spin.valueChanged.connect(lambda _: self.fm_changed.emit())
        fm_row.addWidget(self.fm_spin)
        root.addLayout(fm_row)

        # Small hint label: shows available FM balance and any floor warning
        self.fm_hint_lbl = QLabel("")
        self.fm_hint_lbl.setStyleSheet(f"color: {MUTED}; font-size: 9px; background: transparent;")
        self.fm_hint_lbl.setVisible(False)
        root.addWidget(self.fm_hint_lbl)

    #

    def _on_club_changed(self):
        club_id = self.club_combo.currentData()
        club_name = self.club_combo.currentText()
        has_club = club_id is not None and club_name not in ("", "- nessuna -")
        self.add_btn.setVisible(has_club)
        self.player_list.clear()
        self._available_giocatori = []
        self.club_changed_to.emit(club_name if has_club else "")
        self.fm_changed.emit()   # recalculate FM cap for new club

    #

    def set_fantasquadre(self, fqs: list, with_empty=False):
        self._fantasquadre = fqs
        self.club_combo.blockSignals(True)
        self.club_combo.clear()
        if with_empty:
            self.club_combo.addItem("- nessuna -", userData=None)
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
        Shows available balance and, for acquisto, the minimum required amount."""
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

    def total_vs(self) -> int:
        """Sum of valore_svincolo of all players currently added to this panel."""
        total = 0
        for r in self.player_list._rows:
            g = next((g for g in self._available_giocatori if g.id == r.giocatore_id), None)
            total += int(g.valore_svincolo or 0) if g else 0
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

    #

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
                    show_estendi=self._show_estendi,
                )
                row.removed.connect(self.player_list.remove_row)
                row.removed.connect(lambda _: self.fm_changed.emit())  # update VS floor
                self.player_list.add_row(row)
            self.fm_changed.emit()   # update VS floor after batch add



#

