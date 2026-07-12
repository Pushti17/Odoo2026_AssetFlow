from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify
from functools import wraps
from datetime import datetime
from app.database import db
from app.models.user import Employee, Department
from app.models.audit import Notification, AuditLog

notification_bp = Blueprint('notifications', __name__)

# ── Login required decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# Helper to write logs
def log_activity(user_id, action, ip_address='127.0.0.1'):
    try:
        log = AuditLog(user_id=user_id, action=action, ip_address=ip_address)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Logging error:", e)

# Helper to send notifications
def send_notification(title, message, notification_type, user_id=None, dept_id=None):
    try:
        notif = Notification(
            title=title,
            message=message,
            notification_type=notification_type,
            user_id=user_id,
            dept_id=dept_id
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print("Notification send error:", e)

# Seed audit logs if empty
def seed_audit_logs_if_empty(user_id, dept_id):
    if AuditLog.query.count() == 0:
        # Seed Admin logs
        log_activity(1, "Asset AF-0001 (Lenovo ThinkPad) registered in database", "192.168.1.10")
        log_activity(1, "User Vishrut promoted to Administrator role", "192.168.1.10")
        log_activity(1, "Asset Category Laptops warrant period configured to 36 months", "192.168.1.10")
        
        # Seed Manager logs
        log_activity(2, "Asset AF-0114 allocated to Employee Priya", "192.168.1.12")
        log_activity(2, "Maintenance request #4 status set to Approved", "192.168.1.12")
        
        # Seed Dept Head logs
        log_activity(3, "Resource booking confirmed for Team Engineering", "192.168.1.15")
        
        # Seed Employee logs
        log_activity(3, "Booking starts in 30 mins: Conference Room Alpha", "127.0.0.1")
        log_activity(3, "Laptop AF-0114 returned condition checked in as Good", "127.0.0.1")

    if Notification.query.count() == 0:
        # Admin Notifications
        send_notification("New Category Created", "Category Laptops registered in database by Admin", "Asset Assigned")
        send_notification("Audit Cycle Initiated", "Annual IT audit cycle has been initiated", "Audits")
        
        # Dept Head Notifications (dept_id = 1)
        send_notification("Transfer Request Pending", "Transfer request in your dept awaiting approval", "Transfers", dept_id=1)
        send_notification("Team Resource Booking Confirmed", "Booking confirmed for your team in Room B", "Bookings", dept_id=1)
        
        # Employee Notifications (user_id = 3)
        send_notification("Asset Allocated", "Laptop AF-0114 allocated to you", "Asset Assigned", user_id=3)
        send_notification("Booking Reminder", "Booking starts in 30 mins: Meeting Room 4", "Bookings", user_id=3)
        send_notification("Maintenance Request Approved", "Maintenance request #2 has been approved", "Maintenance Approved", user_id=3)
        send_notification("Overdue Return Alert", "Your laptop AF-0114 return is overdue", "Overdue Return Alert", user_id=3)

@notification_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    user = Employee.query.get(user_id)
    dept_id = user.dept_id

    # Seed if needed
    seed_audit_logs_if_empty(user_id, dept_id)

    # 1. POST Action: Mark notifications as read
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'mark_all_read':
            if user_role in ['Admin', 'Asset Manager']:
                Notification.query.filter_by(is_read=False).update({Notification.is_read: True})
            elif user_role == 'Department Head':
                Notification.query.filter_by(dept_id=dept_id, is_read=False).update({Notification.is_read: True})
            else:
                Notification.query.filter_by(user_id=user_id, is_read=False).update({Notification.is_read: True})
            db.session.commit()
            flash("All notifications marked as read.", "success")
        return redirect(url_for('notifications.index'))

    # 2. GET Notifications Scoped
    filter_type = request.args.get('type')

    if user_role == 'Admin':
        notif_query = Notification.query
    elif user_role == 'Asset Manager':
        notif_query = Notification.query.filter(Notification.notification_type.in_(['Asset Assigned', 'Maintenance Approved', 'Audits', 'Transfers']))
    elif user_role == 'Department Head':
        notif_query = Notification.query.filter_by(dept_id=dept_id)
    else: # Employee
        notif_query = Notification.query.filter_by(user_id=user_id)

    if filter_type:
        notif_query = notif_query.filter_by(notification_type=filter_type)

    notifications = notif_query.order_by(Notification.id.desc()).all()

    # 3. GET Audit Logs Scoped
    if user_role in ['Admin', 'Asset Manager']:
        audit_logs = AuditLog.query.order_by(AuditLog.id.desc()).all()
    elif user_role == 'Department Head':
        # Logs matching employees in their department
        audit_logs = AuditLog.query.join(Employee).filter(Employee.dept_id == dept_id).order_by(AuditLog.id.desc()).all()
    else: # Employee
        audit_logs = AuditLog.query.filter_by(user_id=user_id).order_by(AuditLog.id.desc()).all()

    return render_template(
        'notifications.html',
        notifications=notifications,
        audit_logs=audit_logs,
        role=user_role,
        active_type=filter_type
    )
