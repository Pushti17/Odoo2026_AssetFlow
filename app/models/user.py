from datetime import datetime
from app.database import db

class Department(db.Model):
    """
    Department Management Master Table.
    Maintains organizational hierarchy and administrative groups.
    """
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True) # e.g., 'DEPT-ENG', 'DEPT-HR'
    
    # Hierarchy handling: Optional Parent Department for sub-departments
    parent_dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # Department Head mapping
    head_id = db.Column(db.Integer, db.ForeignKey('employees.id', use_alter=True, name='fk_dept_head_id'), nullable=True)
    
    status = db.Column(db.String(20), default='Active', nullable=False) # Active / Inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sub_departments = db.relationship('Department', backref=db.backref('parent_department', remote_side=[id]))
    members = db.relationship('Employee', foreign_keys='Employee.dept_id', backref='assigned_department', lazy=True)


class Employee(db.Model):
    """
    Employee Directory Master Table.
    Stores authentication parameters and access roles for RBAC.
    """
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # Role-Based Access Control: 'Admin', 'Asset Manager', 'Department Head', 'Employee'
    role = db.Column(db.String(50), default='Employee', nullable=False, index=True)
    
    status = db.Column(db.String(20), default='Active', nullable=False) # Active / Inactive
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Managed departments relationship
    managed_departments = db.relationship('Department', foreign_keys='Department.head_id', backref='department_head', lazy=True)