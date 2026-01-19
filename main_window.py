from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QTableView,
)
from table_model import EditableTableModel
from dummy_data import (
    GIOCATORI_HEADERS,
    GIOCATORI_DATA,
    FANTASQUADRE_HEADERS,
    FANTASQUADRE_DATA,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Fantamanager – Phase 1")
        self.resize(1000, 600)

        self.tabs = QTabWidget()

        # --- Giocatori ---
        self.giocatori_view = QTableView()
        self.giocatori_model = EditableTableModel(
            GIOCATORI_DATA,
            GIOCATORI_HEADERS
        )
        self.giocatori_view.setModel(self.giocatori_model)

        giocatori_tab = QWidget()
        giocatori_layout = QVBoxLayout()
        giocatori_layout.addWidget(self.giocatori_view)
        giocatori_tab.setLayout(giocatori_layout)

        # --- Fantasquadre ---
        self.fantasquadre_view = QTableView()
        self.fantasquadre_model = EditableTableModel(
            FANTASQUADRE_DATA,
            FANTASQUADRE_HEADERS
        )
        self.fantasquadre_view.setModel(self.fantasquadre_model)

        fantasquadre_tab = QWidget()
        fantasquadre_layout = QVBoxLayout()
        fantasquadre_layout.addWidget(self.fantasquadre_view)
        fantasquadre_tab.setLayout(fantasquadre_layout)

        # --- Tabs ---
        self.tabs.addTab(giocatori_tab, "Giocatori")
        self.tabs.addTab(fantasquadre_tab, "Fantasquadre")

        self.setCentralWidget(self.tabs)
