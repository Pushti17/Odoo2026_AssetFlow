from flask import Blueprint, render_template, redirect, url_for, flash, session
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db
from app.models.user import Employee


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
# 4. FORGOT PASSWORD
# ══════════════════════════════════════════

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    GET  → render forgot_password.html with ForgotPasswordForm.
    POST → validate email → if found, store email in session and redirect
           to reset page (in production, this would send a reset email).
    """
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user  = Employee.query.filter_by(email=email).first()

        # Always show a success message to avoid user enumeration attacks
        if user:
            # In production: generate a secure token, email a reset link.
            # Here we store the user_id in session for the reset step.
            session['reset_user_id'] = user.id

        flash(
            'If that email is registered, a reset link has been sent. '
            'Check your inbox.',
            'success'
        )
        # Redirect to reset form only if user actually exists
        if user:
            return redirect(url_for('auth.reset_password'))
        return redirect(url_for('auth.forgot_password'))

    return render_template('forgot_password.html', form=form)


# ══════════════════════════════════════════
# 5. RESET PASSWORD
# ══════════════════════════════════════════

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """
    GET  → render reset_password.html with ResetPasswordForm.
    POST → validate → hash new password → update Employee record.
    Requires 'reset_user_id' to be present in session (set by forgot_password).
    """
    reset_uid = session.get('reset_user_id')
    if not reset_uid:
        flash('Invalid or expired reset session. Please try again.', 'error')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user = Employee.query.get(reset_uid)
        if not user:
            flash('User not found. Please try again.', 'error')
            return redirect(url_for('auth.forgot_password'))

        user.password_hash = generate_password_hash(
            form.password.data, method='pbkdf2:sha256'
        )

        try:
            db.session.commit()
            session.pop('reset_user_id', None)  # Invalidate reset session
            flash('Password updated successfully! You can now log in.', 'success')
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
    """Session-guarded dashboard placeholder."""
    return (
        f"<h2>Welcome, {session['user_name']}!</h2>"
        f"<p>Role: {session['user_role']}</p>"
        f"<a href='{url_for('auth.logout')}'>Logout</a>"
    )
