from datetime import datetime


class Repository:
    def __init__(self, session, model, fields):
        self.session = session
        self.model = model
        self.fields = fields

    def all(self):
        return self.session.query(self.model).filter_by(deleted=False).all()
    
    def all_deleted(self):
        return self.session.query(self.model).filter_by(deleted=True).all()
    
    def create(self, data: dict):
        # Convert data types as needed
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
        # Get the column type from the model
        column = getattr(self.model, field)
        converted_value = self._convert_value(value, column.type)
        setattr(obj, field, converted_value)
        self.session.commit()
    
    def soft_delete(self, obj):
        obj.deleted = True
        self.session.commit()
    
    def restore(self, obj):
        obj.deleted = False
        self.session.commit()
    
    def hard_delete(self, obj):
        self.session.delete(obj)
        self.session.commit()
    
    def _convert_data_types(self, data: dict) -> dict:
        """Convert string values to appropriate types based on model columns"""
        converted = {}
        for field, value in data.items():
            if field not in self.fields:
                continue
            
            # Skip empty strings
            if value == "" or value is None:
                converted[field] = None
                continue
            
            # Get the column from the model
            column = getattr(self.model, field)
            converted[field] = self._convert_value(value, column.type)
        
        return converted
    
    def _convert_value(self, value, column_type):
        """Convert a value to the appropriate type based on column type"""
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
                if hasattr(value, 'strftime'):  # Already a date
                    return value
                # Try to parse string date
                if isinstance(value, str):
                    # Try common date formats
                    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']:
                        try:
                            return datetime.strptime(value, fmt).date()
                        except ValueError:
                            continue
                return None
            else:  # String or other
                return str(value)
        except (ValueError, TypeError):
            return None