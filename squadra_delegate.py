from PySide6.QtWidgets import QStyledItemDelegate, QComboBox
from PySide6.QtCore import Qt

from database import SessionLocal
from models import Fantasquadra


class SquadraDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        
        editor = QComboBox(parent)
        
        session = SessionLocal()
        # Ottieni tutte le fantasquadre attive
        squadre = session.query(Fantasquadra.nome).filter_by(deleted=False).all()
        session.close()

        for name in squadre:
            editor.addItem(name[0])
        editor.addItem("")  # Opzione per nessuna squadra
        
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