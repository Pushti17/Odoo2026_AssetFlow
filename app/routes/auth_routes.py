from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db
from app.models.user import Employee  # Implemented under Developer A's tasks

# 1. Define the Authentication Blueprint
auth_bp = Blueprint('auth', __name__)

# ==========================================
# 1. USER SIGNUP ENDPOINT
# ==========================================
@auth_bp.route('/signup', methods=['POST'])
def signup():
    """
    Registers a new user in the system.
    CRITICAL ERP RULE: All custom signups default strictly to the 'Employee' role.
    No role selection is allowed at signup to prevent self-elevation.
    """
    data = request.get_json() or {}
    
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    dept_id = data.get('dept_id')  # Optional during initial onboarding

    # Basic input validation
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required fields."}), 400

    # Check if the email is already registered in the system
    existing_employee = Employee.query.filter_by(email=email).first()
    if existing_employee:
        return jsonify({"error": "An account with this email already exists."}), 409

    # Generate a secure salted password hash (Never store raw text)
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Enforce default non-elevated role 'Employee'
    new_user = Employee(
        name=name,
        email=email,
        password_hash=hashed_password,
        dept_id=dept_id,
        role='Employee',  # Enforced business logic constraint
        status='Active'   # Accounts are active by default upon creation
    )

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({
            "message": "Account created successfully as 'Employee'. Contact your Admin for role updates.",
            "user_id": new_user.id
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error occurred during registration."}), 500


# ==========================================
# 2. USER LOGIN ENDPOINT
# ==========================================
@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticates an employee, verifies password hash, and stores state inside a secure session.
    """
    data = request.get_json() or {}
    
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    # Query the user from the database
    user = Employee.query.filter_by(email=email).first()

    # Safety rule: Verify user exists and check the cryptographic hash matches
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password configuration."}), 401

    # Check if the employee directory profile is marked active
    if user.status != 'Active':
        return jsonify({"error": "Your account profile has been deactivated. Contact an administrator."}), 403

    # Initialize session validation parameters
    session.clear()
    session['user_id'] = user.id
    session['user_name'] = user.name
    session['user_role'] = user.role
    session['dept_id'] = user.dept_id

    return jsonify({
        "message": f"Welcome back, {user.name}!",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "dept_id": user.dept_id
        }
    }), 200


# ==========================================
# 3. USER LOGOUT ENDPOINT
# ==========================================
@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    Clears the active session tokens, effectively logging out the user.
    """
    session.clear()
    return jsonify({"message": "Logged out successfully. Session tokens cleared."}), 200


# ==========================================
# 4. SESSION AUTHENTICATION GUARD HELPER
# ==========================================
@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """
    Helper endpoint for the frontend to check if the current browser session remains active.
    """
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"authenticated": False}), 401

    user = Employee.query.get(user_id)
    if not user or user.status != 'Active':
        session.clear()
        return jsonify({"authenticated": False}), 401

    return jsonify({
        "authenticated": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "dept_id": user.dept_id
        }
    }), 200