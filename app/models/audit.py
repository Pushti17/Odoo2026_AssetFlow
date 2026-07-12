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


class Notification(db.Model):
    """
    Tracks notifications sent to employees or departments.
    """
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True) # Target employee
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True) # Scoped department
    
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False) # e.g. Asset Assigned, Maintenance Approved, etc.
    
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('Employee', backref='user_notifications')
    department = db.relationship('Department', backref='dept_notifications')


class AuditLog(db.Model):
    """
    Centrally logs all system, admin, manager and employee actions.
    """
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True) # Who performed the action
    action = db.Column(db.String(255), nullable=False)
    ip_address = db.Column(db.String(45), default='127.0.0.1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('Employee', backref='performed_logs')