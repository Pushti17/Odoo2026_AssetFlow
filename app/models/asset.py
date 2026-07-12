from datetime import datetime
from app.database import db

class Category(db.Model):
    """
    Asset Categories (e.g., Electronics, Furniture, Vehicles).
    """
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    warranty_period_months = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assets = db.relationship('Asset', backref='category', lazy=True)


class Asset(db.Model):
    """
    Master Asset Table.
    Tracks physical assets, bookable resources, and lifecycle states.
    """
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(50), unique=True, nullable=False, index=True) # AF-0001
    serial_number = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(150), nullable=False)
    
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    acquisition_date = db.Column(db.Date, nullable=True)
    acquisition_cost = db.Column(db.Float, nullable=True)
    
    condition = db.Column(db.String(50), default='Good')
    location = db.Column(db.String(150), nullable=True)
    is_bookable = db.Column(db.Boolean, default=False) # Flag for shared bookable resources

    # States: Available, Allocated, Reserved, Under Maintenance, Lost, Retired, Disposed
    status = db.Column(db.String(30), default='Available', nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    allocations = db.relationship('Allocation', backref='asset', lazy=True)
    transfers = db.relationship('Transfer', backref='asset', lazy=True)
    maintenance_requests = db.relationship('MaintenanceRequest', backref='asset', lazy=True)
    bookings = db.relationship('ResourceBooking', backref='asset', lazy=True)

    @staticmethod
    def generate_asset_tag():
        """
        Auto-generates incremental Asset Tags (AF-0001, AF-0002).
        """
        last_asset = Asset.query.order_by(Asset.id.desc()).first()
        if not last_asset:
            return "AF-0001"
        return f"AF-{last_asset.id + 1:04d}"


class Allocation(db.Model):
    """
    Tracks asset allocations to employees with expected return dates.
    """
    __tablename__ = 'allocations'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expected_return_date = db.Column(db.DateTime, nullable=True)
    returned_date = db.Column(db.DateTime, nullable=True)
    
    is_active = db.Column(db.Boolean, default=True, index=True)
    check_in_notes = db.Column(db.Text, nullable=True)
    returned_condition = db.Column(db.String(50), nullable=True)

    employee = db.relationship('Employee', backref='allocations')


class Transfer(db.Model):
    """
    Workflow for transferring an allocated asset between employees.
    """
    __tablename__ = 'transfers'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    
    from_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    to_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Statuses: Pending, Approved, Rejected
    status = db.Column(db.String(20), default='Pending', nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    from_employee = db.relationship('Employee', foreign_keys=[from_employee_id])
    to_employee = db.relationship('Employee', foreign_keys=[to_employee_id])