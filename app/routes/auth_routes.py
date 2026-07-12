from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app
from datetime import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.database import db
from app.models.user import Employee
from app.models.asset import Allocation, Asset, Category, Transfer
from app.models.booking import ResourceBooking
from app.models.audit import MaintenanceRequest, AuditItem


# ──────────────────────────────────────────
# WTForms
# ──────────────────────────────────────────

class LoginForm(FlaskForm):
    """Login form — email + password."""
    email    = EmailField   ('Email',    validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])


class SignupForm(FlaskForm):
    """Signup form — username, email, password + confirm."""
    username         = StringField ('Username',
                                    validators=[DataRequired(), Length(min=3, max=150)])
    email            = EmailField  ('Email',
                                    validators=[DataRequired(), Email()])
    password         = PasswordField('Password',
                                    validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                    validators=[
                                        DataRequired(),
                                        EqualTo('password', message='Passwords must match.')
                                    ])


class ForgotPasswordForm(FlaskForm):
    """Forgot-password form — email lookup only."""
    email = EmailField('Email', validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    """Reset-password form — new password + confirm."""
    password         = PasswordField('New Password',
                                    validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password',
                                    validators=[
                                        DataRequired(),
                                        EqualTo('password', message='Passwords must match.')
                                    ])


# ──────────────────────────────────────────
# Blueprint
# ──────────────────────────────────────────

auth_bp = Blueprint('auth', __name__)


# ──────────────────────────────────────────
# Helper — session guard decorator
# ──────────────────────────────────────────

def login_required(f):
    """Redirect to /login if user is not authenticated."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════
# 1. SIGNUP  — GET shows form, POST registers
# ══════════════════════════════════════════

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    GET  → render signin.html with blank SignupForm.
    POST → validate → hash password → persist Employee (role='Employee').
    CRITICAL ERP RULE: role is locked to 'Employee' at registration.
    """
    if session.get('user_id'):
        return redirect(url_for('auth.dashboard'))

    form = SignupForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        email    = form.email.data.strip().lower()
        password = form.password.data

        # Guard: email must be unique across all employees
        if Employee.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('signin.html', form=form)

        # Werkzeug — never store plain-text passwords
        hashed = generate_password_hash(password, method='pbkdf2:sha256')

        new_user = Employee(
            name          = username,
            email         = email,
            password_hash = hashed,
            role          = 'Employee',  # Enforced — no self-elevation allowed
            status        = 'Active',
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Database error: {e}', 'error')

    return render_template('signin.html', form=form)


# ══════════════════════════════════════════
# 2. LOGIN  — GET shows form, POST authenticates
# ══════════════════════════════════════════

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET  → render login.html with blank LoginForm.
    POST → validate → verify hash → populate Flask session → redirect dashboard.
    """
    if session.get('user_id'):
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        email    = form.email.data.strip().lower()
        password = form.password.data

        user = Employee.query.filter_by(email=email).first()

        # Werkzeug constant-time hash comparison
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return render_template('login.html', form=form)

        if user.status != 'Active':
            flash('Your account has been deactivated. Contact an administrator.', 'error')
            return render_template('login.html', form=form)

        # Populate Flask session with identity data
        session.clear()
        session['user_id']   = user.id
        session['user_name'] = user.name
        session['user_role'] = user.role
        session['dept_id']   = user.dept_id

        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('login.html', form=form)


# ══════════════════════════════════════════
# 3. LOGOUT
# ══════════════════════════════════════════

@auth_bp.route('/logout')
def logout():
    """Clear Flask session and redirect to login."""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))


# ══════════════════════════════════════════
# Helper — Send Reset Email
# ══════════════════════════════════════════

def send_reset_email(to_email, reset_url):
    """Sends a password reset email using SMTP or logs to console as a fallback."""
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    
    if not mail_username or not mail_password:
        print("\n" + "="*60)
        print("====== RESET PASSWORD EMAIL (FALLBACK CONSOLE LOG) ======")
        print(f"To: {to_email}")
        print(f"Subject: Reset Your AssetFlow Password")
        print(f"Link: {reset_url}")
        print("="*60 + "\n")
        return True

    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@assetflow.com')
        msg['To'] = to_email
        msg['Subject'] = "Reset Your AssetFlow Password"

        body = f"""Hello,

You requested a password reset for your AssetFlow account.
Please click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you did not request this, please ignore this email.
"""
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(
            current_app.config.get('MAIL_SERVER', 'smtp.gmail.com'),
            current_app.config.get('MAIL_PORT', 587)
        )
        if current_app.config.get('MAIL_USE_TLS', True):
            server.starttls()
        server.login(mail_username, mail_password)
        server.sendmail(msg['From'], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# ══════════════════════════════════════════
# 4. FORGOT PASSWORD
# ══════════════════════════════════════════

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    GET  → render forgot_password.html with ForgotPasswordForm.
    POST → validate email → generate secure timed token → send reset email.
    """
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user  = Employee.query.filter_by(email=email).first()

        if user:
            # Generate timed token (expires in 1 hour / 3600 seconds)
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt='password-reset-salt')
            
            # Construct absolute reset URL
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            # Send SMTP or Log
            send_reset_email(email, reset_url)

        # Always show success to prevent email enumeration attacks
        flash(
            'If that email is registered, a password reset link has been sent to your inbox.',
            'success'
        )
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html', form=form)


# ══════════════════════════════════════════
# 5. RESET PASSWORD
# ══════════════════════════════════════════

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    GET  → render reset_password.html with ResetPasswordForm if token is valid.
    POST → validate form → update password hash.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        # Link expires in 1 hour
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = Employee.query.filter_by(email=email).first()
    if not user:
        flash('User not found. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.password_hash = generate_password_hash(
            form.password.data, method='pbkdf2:sha256'
        )

        try:
            db.session.commit()
            flash('Your password has been updated successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            flash('A database error occurred. Please try again.', 'error')

    return render_template('reset_password.html', form=form)


# ══════════════════════════════════════════
# 6. DASHBOARD  — session-guarded landing
# ══════════════════════════════════════════

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """Role-aware dashboard routing."""
    user_id = session.get('user_id')
    user_role = session.get('user_role', 'Employee')
    now_hour = datetime.now().hour

    if user_role in ['Admin', 'Asset Manager']:
        # ── ADMIN / ASSET MANAGER (ORG-WIDE) SCOPE ──
        total_assets = Asset.query.count()
        allocated_count = Allocation.query.filter_by(is_active=True).count()
        maintenance_count = Asset.query.filter_by(status='Under Maintenance').count()
        pending_audits_count = AuditItem.query.filter_by(verification_status='Pending').count()

        # Category distribution breakdown
        category_distribution = db.session.query(
            Category.name.label('category_name'),
            db.func.count(Asset.id).label('asset_count')
        ).join(Asset).group_by(Category.name).all()

        # Recent activities
        recent_allocations = Allocation.query.order_by(Allocation.id.desc()).limit(5).all()
        recent_maintenance = MaintenanceRequest.query.order_by(MaintenanceRequest.id.desc()).limit(5).all()

        # Pending admin approvals
        pending_maintenance = MaintenanceRequest.query.filter_by(status='Pending').all()
        pending_transfers = Transfer.query.filter_by(status='Pending').all()

        return render_template(
            'admin_dashboard.html',
            now_hour=now_hour,
            total_assets=total_assets,
            allocated_count=allocated_count,
            maintenance_count=maintenance_count,
            pending_audits_count=pending_audits_count,
            category_distribution=category_distribution,
            recent_allocations=recent_allocations,
            recent_maintenance=recent_maintenance,
            pending_maintenance=pending_maintenance,
            pending_transfers=pending_transfers
        )
    else:
        # ── EMPLOYEE (PERSONAL) SCOPE ──
        my_allocations = Allocation.query.filter_by(employee_id=user_id, is_active=True).all()
        total_assets = len(my_allocations)
        
        my_bookings = ResourceBooking.query.filter(
            ResourceBooking.user_id == user_id,
            ResourceBooking.status.in_(['Upcoming', 'Ongoing'])
        ).all()
        active_bookings_count = len(my_bookings)
        
        my_maintenance = MaintenanceRequest.query.filter(
            MaintenanceRequest.raised_by_id == user_id,
            MaintenanceRequest.status.notin_(['Resolved', 'Rejected'])
        ).all()
        maintenance_count = len(my_maintenance)
        
        my_audits = AuditItem.query.filter_by(auditor_id=user_id, verification_status='Pending').all()
        pending_audits_count = len(my_audits)
        
        return render_template(
            'dashboard.html',
            now_hour=now_hour,
            total_assets=total_assets,
            active_bookings_count=active_bookings_count,
            maintenance_count=maintenance_count,
            pending_audits_count=pending_audits_count,
            my_allocations=my_allocations,
            my_bookings=my_bookings,
            my_maintenance=my_maintenance,
            my_audits=my_audits
        )
