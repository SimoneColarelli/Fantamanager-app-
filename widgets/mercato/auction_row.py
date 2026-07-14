from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QSpinBox,
    QToolButton,
)
from PySide6.QtGui import QFont

from widgets.mercato.common import BORDER, CREAM, MUTED, NAVY, RED, WHITE, INPUT_STYLE

class AstaPlayerRow(QFrame):
    """
    A single row for manually entering one auction purchase.
    Layout: [extend checkbox] [name] [Q spinbox] [FM spinbox].
    Date is shared for the whole asta operation (from the form's data_edit).
    """
    removed = Signal()

    def __init__(self, show_estendi: bool = False, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            AstaPlayerRow {{
                background: {WHITE};
                border: 1px solid {BORDER};
                border-radius: 5px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(6)

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
        f = x.font(); f.setPointSize(10); x.setFont(f)
        x.setStyleSheet(f"""
            QToolButton {{ color: {MUTED}; background: transparent; border: none; padding: 0; }}
            QToolButton:hover {{ color: {RED}; }}
        """)
        x.clicked.connect(self.removed.emit)
        row.addWidget(x)

        # Name
        self.nome_edit = QLineEdit()
        self.nome_edit.setPlaceholderText("Nome giocatore...")
        self.nome_edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {BORDER}; border-radius: 3px;
                padding: 2px 5px; background: {WHITE};
                font-size: 11px; color: {NAVY};
            }}
        """)
        row.addWidget(self.nome_edit, stretch=1)

        # Quotazione
        q_lbl = QLabel("Q:")
        q_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        q_lbl.setFixedWidth(16)
        row.addWidget(q_lbl)

        self.quot_spin = QSpinBox()
        self.quot_spin.setRange(0, 9999)
        self.quot_spin.setSpecialValueText("-")
        self.quot_spin.setFixedWidth(58)
        self.quot_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER}; border-radius: 3px;
                padding: 1px 4px; background: {CREAM};
                font-size: 11px; color: {NAVY};
            }}
        """)
        row.addWidget(self.quot_spin)

        # FM paid
        fm_lbl = QLabel("FM:")
        fm_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")
        fm_lbl.setFixedWidth(22)
        row.addWidget(fm_lbl)

        self.fm_spin = QSpinBox()
        self.fm_spin.setRange(1, 999999)
        self.fm_spin.setValue(1)
        self.fm_spin.setFixedWidth(68)
        self.fm_spin.setStyleSheet(f"""
            QSpinBox {{
                border: 1px solid {BORDER}; border-radius: 3px;
                padding: 1px 4px; background: {CREAM};
                font-size: 11px; color: {NAVY};
            }}
        """)
        row.addWidget(self.fm_spin)

    def get_data(self) -> dict:
        """Return dict with nome, quotazione, spesa (date is handled at operation level)."""
        return {
            "nome":       self.nome_edit.text().strip(),
            "quotazione": self.quot_spin.value(),
            "spesa":      self.fm_spin.value(),
            "estendi":    self.estendi_cb.isChecked(),
        }

#

