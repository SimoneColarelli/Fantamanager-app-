from PySide6.QtCore import QSortFilterProxyModel, Qt

class SearchProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.squadra_text = ""
        self.nome_col_index = -1
        self.squadra_col_index = -1
        self.in_prestito_a_col_index = -1

    def set_filter_columns(self, nome_idx, squadra_idx, in_prestito_a_idx=-1):
        self.nome_col_index = nome_idx
        self.squadra_col_index = squadra_idx
        self.in_prestito_a_col_index = in_prestito_a_idx
        self.invalidateFilter()

    def set_search_text(self, text):
        self.search_text = text.lower()
        self.invalidateFilter()

    def set_squadra_filter(self, text):
        self.squadra_text = text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if source_row == 0:
            return True
        
        # 1. Filtro Nome
        nome_match = True
        if self.search_text and self.nome_col_index != -1:
            index = self.sourceModel().index(source_row, self.nome_col_index, source_parent)
            data = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
            if data is not None:
                nome_match = self.search_text in str(data).lower()
            else:
                nome_match = False
                
        # 2. Filtro Squadra
        # A row matches if:
        #   (squadra == selected AND in_prestito_a is empty)  — player registered to this team and not on loan
        #   OR in_prestito_a == selected                       — player on loan TO this team
        squadra_match = True
        if self.squadra_text and self.squadra_text != "Tutte le squadre" and self.squadra_col_index != -1:
            squadra_idx = self.sourceModel().index(source_row, self.squadra_col_index, source_parent)
            squadra_val = self.sourceModel().data(squadra_idx, Qt.ItemDataRole.DisplayRole) or ""

            in_prestito_val = ""
            if self.in_prestito_a_col_index != -1:
                prestito_idx = self.sourceModel().index(source_row, self.in_prestito_a_col_index, source_parent)
                in_prestito_val = self.sourceModel().data(prestito_idx, Qt.ItemDataRole.DisplayRole) or ""

            owns_and_not_loaned = (squadra_val == self.squadra_text and in_prestito_val == "")
            on_loan_here        = (in_prestito_val == self.squadra_text)
            squadra_match = owns_and_not_loaned or on_loan_here

        return nome_match and squadra_match

    def lessThan(self, left, right):
        """Sovrascrive l'ordinamento standard di Qt per mantenere la riga 0 in alto e usare i dati reali."""
        # Mantieni sempre la riga 0 (riga creazione) fissa in cima!
        if left.row() == 0:
            return self.sortOrder() == Qt.SortOrder.AscendingOrder
        if right.row() == 0:
            return self.sortOrder() == Qt.SortOrder.DescendingOrder

        # Usa il Custom Role (UserRole + 1) che restituisce date o int reali invece di stringhe
        SORT_ROLE = Qt.ItemDataRole.UserRole + 1
        left_data = self.sourceModel().data(left, SORT_ROLE)
        right_data = self.sourceModel().data(right, SORT_ROLE)
        
        if left_data is None and right_data is None:
            return False
        if left_data is None:
            return True
        if right_data is None:
            return False
            
        try:
            return left_data < right_data
        except TypeError:
            # Fallback sicuro se si tenta di comparare tipi diversi (es. un int e una stringa in una colonna mista)
            return str(left_data) < str(right_data)

    # --- Delegate custom row methods to the source model ---
    def soft_delete_row(self, proxy_row):
        source_row = self.mapToSource(self.index(proxy_row, 0)).row()
        if hasattr(self.sourceModel(), 'soft_delete_row'):
            self.sourceModel().soft_delete_row(source_row) #type: ignore

    def commit_row_changes(self, proxy_row):
        source_row = self.mapToSource(self.index(proxy_row, 0)).row()
        if hasattr(self.sourceModel(), 'commit_row_changes'):
            self.sourceModel().commit_row_changes(source_row) #type: ignore

    def cancel_row_changes(self, proxy_row):
        source_row = self.mapToSource(self.index(proxy_row, 0)).row()
        if hasattr(self.sourceModel(), 'cancel_row_changes'):
            self.sourceModel().cancel_row_changes(source_row) #type: ignore
            
    def create_from_row(self):
        if hasattr(self.sourceModel(), 'create_from_row'):
            self.sourceModel().create_from_row() #type: ignore