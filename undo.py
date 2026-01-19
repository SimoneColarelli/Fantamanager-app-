from backup import export_db, import_db

UNDO_FILE = "undo.json"


class UndoManager:
    def __init__(self, session):
        self.session = session

    def snapshot(self):
        """Save current state before making changes"""
        export_db(self.session, UNDO_FILE)

    def undo(self):
        """Restore last saved state"""
        try:
            import_db(self.session, UNDO_FILE)
            return True
        except FileNotFoundError:
            return False