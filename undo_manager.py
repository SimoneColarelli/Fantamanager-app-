import os
from backup import export_db, import_db

UNDO_DIR = "undo_stack"

class UndoManager:
    def __init__(self, session):
        self.session = session
        os.makedirs(UNDO_DIR, exist_ok=True)

    def snapshot(self):
        files = sorted(os.listdir(UNDO_DIR))
        idx = int(files[-1].split(".")[0]) + 1 if files else 1
        export_db(self.session, f"{UNDO_DIR}/{idx:03}.json")

    def undo(self):
        files = sorted(os.listdir(UNDO_DIR))
        if not files:
            return False
        last = files[-1]
        import_db(self.session, f"{UNDO_DIR}/{last}")
        os.remove(f"{UNDO_DIR}/{last}")
        return True
