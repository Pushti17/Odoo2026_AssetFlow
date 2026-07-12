from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from functools import wraps
from app.database import db
from app.models.user import Employee, Department
from app.models.asset import Category

admin_bp = Blueprint('admin', __name__)

# ── Decorator to enforce Admin-only access ──
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        if session.get('user_role') != 'Admin':
            flash('Access denied. Administrators only.', 'error')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route('/org-setup', methods=['GET', 'POST'])
@admin_required
def org_setup():
    # Fetch active lists for UI rendering
    departments = Department.query.all()
    categories = Category.query.all()
    employees = Employee.query.all()
    
    # Active options for dropdowns
    active_employees = Employee.query.filter_by(status='Active').all()
    active_depts = Department.query.filter_by(status='Active').all()

    # Determine active tab from request args (default to Tab A)
    active_tab = request.args.get('tab', 'departments')

    if request.method == 'POST':
        action = request.form.get('action')

        # ── DEPARTMENT ACTIONS ──
        if action == 'add_department':
            name = request.form.get('name', '').strip()
            code = request.form.get('code', '').strip().upper()
            parent_id = request.form.get('parent_dept_id')
            head_id = request.form.get('head_id')
            status = request.form.get('status', 'Active')

            if not name or not code:
                flash('Department name and code are required.', 'error')
                return redirect(url_for('admin.org_setup', tab='departments'))

            # Check uniqueness
            if Department.query.filter((Department.name == name) | (Department.code == code)).first():
                flash('Department name or code already exists.', 'error')
                return redirect(url_for('admin.org_setup', tab='departments'))

            parent_dept_id = int(parent_id) if parent_id and parent_id != 'None' else None
            dept_head_id = int(head_id) if head_id and head_id != 'None' else None

            new_dept = Department(
                name=name,
                code=code,
                parent_dept_id=parent_dept_id,
                head_id=dept_head_id,
                status=status
            )
            db.session.add(new_dept)
            
            # If a head is assigned, update their role to 'Department Head'
            if dept_head_id:
                head_emp = Employee.query.get(dept_head_id)
                if head_emp and head_emp.role == 'Employee':
                    head_emp.role = 'Department Head'
                    
            try:
                db.session.commit()
                flash('Department created successfully.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {e}', 'error')

        elif action == 'edit_department':
            dept_id = request.form.get('dept_id')
            dept = Department.query.get(dept_id)
            if dept:
                dept.name = request.form.get('name', '').strip()
                parent_id = request.form.get('parent_dept_id')
                head_id = request.form.get('head_id')
                dept.status = request.form.get('status', 'Active')

                # Avoid self-referencing hierarchy loops
                selected_parent_id = int(parent_id) if parent_id and parent_id != 'None' else None
                if selected_parent_id == dept.id:
                    flash('A department cannot be its own parent.', 'error')
                    return redirect(url_for('admin.org_setup', tab='departments'))

                dept.parent_dept_id = selected_parent_id
                
                # Check head change
                old_head_id = dept.head_id
                new_head_id = int(head_id) if head_id and head_id != 'None' else None
                dept.head_id = new_head_id

                # Update Employee Roles accordingly
                if old_head_id and old_head_id != new_head_id:
                    # Demote old head back to Employee if they are not head of another dept
                    other_depts = Department.query.filter(Department.id != dept.id, Department.head_id == old_head_id).first()
                    if not other_depts:
                        old_head = Employee.query.get(old_head_id)
                        if old_head and old_head.role == 'Department Head':
                            old_head.role = 'Employee'

                if new_head_id:
                    new_head = Employee.query.get(new_head_id)
                    if new_head and new_head.role == 'Employee':
                        new_head.role = 'Department Head'

                try:
                    db.session.commit()
                    flash('Department updated successfully.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Database error: {e}', 'error')

        # ── CATEGORY ACTIONS ──
        elif action == 'add_category':
            name = request.form.get('name', '').strip()
            warranty = request.form.get('warranty_period_months')

            if not name:
                flash('Category name is required.', 'error')
                return redirect(url_for('admin.org_setup', tab='categories'))

            if Category.query.filter_by(name=name).first():
                flash('Category already exists.', 'error')
                return redirect(url_for('admin.org_setup', tab='categories'))

            warranty_period = int(warranty) if warranty and warranty.strip() else None
            new_cat = Category(name=name, warranty_period_months=warranty_period)
            db.session.add(new_cat)
            
            try:
                db.session.commit()
                flash('Asset Category created successfully.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {e}', 'error')

        elif action == 'edit_category':
            cat_id = request.form.get('cat_id')
            cat = Category.query.get(cat_id)
            if cat:
                cat.name = request.form.get('name', '').strip()
                warranty = request.form.get('warranty_period_months')
                cat.warranty_period_months = int(warranty) if warranty and warranty.strip() else None
                
                try:
                    db.session.commit()
                    flash('Category updated successfully.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Database error: {e}', 'error')

        # ── EMPLOYEE ACTIONS ──
        elif action == 'edit_employee':
            emp_id = request.form.get('employee_id')
            emp = Employee.query.get(emp_id)
            if emp:
                dept_id = request.form.get('dept_id')
                role = request.form.get('role')
                status = request.form.get('status')

                emp.dept_id = int(dept_id) if dept_id and dept_id != 'None' else None
                emp.role = role
                emp.status = status

                try:
                    db.session.commit()
                    flash('Employee record updated successfully.', 'success')
                except Exception as e:
                    db.session.rollback()
                    flash(f'Database error: {e}', 'error')

        return redirect(url_for('admin.org_setup', tab=active_tab))

    return render_template(
        'org_setup.html',
        departments=departments,
        categories=categories,
        employees=employees,
        active_employees=active_employees,
        active_depts=active_depts,
        active_tab=active_tab
    )
