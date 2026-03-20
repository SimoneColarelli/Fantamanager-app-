from PySide6.QtWidgets import QStyledItemDelegate, QComboBox
from PySide6.QtCore import Qt
from datetime import datetime

from helpers import from_str_to_trunc_date


def get_current_year_month():
    """Get current year (short form) and month (Italian abbreviation)"""
    now = datetime.now()
    cy = now.strftime("%y")  # Last 2 digits of year
    
    months_it = {
        1: "gen", 2: "feb", 3: "mar", 4: "apr",
        5: "mag", 6: "giu", 7: "lug", 8: "ago",
        9: "set", 10: "ott", 11: "nov", 12: "dic"
    }
    cm = months_it[now.month]
    
    return cy, cm


class DataAcquistoDelegate(QStyledItemDelegate):
    """Delegate for 'Data acquisto' column"""
    
    def createEditor(self, parent, option, index):
        cy, cm = get_current_year_month()
        value = from_str_to_trunc_date(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole))
        
        editor = QComboBox(parent)
        editor.setEditable(True)
        choices = [f"ago-{cy}", f"set-{cy}", f"gen-{cy}", f"feb-{cy}", value] if value and value != "" else [f"ago-{cy}", f"set-{cy}", f"gen-{cy}", f"feb-{cy}"]
        
        for choice in choices:
            editor.addItem(choice)
        
        # Set default value
        if value and value !="":
            default = value        
        else:
            default = f"{cm}-{cy}" if f"{cm}-{cy}" in choices else f"ago-{cy}"

        default_index = choices.index(default) if default in choices else 0
        editor.setCurrentIndex(default_index)
        
        return editor
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole)
        if value and value != "":
            # Find the item in the combobox
            idx = editor.findText(str(value))
            if idx >= 0:
                editor.setCurrentIndex(idx)
    
    def setModelData(self, editor, model, index):
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class ScadenzaContrattoDelegate(QStyledItemDelegate):
    """Delegate for 'Scadenza contratto' column - depends on Data acquisto"""
    
    def __init__(self, model, data_acquisto_col_index):
        super().__init__()
        self.model = model
        self.data_acquisto_col = data_acquisto_col_index
    
    def createEditor(self, parent, option, index):
        cy, cm = get_current_year_month()
        cy_int = int(cy)
        value = from_str_to_trunc_date(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole))
        
        # Get Data acquisto value from the same row
        row = index.row()
        data_acquisto_index = self.model.index(row, self.data_acquisto_col)
        data_acquisto = self.model.data(data_acquisto_index, Qt.ItemDataRole.DisplayRole)
        
        editor = QComboBox(parent)
        editor.setEditable(True)
        
        # Determine choices based on Data acquisto


        if data_acquisto in [f"gen-{cy}", f"feb-{cy}"]:
            choices = [f"lug-{cy_int + 2:02d}", f"lug-{cy_int + 3:02d}", value] if value and value != "" and index.row() > 0 else [f"lug-{cy_int + 2:02d}", f"lug-{cy_int + 3:02d}"]
            if value and value != "":
                default = value
            else:
                default = choices[0]  # lug-(cy+2)
        else:
            choices = [f"lug-{cy_int + 3:02d}", f"lug-{cy_int + 4:02d}", value] if value and value != "" else [f"lug-{cy_int + 3:02d}", f"lug-{cy_int + 4:02d}"]
            if value and value != "":
                default = value
            else:
                default = choices[0]  # lug-(cy+3)
        
        for choice in choices:
            editor.addItem(choice)
        
        # Set default
        default_index = choices.index(default) if default in choices else 0
        editor.setCurrentIndex(default_index)
        
        return editor
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole)
        if value and value != "":
            idx = editor.findText(str(value))
            if idx >= 0:
                editor.setCurrentIndex(idx)
    
    def setModelData(self, editor, model, index):
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class InizioPrestitoDelegate(QStyledItemDelegate):
    """Delegate for 'Inizio prestito' column - same as Data acquisto"""
    
    def createEditor(self, parent, option, index):
        cy, cm = get_current_year_month()
        value = from_str_to_trunc_date(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole))

        
        editor = QComboBox(parent)
        editor.setEditable(True)
        choices = [f"ago-{cy}", f"set-{cy}", f"gen-{cy}", f"feb-{cy}", value, ""] if value and value != "" and value != "nuovo inizio prestito" else [f"ago-{cy}", f"set-{cy}", f"gen-{cy}", f"feb-{cy}", ""]
        
        for choice in choices:
            editor.addItem(choice)
        
        # Set default value

        # When i'm not in a creation row: if it has already a value, set it as default in the combo, otherwise set default to empty (nessun prestito)
        if index.row() != 0:
            if value:
                default = value
            else:
                default = ""
        else:
            default = "" # In creation row, default to empty (nessun prestito)

        default_index = choices.index(default) if default in choices else 0
        editor.setCurrentIndex(default_index)
        
        return editor
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole)
        if value and value != "":
            idx = editor.findText(str(value))
            if idx >= 0:
                editor.setCurrentIndex(idx)
    
    def setModelData(self, editor, model, index):
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class FinePrestitoDelegate(QStyledItemDelegate):
    """Delegate for 'Fine prestito' column - depends on Data acquisto"""
    
    def __init__(self, model, inizio_prestito_col_index):
        super().__init__()
        self.model = model
        self.inizio_prestito_col = inizio_prestito_col_index
    
    def createEditor(self, parent, option, index):
        cy, cm = get_current_year_month()
        cy_int = int(cy)
        value = from_str_to_trunc_date(index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole))
        
        # Get inizio prestito value from the same row
        row = index.row()
        inizio_prestito_index = self.model.index(row, self.inizio_prestito_col)
        inizio_prestito = self.model.data(inizio_prestito_index, Qt.ItemDataRole.DisplayRole) or self.model.data(inizio_prestito_index, Qt.ItemDataRole.EditRole)
        inizio_prestito = from_str_to_trunc_date(inizio_prestito)
        
        editor = QComboBox(parent)
        editor.setEditable(True)
        
        # Choices: gen-(cy+1), lug-(cy+1), lug-(cy+2), lug-cy, cm-(cy+1), cm-(cy+2)
        choices = [
            f"gen-{cy_int + 1:02d}",
            f"lug-{cy_int + 1:02d}",
            f"lug-{cy_int + 2:02d}",
            f"lug-{cy}",
            f"{cm}-{cy_int + 1:02d}",
            f"{cm}-{cy_int + 2:02d}",
            value,
            ""
        ] if value and value != "" and value != "nuovo fine prestito" else [
            f"gen-{cy_int + 1:02d}",    
            f"lug-{cy_int + 1:02d}",
            f"lug-{cy_int + 2:02d}",
            f"lug-{cy}",
            f"{cm}-{cy_int + 1:02d}",
            f"{cm}-{cy_int + 2:02d}",
            ""
        ]
        
        for choice in choices:
            editor.addItem(choice)
        
        # If i'm not in a creation row: if it has already a value, set it as default in the combo, otherwise set default based on inizio prestito value:
        if index.row() != 0:
            if value:
                default = value
            else: default = ""
        else:
            if inizio_prestito in [f"ago-{cy}", f"set-{cy}"]:
                    default = f"gen-{cy_int + 1:02d}"
            else: default = ""
        
        default_index = choices.index(default) if default in choices else 0
        editor.setCurrentIndex(default_index)
        
        return editor
    
    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole) or index.data(Qt.ItemDataRole.DisplayRole)
        if value and value != "":
            idx = editor.findText(str(value))
            if idx >= 0:
                editor.setCurrentIndex(idx)
    
    def setModelData(self, editor, model, index):
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)