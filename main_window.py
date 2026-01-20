from PySide6.QtWidgets import QMainWindow, QTabWidget, QTableView
from database import SessionLocal, engine
from models import Giocatore, Fantasquadra
from repository import Repository
from table_model import EditableTableModel
from constants import *


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fantamanager – Phase 3")
        self.resize(1000, 600)

        Giocatore.metadata.create_all(engine)

        session = SessionLocal()

        self.tabs = QTabWidget()

        g_repo = Repository(session, Giocatore, GIOCATORI_FIELDS)
        g_model = EditableTableModel(g_repo, GIOCATORI_FIELDS, GIOCATORI_HEADERS)

        g_view = QTableView()
        g_view.setModel(g_model)
        g_view.clicked.connect(self._handle_click)


        f_repo = Repository(session, Fantasquadra, FANTASQUADRE_FIELDS)
        f_model = EditableTableModel(f_repo, FANTASQUADRE_FIELDS, FANTASQUADRE_HEADERS)

        f_view = QTableView()
        f_view.setModel(f_model)
        f_view.clicked.connect(self._handle_click)


        self.tabs.addTab(g_view, "Giocatori")
        self.tabs.addTab(f_view, "Fantasquadre")

        self.setCentralWidget(self.tabs)

    def _handle_click(self, index):
        model = index.model()
        if (
            index.row() == model.rowCount() - 1
            and index.column() == model.columnCount() - 1
        ):
            model.create_from_row()

