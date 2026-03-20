from PySide6.QtWidgets import QStyledItemDelegate, QComboBox
from PySide6.QtCore import Qt


class FasciaDelegate(QStyledItemDelegate):
    """Custom delegate for integer fields with Sì/No dropdown"""
    
    def createEditor(self, parent, option, index):
        """Create a QComboBox for editing int values of fascia column"""
        editor = QComboBox(parent)
        editor.setEditable(True)
        editor.addItem("1")
        editor.addItem("2")
        editor.addItem("3")
        editor.addItem("4")
        editor.addItem("5")
        editor.addItem("6")
        return editor
    
    def setEditorData(self, editor, index):
        """Set the current value in the combo box"""
        value = index.data(Qt.ItemDataRole.EditRole)
        
        if value == 1 or value == "1":
            editor.setCurrentIndex(0)
        elif value == 2 or value == "2":
            editor.setCurrentIndex(1)
        elif value == 3 or value == "3":
            editor.setCurrentIndex(2)
        elif value == 4 or value == "4":
            editor.setCurrentIndex(3)
        elif value == 5 or value == "5":
            editor.setCurrentIndex(4)
        elif value == 6 or value == "6":
            editor.setCurrentIndex(5)
    
    def setModelData(self, editor, model, index):
        """Save the selected value back to the model"""
        text = editor.currentText()
        model.setData(index, text, Qt.ItemDataRole.EditRole)
    
    def updateEditorGeometry(self, editor, option, index):
        """Update the geometry of the editor"""
        editor.setGeometry(option.rect)