from datetime import datetime, date


class Repository:
    def __init__(self, session_factory, model, fields):
        self.session_factory = session_factory
        self.model = model
        self.fields = fields
        # Keep a persistent session for writes (add/commit/delete)
        self.session = session_factory()

    def _fresh_session(self):
        """Return a new session to bypass SQLAlchemy's identity map cache."""
        return self.session_factory()

    def all(self):
        """
        Load all active records and merge them into the write session so that
        any later setattr + session.commit() actually persists to the DB.
        """
        fresh = self._fresh_session()
        try:
            results = fresh.query(self.model).filter_by(deleted=False).all()
            fresh.expunge_all()
        finally:
            fresh.close()

        # Merge every detached object into the persistent write session so
        # edits made via setattr() are tracked and committed correctly.
        merged = [self.session.merge(obj) for obj in results]
        return merged

    def all_deleted(self):
        session = self._fresh_session()
        try:
            results = session.query(self.model).filter_by(deleted=True).all()
            session.expunge_all()
            return results
        finally:
            session.close()

    def create(self, data: dict):
        converted_data = self._convert_data_types(data)
        obj = self.model(**converted_data)
        self.session.add(obj)
        self.session.commit()
        return obj

    def create_empty(self):
        obj = self.model()
        self.session.add(obj)
        self.session.commit()
        return obj

    def set_value(self, obj, field, value):
        setattr(obj, field, value)
        self.session.commit()
    
    def soft_delete(self, obj):
        if obj not in self.session:
            obj = self.session.merge(obj)
        obj.deleted = True
        self.session.commit()
    
    def restore(self, obj):
        if obj not in self.session:
            obj = self.session.merge(obj)
        obj.deleted = False
        self.session.commit()
    
    def hard_delete(self, obj):
        if obj not in self.session:
            obj = self.session.merge(obj)
        self.session.delete(obj)
        self.session.commit()

    def _convert_data_types(self, data: dict) -> dict:
        converted = {}
        for field, value in data.items():
            if field not in self.fields:
                continue
            # Skip fields that are not actual DB columns on the model
            # (e.g. computed display-only fields like in_rosa, convocati)
            if not hasattr(self.model, field):
                continue
            if value == "" or value is None:
                converted[field] = None
                continue
            column = getattr(self.model, field)
            converted[field] = self._convert_value(value, column.type)
        return converted
    
    def _parse_italian_date(self, date_str):
        if not date_str or date_str == "":
            return None
        months = {
            "gen": 1, "feb": 2, "mar": 3, "apr": 4,
            "mag": 5, "giu": 6, "lug": 7, "ago": 8,
            "set": 9, "ott": 10, "nov": 11, "dic": 12
        }
        try:
            parts = date_str.split("-")
            if len(parts) != 2:
                return None
            month_abbr = parts[0].lower()
            year_short = parts[1]
            if month_abbr not in months:
                return None
            month_num = months[month_abbr]
            year_full = 2000 + int(year_short)
            return date(year_full, month_num, 1)
        except (ValueError, AttributeError, IndexError):
            return None
    
    def _convert_value(self, value, column_type):
        from sqlalchemy import Integer, Float, Boolean, Date, String
        if value == "" or value is None:
            return None
        type_name = type(column_type).__name__
        try:
            if type_name == 'Integer':
                return int(value)
            elif type_name == 'Float':
                return float(value)
            elif type_name == 'Boolean':
                if isinstance(value, bool):
                    return value
                return str(value).lower() in ('true', '1', 'yes', 'si', 'sì')
            elif type_name == 'Date':
                if isinstance(value, datetime):
                    return value.date()
                if hasattr(value, 'strftime'):
                    return value
                if isinstance(value, str):
                    italian_date = self._parse_italian_date(value)
                    if italian_date:
                        return italian_date
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                        try:
                            return datetime.strptime(value, fmt).date()
                        except ValueError:
                            continue
                return None
            else:
                return str(value)
        except (ValueError, TypeError):
            return None