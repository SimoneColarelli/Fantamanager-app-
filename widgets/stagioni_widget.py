from __future__ import annotations

import datetime as dt

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.backup_service import BackupService, SEASONAL_BACKUPS
from services.mercato_commands import SvincoloFineContrattoCommand
from services.mercato_service import MercatoService
from services.quotazioni_service import QuotazioniService
from services.stagione_service import (
    ActiveStagioneExistsError,
    CreateStagioneCommand,
    StagioneDTO,
    StagioneFaseDTO,
    StagioneService,
    UpdateStagioneDatesCommand,
    UpdateStagioneFaseCommand,
    build_stagione_code,
)


PHASE_BACKUP_KEYS = {
    "fase_1_estiva": (
        "inizio_stagione",
        "pre_asta_estiva",
        "post_asta_estiva",
        "chiusura_sessione_estiva",
    ),
    "fase_2_invernale": (
        "inizio_sessione_invernale",
        "pre_asta_invernale",
        "post_asta_invernale",
        "chiusura_sessione_invernale",
    ),
    "fase_3_fine_stagione": ("fine_stagione",),
}

PHASE_UPDATE_ACTIONS = {
    "fase_1_estiva": (
        "Aggiorna inizio stagione",
        "inizio_stagione",
        "inizio_stagione",
    ),
    "fase_2_invernale": (
        "Aggiorna inizio sessione invernale",
        "complete",
        "inizio_sessione_invernale",
    ),
    "fase_3_fine_stagione": (
        "Aggiorna fine stagione",
        "complete",
        "fine_stagione",
    ),
}

PHASE_AUCTION_ACTIONS = {
    "fase_1_estiva": ("Esporta rose per asta", "Importa asta estiva"),
    "fase_2_invernale": ("Esporta rose per asta", "Importa asta invernale"),
}


def _date_to_qdate(value: dt.date | None) -> QDate:
    value = value or dt.date.today()
    return QDate(value.year, value.month, value.day)


def _qdate_to_date(value: QDate) -> dt.date:
    return dt.date(value.year(), value.month(), value.day())


class _OptionalDateControl:
    def __init__(self, label: str, value: dt.date | None):
        self.checkbox = QCheckBox(label)
        self.checkbox.setChecked(value is not None)
        self.date_edit = QDateEdit(_date_to_qdate(value))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setEnabled(value is not None)
        self.checkbox.toggled.connect(self.date_edit.setEnabled)

    def value(self) -> dt.date | None:
        if not self.checkbox.isChecked():
            return None
        return _qdate_to_date(self.date_edit.date())


class StagioniWidget(QWidget):
    def __init__(
        self,
        service: StagioneService,
        backup_service: BackupService,
        quotazioni_service: QuotazioniService | None = None,
        mercato_service: MercatoService | None = None,
        quotazioni_provider=None,
        refresh_callback=None,
        show_mercato_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.service = service
        self.backup_service = backup_service
        self.quotazioni_service = quotazioni_service
        self.mercato_service = mercato_service
        self.quotazioni_provider = quotazioni_provider
        self.refresh_callback = refresh_callback
        self.show_mercato_callback = show_mercato_callback
        self._active: StagioneDTO | None = None
        self._phase_controls: dict[str, dict[str, _OptionalDateControl]] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Stagioni")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("Aggiorna")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._content_widget = QWidget()
        self._content = QVBoxLayout(self._content_widget)
        self._content.setContentsMargins(0, 0, 0, 0)
        self._content.setSpacing(12)
        scroll.setWidget(self._content_widget)
        root.addWidget(scroll, stretch=1)

    def refresh(self):
        self._active = self.service.get_active_stagione()
        self._clear_layout(self._content)
        self._phase_controls = {}
        if self._active:
            self._render_active(self._active)
        else:
            self._render_empty_state()
        self._content.addStretch()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

    def _render_empty_state(self):
        box = QGroupBox("Nuova stagione")
        layout = QFormLayout(box)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        today = dt.date.today()
        default_year = today.year
        self._new_year = QSpinBox()
        self._new_year.setRange(2000, 2100)
        self._new_year.setValue(default_year)
        self._new_year.valueChanged.connect(self._update_new_code_preview)

        self._new_code_preview = QLabel(build_stagione_code(default_year))
        self._new_start_date = QDateEdit(QDate(default_year, 8, 1))
        self._new_start_date.setCalendarPopup(True)

        create_btn = QPushButton("Inizia nuova stagione")
        create_btn.clicked.connect(self._create_stagione)

        layout.addRow("Anno inizio", self._new_year)
        layout.addRow("Codice stagione", self._new_code_preview)
        layout.addRow("Data inizio", self._new_start_date)
        layout.addRow(create_btn)
        self._content.addWidget(box)

    def _render_active(self, stagione: StagioneDTO):
        summary = QGroupBox(f"Stagione attiva {stagione.codice}")
        summary_layout = QFormLayout(summary)
        summary_layout.setContentsMargins(12, 12, 12, 12)
        summary_layout.setSpacing(8)

        self._season_start_date = QDateEdit(_date_to_qdate(stagione.data_inizio))
        self._season_start_date.setCalendarPopup(True)
        self._season_end_date = _OptionalDateControl("Impostata", stagione.data_fine)

        summary_layout.addRow("Stato", QLabel(stagione.stato))
        summary_layout.addRow("Fase corrente", QLabel(stagione.fase_corrente or "-"))
        summary_layout.addRow("Cartella", QLabel(stagione.storage_path))
        summary_layout.addRow("Data inizio", self._season_start_date)
        summary_layout.addRow("Data fine", self._optional_row(self._season_end_date))
        self._content.addWidget(summary)

        for fase in stagione.fasi:
            self._content.addWidget(self._phase_box(fase))

        actions = QHBoxLayout()
        actions.addStretch()
        save_btn = QPushButton("Salva date stagione")
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(self._save_dates)
        actions.addWidget(save_btn)
        self._content.addLayout(actions)

    def _phase_box(self, fase: StagioneFaseDTO) -> QGroupBox:
        box = QGroupBox(fase.nome)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QFormLayout(box)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        start = _OptionalDateControl("Impostata", fase.data_inizio)
        end = _OptionalDateControl("Impostata", fase.data_fine)
        asta_start = _OptionalDateControl("Impostata", fase.asta_data_inizio)
        asta_end = _OptionalDateControl("Impostata", fase.asta_data_fine)
        self._phase_controls[fase.codice_fase] = {
            "start": start,
            "end": end,
            "asta_start": asta_start,
            "asta_end": asta_end,
        }

        layout.addRow("Stato", QLabel(fase.stato))
        layout.addRow("Inizio fase", self._optional_row(start))
        layout.addRow("Fine fase", self._optional_row(end))
        layout.addRow("Inizio asta", self._optional_row(asta_start))
        layout.addRow("Fine asta", self._optional_row(asta_end))
        update_row = self._update_button(fase.codice_fase)
        if update_row:
            layout.addRow("Update", update_row)
        auction_row = self._auction_buttons(fase.codice_fase)
        if auction_row:
            layout.addRow("Asta", auction_row)
        end_season_row = self._end_season_buttons(fase.codice_fase)
        if end_season_row:
            layout.addRow("Fine contratto", end_season_row)
        backup_row = self._backup_buttons(fase.codice_fase)
        if backup_row:
            layout.addRow("Backup", backup_row)
        return box

    def _optional_row(self, control: _OptionalDateControl) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(control.checkbox)
        layout.addWidget(control.date_edit)
        layout.addStretch()
        return wrapper

    def _update_new_code_preview(self):
        self._new_code_preview.setText(build_stagione_code(self._new_year.value()))

    def _create_stagione(self):
        try:
            self.service.create_stagione(
                CreateStagioneCommand(
                    anno_inizio=self._new_year.value(),
                    data_inizio=_qdate_to_date(self._new_start_date.date()),
                )
            )
        except ActiveStagioneExistsError as exc:
            QMessageBox.warning(self, "Stagione attiva presente", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Creazione stagione fallita: {exc}")
            return

        QMessageBox.information(self, "Stagione creata", "Nuova stagione attiva creata.")
        self.refresh()

    def _save_dates(self):
        if not self._active:
            return

        try:
            updates = []
            for codice_fase, controls in self._phase_controls.items():
                updates.append(
                    UpdateStagioneFaseCommand(
                        codice_fase=codice_fase,
                        data_inizio=controls["start"].value(),
                        data_fine=controls["end"].value(),
                        asta_data_inizio=controls["asta_start"].value(),
                        asta_data_fine=controls["asta_end"].value(),
                    )
                )
            self.service.update_stagione_dates(
                UpdateStagioneDatesCommand(
                    stagione_id=self._active.id,
                    data_inizio=_qdate_to_date(self._season_start_date.date()),
                    data_fine=self._season_end_date.value(),
                    fasi=updates,
                )
            )
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Salvataggio date fallito: {exc}")
            return

        QMessageBox.information(self, "Date salvate", "Date stagione aggiornate.")
        self.refresh()

    def _backup_buttons(self, codice_fase: str) -> QWidget | None:
        keys = PHASE_BACKUP_KEYS.get(codice_fase)
        if not keys:
            return None

        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for key in keys:
            button = QPushButton(SEASONAL_BACKUPS[key].label)
            button.clicked.connect(
                lambda checked=False, backup_key=key: self._run_backup(backup_key)
            )
            layout.addWidget(button)
        layout.addStretch()
        return wrapper

    def _run_backup(self, backup_key: str):
        if not self._active:
            return

        try:
            result = self.backup_service.create_season_backup(self._active, backup_key)
        except Exception as exc:
            QMessageBox.critical(self, "Errore backup", f"Backup fallito: {exc}")
            return

        paths = "\n".join(str(path) for path in result.paths)
        QMessageBox.information(self, "Backup creato", f"{result.message}\n\n{paths}")

    def _update_button(self, codice_fase: str) -> QWidget | None:
        action = PHASE_UPDATE_ACTIONS.get(codice_fase)
        if not action:
            return None

        label, mode, backup_key = action
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton(label)
        button.clicked.connect(
            lambda checked=False: self._run_season_update(mode, backup_key)
        )
        layout.addWidget(button)
        layout.addStretch()
        return wrapper

    def _run_season_update(self, mode: str, backup_key: str):
        if not self._active:
            return
        if not self.quotazioni_service or not self.quotazioni_provider:
            QMessageBox.warning(
                self,
                "Update non configurato",
                "Il service quotazioni non e' disponibile.",
            )
            return

        quotazioni = self.quotazioni_provider()
        if not quotazioni:
            QMessageBox.warning(
                self,
                "Quotazioni mancanti",
                "Carica prima il file Quotazioni dalla barra Giocatori.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Conferma update",
            "Questa operazione aggiornera' i dati giocatori e creera' il backup "
            "stagionale collegato. Vuoi continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if mode == "inizio_stagione":
                quote_result = self.quotazioni_service.quotazioni_update(quotazioni)
                serie_a_result = self.quotazioni_service.serie_a_update(quotazioni)
                update_message = (
                    "Aggiornamento inizio stagione completato.\n"
                    f"Quotazioni aggiornate: {quote_result.quotazioni_aggiornate}\n"
                    f"Giocatori presenti in Serie A: {serie_a_result.presenti}\n"
                    f"Giocatori assenti: {serie_a_result.assenti}"
                )
            else:
                result = self.quotazioni_service.complete_update(quotazioni)
                update_message = (
                    "Complete update completato.\n"
                    f"Giocatori presenti: {result.presenti}\n"
                    f"Giocatori assenti: {result.assenti}\n"
                    f"Valori svincolo aggiornati: {result.valori_svincolo_aggiornati}"
                )

            backup_result = self.backup_service.create_season_backup(
                self._active,
                backup_key,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Errore update", f"Update fallito: {exc}")
            return

        if self.refresh_callback:
            self.refresh_callback()
        else:
            self.refresh()

        paths = "\n".join(str(path) for path in backup_result.paths)
        QMessageBox.information(
            self,
            "Update completato",
            f"{update_message}\n\n{backup_result.message}\n\n{paths}",
        )

    def _end_season_buttons(self, codice_fase: str) -> QWidget | None:
        if codice_fase != "fase_3_fine_stagione":
            return None

        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        month_combo = QComboBox()
        month_combo.addItem("Maggio", userData=5)
        month_combo.addItem("Giugno", userData=6)
        month_combo.setCurrentIndex(1)
        layout.addWidget(month_combo)

        button = QPushButton("Svincola contratti scaduti")
        button.clicked.connect(
            lambda checked=False, combo=month_combo: self._run_svincolo_fine_contratto(combo)
        )
        layout.addWidget(button)
        layout.addStretch()
        return wrapper

    def _run_svincolo_fine_contratto(self, month_combo: QComboBox):
        if not self._active:
            return
        if not self.mercato_service:
            QMessageBox.warning(
                self,
                "Service non configurato",
                "Il service mercato non e' disponibile.",
            )
            return

        mese = int(month_combo.currentData())
        mese_label = month_combo.currentText()
        reply = QMessageBox.question(
            self,
            "Conferma svincolo",
            "Questa operazione svincolera' i giocatori con contratto scaduto "
            f"nella stagione {self._active.codice}, senza accredito FM, e "
            "creera' il backup di fine stagione. Vuoi continuare?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.mercato_service.svincola_fine_contratto(
                SvincoloFineContrattoCommand(
                    stagione_id=self._active.id,
                    stagione_codice=self._active.codice,
                    anno_fine=self._active.anno_fine,
                    mese_regolamento=mese,
                )
            )
            if result.giocatori_svincolati == 0:
                QMessageBox.information(
                    self,
                    "Nessuno svincolo",
                    "Non ci sono giocatori con contratto in scadenza per "
                    f"la stagione {self._active.codice}.",
                )
                return

            backup_result = self.backup_service.create_season_backup(
                self._active,
                "fine_stagione",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Errore fine stagione",
                f"Svincolo contratti scaduti fallito: {exc}",
            )
            return

        if self.refresh_callback:
            self.refresh_callback()
        else:
            self.refresh()

        paths = "\n".join(str(path) for path in backup_result.paths)
        QMessageBox.information(
            self,
            "Svincoli completati",
            f"Giocatori svincolati: {result.giocatori_svincolati}\n"
            f"Fantasquadre coinvolte: {result.fantasquadre_coinvolte}\n"
            f"Contesto regolamentare: Fine stagione {self._active.codice} - {mese_label}"
            f"\n\n{backup_result.message}\n\n{paths}",
        )

    def _auction_buttons(self, codice_fase: str) -> QWidget | None:
        labels = PHASE_AUCTION_ACTIONS.get(codice_fase)
        if not labels:
            return None

        export_label, import_label = labels
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        export_btn = QPushButton(export_label)
        export_btn.clicked.connect(
            lambda checked=False, phase_code=codice_fase: self._export_rosters_for_asta(phase_code)
        )
        layout.addWidget(export_btn)

        import_btn = QPushButton(import_label)
        import_btn.clicked.connect(self._go_to_mercato_for_asta)
        layout.addWidget(import_btn)
        layout.addStretch()
        return wrapper

    def _export_rosters_for_asta(self, phase_code: str):
        if not self._active:
            return
        try:
            result = self.backup_service.export_rosters_for_asta(self._active, phase_code)
        except Exception as exc:
            QMessageBox.critical(self, "Errore export asta", f"Export fallito: {exc}")
            return

        paths = "\n".join(str(path) for path in result.paths)
        QMessageBox.information(self, "Export asta", f"{result.message}\n\n{paths}")

    def _go_to_mercato_for_asta(self):
        if self.show_mercato_callback:
            self.show_mercato_callback()
        QMessageBox.information(
            self,
            "Importa asta",
            "Usa il tab Mercato e la sezione Importa asta per completare l'import.",
        )
