import json
import datetime
from sqlalchemy import DateTime, inspect, text
from sqlalchemy.orm import Session
from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PySide6.QtCore import QDir, Signal

# --- ADJUST THESE IMPORTS TO MATCH YOUR PROJECT STRUCTURE ---
from database import SessionLocal, engine, Base
from models import * # Import all models to ensure they are registered in Base
# -----------------------------------------------------------

class DataManager:
    """
    Handles the logic for exporting and importing data to/from JSON.
    """
    @staticmethod
    def get_all_models():
        """
        Retrieves all SQLAlchemy models registered with Base.
        """
        # For SQLAlchemy 1.4+
        if hasattr(Base, 'registry'):
            return [mapper.class_ for mapper in Base.registry.mappers]
        # Fallback for older versions
        else:
            return [c for c in Base._decl_class_registry.values() if isinstance(c, type) and issubclass(c, Base)]

    @staticmethod
    def model_to_dict(obj):
        """
        Converts a SQLAlchemy model instance to a dictionary.
        Handles datetime serialization.
        """
        data = {}
        mapper = inspect(obj).mapper
        for col in mapper.column_attrs:
            val = getattr(obj, col.key)
            if isinstance(val, (datetime.date, datetime.datetime)):
                val = val.isoformat()
            data[col.key] = val
        return data

    @staticmethod
    def export_data(filepath, models=None):
        """
        Exports data from specified models (or all if None) to a JSON file.
        """
        session: Session = SessionLocal()
        try:
            target_models = models if models else DataManager.get_all_models()
            export_dict = {}

            for model in target_models:
                table_name = model.__tablename__
                records = session.query(model).all()
                export_dict[table_name] = [DataManager.model_to_dict(r) for r in records]

            # Export the operazione_giocatori association table separately
            # (it is a plain Table, not an ORM class, so it is invisible to get_all_models)
            try:
                from sqlalchemy import text as _text
                rows = session.execute(_text("SELECT operazione_id, giocatore_id FROM operazione_giocatori")).fetchall()
                export_dict["operazione_giocatori"] = [
                    {"operazione_id": r[0], "giocatore_id": r[1]} for r in rows
                ]
            except Exception:
                pass

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_dict, f, indent=4, ensure_ascii=False)
            
            return True, "Backup creato correttamente."
        except Exception as e:
            return False, str(e)
        finally:
            session.close()

    @staticmethod
    def import_data(filepath, specific_table=None):
        """
        Imports data from a JSON file.
        If specific_table is provided (as a Model class), only imports that table.
        Otherwise, wipes and imports all found tables.
        Automatically handles string-to-date conversion.
        """
        session: Session = SessionLocal()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # SQLite specific: Disable foreign keys temporarily to allow arbitrary insertion order
            if 'sqlite' in session.bind.dialect.name: #type: ignore
                session.execute(text("PRAGMA foreign_keys=OFF"))

            models_map = {m.__tablename__: m for m in DataManager.get_all_models()}
            tables_to_import = [specific_table.__tablename__] if specific_table else data.keys()

            for table_name in tables_to_import:
                if table_name not in data:
                    continue
                
                if table_name not in models_map:
                    print(f"Warning: Table {table_name} found in JSON but no matching model found.")
                    continue

                model_class = models_map[table_name]
                records = data[table_name]
                
                # Get the mapper to inspect column types
                mapper = inspect(model_class)

                # 1. Clear existing data for this table
                session.query(model_class).delete()

                # 2. Insert new data
                for record_data in records:
                    clean_data = {}
                    
                    for col_name, val in record_data.items():
                        # If the value is a string and the column expects a Date/DateTime, convert it
                        if col_name in mapper.columns:
                            col_type = mapper.columns[col_name].type
                            
                            if val is not None and isinstance(val, str):
                                if isinstance(col_type, Date):
                                    try:
                                        val = datetime.date.fromisoformat(val)
                                    except ValueError:
                                        # Fallback if format is weird, or leave as string to let SQLA try
                                        pass
                                elif isinstance(col_type, DateTime):
                                    try:
                                        val = datetime.datetime.fromisoformat(val)
                                    except ValueError:
                                        pass
                        
                        clean_data[col_name] = val

                    obj = model_class(**clean_data)
                    session.add(obj)

            session.commit()

            # Import operazione_giocatori association rows if present
            if "operazione_giocatori" in data and specific_table is None:
                try:
                    session.execute(text("DELETE FROM operazione_giocatori"))
                    for row in data["operazione_giocatori"]:
                        session.execute(
                            text("INSERT INTO operazione_giocatori (operazione_id, giocatore_id) VALUES (:op_id, :g_id)"),
                            {"op_id": row["operazione_id"], "g_id": row["giocatore_id"]}
                        )
                    session.commit()
                except Exception:
                    session.rollback()

            # Re-enable foreign keys
            if 'sqlite' in session.bind.dialect.name: #type: ignore
                session.execute(text("PRAGMA foreign_keys=ON"))

            return True, "Import successful! Please refresh the view."
        except Exception as e:
            session.rollback()
            return False, f"Import error: {str(e)}"
        finally:
            session.close()

# --- UI INTERGRATION HELPERS ---

class DataManagerUI:

    def __init__(self, parent_window, refresh_callback=None, repos=None):
        """
        parent_window: The main window
        refresh_callback: Optional callback function to refresh all data after import
        repos: list of Repository / OperazioneRepository instances whose sessions
               must be closed before import to release SQLite locks
        """
        self.parent = parent_window
        self.refresh_callback = refresh_callback
        self.repos = repos or []

    def _release_sessions(self):
        """Close all repo sessions to release SQLite file locks before import."""
        for repo in self.repos:
            try:
                repo.session.close()
            except Exception:
                pass

    def _reopen_sessions(self):
        """Open fresh sessions on all repos after import."""
        for repo in self.repos:
            try:
                repo.session = repo.session_factory()
            except Exception:
                pass

    def export_all(self):
        filename, _ = QFileDialog.getSaveFileName(
            self.parent, "Crea backup completo", QDir.homePath(), "JSON Files (*.json)"
        )
        if filename:
            success, msg = DataManager.export_data(filename)
            self._show_result(success, msg)

    def import_all(self):
        confirm = QMessageBox.question(
            self.parent, "Confirm Import",
            "Importing will OVERWRITE all existing data.\nAre you sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        filename, _ = QFileDialog.getOpenFileName(
            self.parent, "Import All Data", QDir.homePath(), "JSON Files (*.json)"
        )
        if filename:
            self._release_sessions()
            success, msg = DataManager.import_data(filename)
            self._reopen_sessions()
            self._show_result(success, msg)
            
            # If import was successful and we have a refresh callback, call it
            if success and self.refresh_callback:
                self.refresh_callback()

    def export_single_table(self):
        models = DataManager.get_all_models()
        items = [m.__tablename__ for m in models]
        item, ok = QInputDialog.getItem(self.parent, "Seleziona tabella", "Tabella da salvare in backup:", items, 0, False)
        
        if ok and item:
            # Find the model class
            selected_model = next((m for m in models if m.__tablename__ == item), None)
            if selected_model:
                filename, _ = QFileDialog.getSaveFileName(
                    self.parent, f"Backup {item}", f"{item}.json", "JSON Files (*.json)"
                )
                if filename:
                    success, msg = DataManager.export_data(filename, models=[selected_model])
                    self._show_result(success, msg)

    def import_single_table(self):
        models = DataManager.get_all_models()
        items = [m.__tablename__ for m in models]
        item, ok = QInputDialog.getItem(self.parent, "Select Table", "Table to import into (will overwrite):", items, 0, False)
        
        if ok and item:
            selected_model = next((m for m in models if m.__tablename__ == item), None)
            if selected_model:
                filename, _ = QFileDialog.getOpenFileName(
                    self.parent, f"Import {item}", QDir.homePath(), "JSON Files (*.json)"
                )
                if filename:
                    self._release_sessions()
                    success, msg = DataManager.import_data(filename, specific_table=selected_model)
                    self._reopen_sessions()
                    self._show_result(success, msg)
                    
                    # If import was successful and we have a refresh callback, call it
                    if success and self.refresh_callback:
                        self.refresh_callback()

    def _show_result(self, success, msg):
        if success:
            QMessageBox.information(self.parent, "Success", msg)
        else:
            QMessageBox.critical(self.parent, "Error", f"Operation failed:\n{msg}")
