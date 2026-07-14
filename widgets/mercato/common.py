from __future__ import annotations

import datetime
import json
from typing import Dict, List, Optional

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

NAVY   = "#0f1f3d"
CREAM  = "#f5f0e8"
WHITE  = "#ffffff"
GOLD   = "#c9a84c"
MUTED  = "#8892a4"
BORDER = "#d0d7e3"
RED    = "#b52a2a"

TIPO_META: Dict[str, tuple] = {
    "acquisto definitivo": ("#1a7a4a", "#d4edda"),
    "scambio definitivo":  ("#0d4f8a", "#d0e8ff"),
    "prestito":            ("#7a4f00", "#fff3cd"),
    "scambio prestiti":    ("#5a007a", "#f0d6ff"),
    "svincolo":            ("#8a1500", "#ffe0db"),
    "asta":               ("#1a4a7a", "#d0e8ff"),
    "aumento contratto":  ("#6a3d00", "#ffe8c0"),
}


#

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


#

