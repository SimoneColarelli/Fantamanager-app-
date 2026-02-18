from PySide6.QtCore import QSortFilterProxyModel, Qt

class SearchProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_text = ""
        self.filter_col_index = -1

    def set_search_text(self, text):
        self.search_text = text.lower()
        self.invalidateFilter()  # Triggers a re-filter

    def set_filter_column(self, index):
        self.filter_col_index = index

    def filterAcceptsRow(self, source_row, source_parent):
        # Always show the creation row (row 0)
        if source_row == 0:
            return True
        
        # If no search text or column is invalid, show everything
        if not self.search_text or self.filter_col_index == -1:
            return True
            
        index = self.sourceModel().index(source_row, self.filter_col_index, source_parent)
        data = self.sourceModel().data(index, Qt.ItemDataRole.DisplayRole)
        
        if data is not None:
            # Check if the typed string is inside the cell's data
            return self.search_text in str(data).lower()
        return False

    # --- Delegate custom row methods to the source model ---
    # The view calls these with proxy indexes, we map them back to the source indexes
    
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
    
    def has_pending_changes(self, proxy_row):
        source_row = self.mapToSource(self.index(proxy_row, 0)).row()
        if hasattr(self.sourceModel(), 'has_pending_changes'):
            return self.sourceModel().has_pending_changes(source_row) #type: ignore
        return False