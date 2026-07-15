from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from widgets.mercato.common import BORDER, CREAM, MUTED, NAVY, RED, TIPO_META, WHITE, _month_it

class OperazioneCard(QFrame):
    delete_requested = Signal(int)

    def __init__(self, op, parent=None):
        super().__init__(parent)
        self.op_id = op.id
        self._build(op)

    def _operation_snapshot(self, op) -> dict:
        raw = getattr(op, "operation_snapshot", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _snapshot_player_rows(self, snapshot: dict, preferred: str = "after") -> list:
        rows = []
        for item in snapshot.get("giocatori", []) or []:
            if not isinstance(item, dict):
                continue
            if not any(key in item for key in ("before", "after", "details")):
                rows.append(item)
                continue

            base = item.get(preferred) or item.get("after") or item.get("before") or {}
            details = item.get("details") or {}
            if not isinstance(base, dict):
                base = {}
            if not isinstance(details, dict):
                details = {}
            row = {**base, **details}
            row.setdefault("id", item.get("id"))
            row.setdefault("nome", item.get("nome"))
            rows.append(row)
        return rows

    def _build(self, op):
        badge_fg, badge_bg = TIPO_META.get(op.tipo_operazione, ("#333333", "#eee"))
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

        #
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

        if getattr(op, "periodo_regolamento", None):
            context_text = op.periodo_regolamento
            if getattr(op, "mese_regolamento", None):
                context_text += f" - {op.mese_regolamento}"
            context_lbl = QLabel(context_text)
            context_lbl.setStyleSheet(
                f"color: {badge_fg}; font-size: 10px; background: transparent;"
            )
            sr.addWidget(context_lbl)

        db = QPushButton("X")
        db.setFixedSize(20, 20)
        db.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {MUTED};
                border: none; font-size: 11px; }}
            QPushButton:hover {{ color: {RED}; }}
        """)
        db.clicked.connect(lambda: self.delete_requested.emit(self.op_id))
        sr.addWidget(db)
        outer.addWidget(strip)

        #
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        br = QHBoxLayout(body)
        br.setContentsMargins(12, 10, 12, 12)
        br.setSpacing(8)

        fq_a_name = op.fantasquadra_a.nome if op.fantasquadra_a else "-"
        fq_b_name = op.fantasquadra_b.nome if op.fantasquadra_b else None
        fm        = op.conguaglio or 0
        payer_id  = op.conguaglio_da_id

        is_svincolo       = (tipo == "svincolo")
        is_svincolo_fine  = (tipo == "svincolo fine contratto")
        is_prestito       = (tipo in ("prestito", "scambio prestiti"))
        is_scambio        = (tipo in ("scambio definitivo", "scambio prestiti"))
        is_acquisto       = (tipo == "acquisto definitivo")

        is_asta = (tipo == "asta")
        operation_snapshot = self._operation_snapshot(op)

        if is_svincolo:
            #
            snapshot_rows = self._snapshot_player_rows(operation_snapshot, preferred="before")
            col = self._svincolo_col(
                fq_a_name,
                snapshot_rows or op.giocatori,
                fm,
                from_snapshot=bool(snapshot_rows),
            )
            br.addWidget(col)
        elif is_svincolo_fine:
            snapshot_rows = self._snapshot_player_rows(operation_snapshot, preferred="before")
            col = self._svincolo_fine_contratto_col(
                fq_a_name,
                snapshot_rows or op.giocatori,
            )
            br.addWidget(col)
        elif is_asta:
            snapshot_rows = self._snapshot_player_rows(operation_snapshot, preferred="after")
            col = self._asta_col(fq_a_name, snapshot_rows or op.giocatori, fm)
            br.addWidget(col)
        elif tipo == "aumento contratto":
            snap = self._snapshot_player_rows(operation_snapshot, preferred="after")
            col = self._aumento_col(fq_a_name, snap, fm)
            br.addWidget(col)
        else:
            # Assign players to the side they LEFT from:
            #
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
                # acquisto / prestito: all players left fq_a
                left_a = list(op.giocatori)
                left_b = []

            #
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
                fq_name      = fq_b_name or "-",
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

        #
        if op.clausole and op.clausole.strip():
            foot = QWidget()
            foot.setStyleSheet(f"background: {CREAM}; border-radius: 0 0 4px 4px;")
            fl = QHBoxLayout(foot)
            fl.setContentsMargins(12, 4, 12, 6)
            cl = QLabel(f"Note: {op.clausole}")
            cl.setWordWrap(True)
            cl.setStyleSheet(f"color: {MUTED}; font-size: 10px; font-style: italic; background: transparent;")
            fl.addWidget(cl)
            outer.addWidget(foot)

    #

    def _lbl(self, text, bold=False, size=10, color="#333333", align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
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

        #
        for g in edited_leaving:
            v.addWidget(self._player_row_lbl(g, is_prestito, role="leaving", align=qa))

        # Thin separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        #
        for g in edited_arriving:
            v.addWidget(self._player_row_lbl(g, is_prestito, role="arriving", align=qa))

        # FM line
        if fm_signed != 0:
            sign = "-" if fm_signed < 0 else "+"
            color = RED if fm_signed < 0 else "#1a7a3a"
            fm_lbl = self._lbl(
                f"FM {sign}{abs(fm_signed)}",
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
            secondary_str = ""
            if is_arriving:
                fine = g.fine_prestito
                secondary = fine.strftime("%d/%m/%Y") if fine else "-"
                secondary_str = f"fino al {secondary}"
            sec_color = "#7a4f00" if is_arriving else MUTED
        else:
            vs = g.valore_svincolo
            secondary_str = ""
            if is_arriving:
                secondary_str = f"{int(vs) if vs is not None else '-'} FM"
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
        """Vertical centre column with the operation direction."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 0, 4, 0)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sym = "<->" if is_prestito else "->"
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

        total_lbl = QLabel(f"+{total} FM")
        f = total_lbl.font(); f.setBold(True); f.setPointSize(11)
        total_lbl.setFont(f)
        total_lbl.setStyleSheet("background: transparent; color: #1a7a3a;")
        v.addWidget(total_lbl)

        v.addStretch()
        return w

    def _svincolo_fine_contratto_col(self, fq_name: str, giocatori) -> QWidget:
        """Single-column layout for end-season expired contract releases."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        v.addWidget(self._lbl(fq_name, bold=True, size=11, color=NAVY))

        for g in giocatori:
            if isinstance(g, dict):
                nome = g.get("nome", "-")
                scadenza = g.get("scadenza_contratto")
            else:
                nome = g.nome
                scadenza = (
                    g.scadenza_contratto.isoformat()
                    if g.scadenza_contratto
                    else None
                )
            scadenza_text = self._format_iso_month(scadenza) if scadenza else "-"
            row_lbl = QLabel(
                f"<span style='font-size:10pt; font-weight:bold; color:#1a1a1a;'>{nome}</span>"
                f"  <span style='font-size:9pt; color:{MUTED};'>scad. {scadenza_text}</span>"
            )
            row_lbl.setTextFormat(Qt.TextFormat.RichText)
            row_lbl.setStyleSheet("background: transparent;")
            v.addWidget(row_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        total_lbl = QLabel("Nessun accredito FM")
        f = total_lbl.font(); f.setBold(True); f.setPointSize(11)
        total_lbl.setFont(f)
        total_lbl.setStyleSheet(f"background: transparent; color: {MUTED};")
        v.addWidget(total_lbl)

        v.addStretch()
        return w

    @staticmethod
    def _format_iso_month(value: str) -> str:
        try:
            import datetime as _dt
            d = _dt.date.fromisoformat(value)
        except Exception:
            return value
        months = ["gen","feb","mar","apr","mag","giu",
                  "lug","ago","set","ott","nov","dic"]
        return f"{months[d.month - 1]}-{str(d.year)[2:]}"


    def _asta_col(self, fq_name: str, giocatori, total_fm: int) -> QWidget:
        """Single-column layout for asta: player name + Q + FM per row, then total."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        v.addWidget(self._lbl(fq_name, bold=True, size=11, color=NAVY))

        computed_total = 0
        for g in giocatori:
            if isinstance(g, dict):
                nome = g.get("nome", "-")
                vs   = int(g.get("valore_svincolo") or 0)
                quot = int(g.get("quotazione") or 0)
            else:
                nome = g.nome
                vs   = int(g.valore_svincolo or 0)
                quot = int(g.quotazione or 0)
            computed_total += vs

            row_lbl = QLabel(
                f"<span style='font-size:10pt; font-weight:bold; color:#1a1a1a;'>{nome}</span>"
                f"  <span style='font-size:9pt; color:{MUTED};'>Q:{quot} - {vs} FM</span>"
            )
            row_lbl.setTextFormat(Qt.TextFormat.RichText)
            row_lbl.setStyleSheet("background: transparent;")
            v.addWidget(row_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        display_total = total_fm if total_fm else computed_total
        total_lbl = QLabel(f"-{display_total} FM")
        f = total_lbl.font(); f.setBold(True); f.setPointSize(11)
        total_lbl.setFont(f)
        total_lbl.setStyleSheet(f"background: transparent; color: {RED};")
        v.addWidget(total_lbl)

        v.addStretch()
        return w


    def _aumento_col(self, fq_name: str, snapshot: list, total_costo: int) -> QWidget:
        """Card body for aumento contratto: player + cost + new scadenza, then total."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)

        v.addWidget(self._lbl(fq_name, bold=True, size=11, color=NAVY))

        for row in snapshot:
            nome          = row.get("nome", "-")
            costo         = int(row.get("costo", 0))
            nuova_scad    = row.get("nuova_scadenza", "-")
            # Format nuova_scadenza to Italian short form if possible
            try:
                import datetime as _dt
                d = _dt.date.fromisoformat(nuova_scad)
                months = ["gen","feb","mar","apr","mag","giu",
                          "lug","ago","set","ott","nov","dic"]
                nuova_scad = f"{months[d.month-1]}-{str(d.year)[2:]}"
            except Exception:
                pass

            lbl = QLabel(
                f"<span style='font-size:10pt; font-weight:bold; color:#1a1a1a;'>{nome}</span>"
                f"  <span style='font-size:9pt; color:{MUTED};'>-{costo} FM - scad. {nuova_scad}</span>"
            )
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setStyleSheet("background: transparent;")
            v.addWidget(lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        v.addWidget(sep)

        total_lbl = QLabel(f"-{total_costo} FM")
        f = total_lbl.font(); f.setBold(True); f.setPointSize(11)
        total_lbl.setFont(f)
        total_lbl.setStyleSheet(f"background: transparent; color: {RED};")
        v.addWidget(total_lbl)

        v.addStretch()
        return w


#

