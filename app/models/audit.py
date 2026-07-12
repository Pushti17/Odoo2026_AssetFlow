from datetime import datetime
from app.database import db

class MaintenanceRequest(db.Model):
    """
    Tracks maintenance requests and repair approval workflows.
    """
    __tablename__ = 'maintenance_requests'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    raised_by_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='Medium') # Low, Medium, High, Urgent
    
    # Workflow Statuses: Pending, Approved, Rejected, In Progress, Resolved
    status = db.Column(db.String(20), default='Pending', nullable=False, index=True)
    technician_assigned = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    raised_by = db.relationship('Employee', backref='maintenance_requests')


class AuditCycle(db.Model):
    """
    Represents an active or historical Audit Cycle for verification runs.
    """
    __tablename__ = 'audit_cycles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    
    # Statuses: Open, Closed
    status = db.Column(db.String(20), default='Open', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    department = db.relationship('Department', backref='audit_cycles')
    audit_items = db.relationship('AuditItem', backref='audit_cycle', lazy=True)


class AuditItem(db.Model):
    """
    Individual asset verification logs created during an Audit Cycle.
    """
    __tablename__ = 'audit_items'

    id = db.Column(db.Integer, primary_key=True)
    audit_cycle_id = db.Column(db.Integer, db.ForeignKey('audit_cycles.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    auditor_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Verification Status: Pending, Verified, Missing, Damaged
    verification_status = db.Column(db.String(20), default='Pending', nullable=False)
    discrepancy_flag = db.Column(db.Boolean, default=False) # True if Missing or Damaged
    notes = db.Column(db.Text, nullable=True)
    
    verified_at = db.Column(db.DateTime, nullable=True)

    auditor = db.relationship('Employee', backref='audited_items')
    asset = db.relationship('Asset', backref='audit_logs')