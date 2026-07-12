from datetime import datetime
from app.database import db

class Department(db.Model):
    """
    Department Management Master Table.
    Maintains administrative groups and tracking ownership inside the ERP system.
    """
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True) # e.g., 'DEPT-ENG', 'DEPT-HR'
    
    # Hierarchy handling: Self-referential relationship for optional Parent Departments
    parent_dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # Department Head mapping: Tracks which employee runs the department
    head_id = db.Column(db.Integer, db.ForeignKey('employees.id', use_alter=True, name='fk_dept_head_id'), nullable=True)
    
    # Status flags: Active / Inactive
    status = db.Column(db.String(20), default='Active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    # Resolves self-referential children hierarchies
    sub_departments = db.relationship('Department', backref=db.backref('parent_department', remote_side=[id]))
    # Fetches all employees tied directly to this specific department
    members = db.relationship('Employee', foreign_keys='Employee.dept_id', backref='assigned_department', lazy=True)


class Employee(db.Model):
    """
    Employee Directory Master Table.
    Stores authentication parameters and access roles for the system framework.
    """
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False) # Cryptographic secure string store
    
    # Link employee to their assigned home department
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    
    # Role-Based Access Control (RBAC): 'Admin', 'Asset Manager', 'Department Head', 'Employee'
    role = db.Column(db.String(50), default='Employee', nullable=False, index=True)
    
    # Status configuration parameters: Active / Inactive
    status = db.Column(db.String(20), default='Active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to get the departments managed by this person (if applicable)
    managed_departments = db.relationship('Department', foreign_keys='Department.head_id', backref='department_head', lazy=True)