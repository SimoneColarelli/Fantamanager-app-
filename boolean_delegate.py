from PySide6.QtWidgets import QStyledItemDelegate, QComboBox
from PySide6.QtCore import Qt


class BooleanDelegate(QStyledItemDelegate):
    """Custom delegate for boolean fields with Sì/No dropdown"""
    
    def createEditor(self, parent, option, index):
        """Create a QComboBox for editing boolean values"""
        editor = QComboBox(parent)
        editor.setEditable(True)
        editor.addItem("Sì")
        editor.addItem("No")
        return editor
    
    def setEditorData(self, editor, index):
        """Set the current value in the combo box"""
        value = index.data(Qt.ItemDataRole.EditRole)
        
        if value == "Sì" or value == True or value == "True":
            editor.setCurrentIndex(0)
        elif value == "No" or value == False or value == "False":
            editor.setCurrentIndex(1)
    
    def setModelData(self, editor, model, index):
        """Save the selected value back to the model"""
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        """Update the geometry of the editor"""
        editor.setGeometry(option.rect)