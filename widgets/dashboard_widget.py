from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.dashboard_service import DashboardData, DashboardService
from widgets.mercato.common import BORDER, CREAM, MUTED, NAVY, RED, WHITE


BOX_STYLE = (
    f"QFrame#dashboardBox {{ "
    f"background-color: {WHITE}; "
    f"border-color: {BORDER}; "
    "border-style: solid; "
    "border-width: 1px; "
    "border-radius: 6px; "
    "}"
)

REFRESH_BUTTON_STYLE = (
    f"background-color: {NAVY}; "
    f"color: {WHITE}; "
    "border-width: 0px; "
    "border-radius: 5px; "
    "font-weight: bold;"
)


def _fmt_date(value: dt.date | None) -> str:
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y")


def _label(text: str, *, size: int = 10, bold: bool = False, color: str = NAVY) -> QLabel:
    label = QLabel(text)
    font = QFont()
    font.setPointSize(size)
    font.setBold(bold)
    label.setFont(font)
    label.setStyleSheet(f"color: {color}; background-color: transparent;")
    label.setWordWrap(True)
    return label


def _framed_box() -> QFrame:
    box = QFrame()
    box.setObjectName("dashboardBox")
    box.setFrameShape(QFrame.Shape.NoFrame)
    box.setStyleSheet(BOX_STYLE)
    return box


def _plain_box() -> QFrame:
    box = QFrame()
    box.setFrameShape(QFrame.Shape.NoFrame)
    box.setStyleSheet("background-color: transparent;")
    return box


class DashboardWidget(QWidget):
    def __init__(self, service: DashboardService, parent=None):
        super().__init__(parent)
        self.service = service
        self._data: DashboardData | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.setStyleSheet(f"background-color: {CREAM};")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = _label("Dashboard Lega", size=18, bold=True, color=NAVY)
        header.addWidget(title)
        header.addStretch()
        refresh_btn = QPushButton("Aggiorna")
        refresh_btn.setFixedHeight(30)
        refresh_btn.setMinimumWidth(90)
        refresh_btn.setStyleSheet(REFRESH_BUTTON_STYLE)
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(12)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setStyleSheet("background-color: transparent;")
        left = QWidget()
        left.setStyleSheet("background-color: transparent;")
        self.left_layout = QVBoxLayout(left)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(12)
        left_scroll.setWidget(left)
        content.addWidget(left_scroll, stretch=4)

        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        side_scroll.setStyleSheet("background-color: transparent;")
        side = QWidget()
        side.setStyleSheet("background-color: transparent;")
        self.side_layout = QVBoxLayout(side)
        self.side_layout.setContentsMargins(0, 0, 0, 0)
        self.side_layout.setSpacing(10)
        self.side_layout.addStretch()
        side_scroll.setWidget(side)
        side_scroll.setMinimumWidth(260)
        side_scroll.setMaximumWidth(330)
        content.addWidget(side_scroll, stretch=1)

        root.addLayout(content, stretch=1)

    def refresh(self):
        self._data = self.service.load_dashboard()
        self._render()

    def _clear_layout(self, layout: QVBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

    def _render(self):
        if not self._data:
            return
        self._clear_layout(self.left_layout)
        self._clear_layout(self.side_layout)

        self.left_layout.addWidget(self._section_title("Fantasquadre"))
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        for index, team in enumerate(self._data.teams):
            grid.addWidget(self._team_card(team), index // 2, index % 2)
        self.left_layout.addLayout(grid)

        self.left_layout.addWidget(self._section_title("Prestiti attivi"))
        self.left_layout.addWidget(self._loan_list())

        self.left_layout.addWidget(self._section_title("Contratti in scadenza entro 1 anno"))
        self.left_layout.addWidget(self._expiration_columns())
        self.left_layout.addStretch()

        self.side_layout.addWidget(self._side_totals())
        self.side_layout.addWidget(self._ranking_box("Top FM", self._data.top_fm, "fm"))
        self.side_layout.addWidget(
            self._ranking_box("Top patrimoni", self._data.top_patrimonio, "patrimonio")
        )
        self.side_layout.addWidget(
            self._ranking_box("Top valore rosa", self._data.top_valore_rosa, "valore_rosa")
        )
        self.side_layout.addStretch()

    def _section_title(self, text: str) -> QLabel:
        label = _label(text, size=13, bold=True, color=NAVY)
        label.setContentsMargins(2, 0, 0, 0)
        return label

    def _team_card(self, team) -> QFrame:
        card = _framed_box()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        name = _label(team.nome, size=13, bold=True, color=NAVY)
        layout.addWidget(name)

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(8)
        metrics.setVerticalSpacing(6)
        values = [
            ("FM", team.fm),
            ("Valore rosa", team.valore_rosa),
            ("Patrimonio", team.patrimonio),
            ("Rosa", f"{team.in_rosa}/{team.convocati} conv."),
        ]
        for idx, (label, value) in enumerate(values):
            metrics.addWidget(_label(label, size=9, color=MUTED), idx // 2 * 2, idx % 2)
            metrics.addWidget(
                _label(str(value), size=12, bold=True, color=NAVY),
                idx // 2 * 2 + 1,
                idx % 2,
            )
        layout.addLayout(metrics)
        return card

    def _list_box(self) -> QFrame:
        box = _framed_box()
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        return box

    def _loan_list(self) -> QFrame:
        box = _plain_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if not self._data.loans:
            empty = self._list_box()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(10, 8, 10, 8)
            empty_layout.addWidget(_label("Nessun prestito attivo", color=MUTED))
            layout.addWidget(empty)
            return box
        for loan in self._data.loans:
            layout.addWidget(self._loan_row(loan))
        return box

    def _loan_row(self, loan) -> QFrame:
        row = _framed_box()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        layout.addWidget(_label(loan.giocatore, size=10, bold=True, color=NAVY))
        layout.addWidget(
            _label(
                f"{loan.from_team} -> {loan.to_team} | "
                f"{_fmt_date(loan.inizio)} - {_fmt_date(loan.fine)}",
                size=9,
                color=MUTED,
            )
        )
        return row

    def _expiration_columns(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")
        scroll.setMinimumHeight(170)

        wrapper = QWidget()
        wrapper.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        for group in self._data.expiring_contract_groups:
            layout.addWidget(self._expiration_team_column(group))
        layout.addStretch()

        scroll.setWidget(wrapper)
        return scroll

    def _expiration_team_column(self, group) -> QFrame:
        column = self._list_box()
        column.setMinimumWidth(170)
        column.setMaximumWidth(220)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(_label(group.fantasquadra, size=11, bold=True, color=NAVY))

        if not group.contracts:
            layout.addWidget(_label("Nessuna scadenza", size=9, color=MUTED))
            layout.addStretch()
            return column

        for item in group.contracts:
            row = _label(
                f"{_fmt_date(item.scadenza)}\n{item.giocatore}",
                size=10,
                color=RED,
            )
            layout.addWidget(row)
        layout.addStretch()
        return column

    def _side_totals(self) -> QFrame:
        box = self._list_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(_label("Totali lega", size=12, bold=True, color=NAVY))
        totals = self._data.totals
        rows = [
            ("FM", totals.fm),
            ("Valore rose", totals.valore_rose),
            ("Patrimonio", totals.patrimonio),
            ("Giocatori attivi", totals.giocatori_attivi),
            ("Prestiti attivi", totals.prestiti_attivi),
            ("Scadenze entro 1 anno", totals.contratti_in_scadenza),
        ]
        for label, value in rows:
            layout.addWidget(_label(f"{label}: {value}", size=10, color=NAVY))
        return box

    def _ranking_box(self, title: str, teams: list, attr: str) -> QFrame:
        box = self._list_box()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        layout.addWidget(_label(title, size=12, bold=True, color=NAVY))
        for idx, team in enumerate(teams, start=1):
            layout.addWidget(
                _label(f"{idx}. {team.nome}: {getattr(team, attr)}", size=10, color=NAVY)
            )
        return box
