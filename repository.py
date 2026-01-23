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
        obj = self.model(**data)
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
        obj.deleted = True
        self.session.commit()
    
    def restore(self, obj):
        obj.deleted = False
        self.session.commit()
    
    def hard_delete(self, obj):
        self.session.delete(obj)
        self.session.commit()