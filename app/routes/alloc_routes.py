from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from functools import wraps
from datetime import datetime
from app.database import db
from app.models.user import Employee, Department
from app.models.asset import Allocation, Asset, Transfer, Category

alloc_bp = Blueprint('alloc', __name__)

# ── Login required decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@alloc_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    user = Employee.query.get(user_id)
    dept_id = user.dept_id

    # 1. ── GET DATA FILTERED BY ROLE ──
    # Allocations List
    if user_role in ['Admin', 'Asset Manager']:
        active_allocations = Allocation.query.filter_by(is_active=True).all()
        past_allocations = Allocation.query.filter_by(is_active=False).all()
    elif user_role == 'Department Head':
        active_allocations = Allocation.query.join(Employee).filter(
            Employee.dept_id == dept_id,
            Allocation.is_active == True
        ).all()
        past_allocations = Allocation.query.join(Employee).filter(
            Employee.dept_id == dept_id,
            Allocation.is_active == False
        ).all()
    else: # Employee
        active_allocations = Allocation.query.filter_by(employee_id=user_id, is_active=True).all()
        past_allocations = Allocation.query.filter_by(employee_id=user_id, is_active=False).all()

    # Transfers List
    if user_role in ['Admin', 'Asset Manager']:
        pending_transfers = Transfer.query.filter_by(status='Pending').all()
        past_transfers = Transfer.query.filter(Transfer.status.in_(['Approved', 'Rejected'])).all()
    elif user_role == 'Department Head':
        pending_transfers = Transfer.query.join(Asset).filter(
            Asset.dept_id == dept_id,
            Transfer.status == 'Pending'
        ).all()
        past_transfers = Transfer.query.join(Asset).filter(
            Asset.dept_id == dept_id,
            Transfer.status.in_(['Approved', 'Rejected'])
        ).all()
    else: # Employee
        pending_transfers = Transfer.query.filter(
            (Transfer.from_employee_id == user_id) | (Transfer.to_employee_id == user_id),
            Transfer.status == 'Pending'
        ).all()
        past_transfers = Transfer.query.filter(
            ((Transfer.from_employee_id == user_id) | (Transfer.to_employee_id == user_id)),
            Transfer.status.in_(['Approved', 'Rejected'])
        ).all()

    # Options for Dropdowns
    all_assets = Asset.query.all()
    available_assets = Asset.query.filter_by(status='Available').all()
    
    if user_role in ['Admin', 'Asset Manager']:
        employees_list = Employee.query.filter_by(status='Active').all()
    elif user_role == 'Department Head':
        employees_list = Employee.query.filter_by(dept_id=dept_id, status='Active').all()
    else:
        employees_list = [user]

    # 2. ── POST REQUEST ACTIONS ──
    if request.method == 'POST':
        action = request.form.get('action')

        # A. ALLOCATE ASSET
        if action == 'allocate':
            if user_role == 'Employee':
                flash('Employees are not authorized to perform allocations.', 'error')
                return redirect(url_for('alloc.index'))

            target_asset_id = request.form.get('asset_id')
            target_employee_id = request.form.get('employee_id')
            exp_return_str = request.form.get('expected_return_date')
            force_reallocate = request.form.get('force') == 'true'

            # Validate input
            asset = Asset.query.get(target_asset_id)
            emp = Employee.query.get(target_employee_id)
            if not asset or not emp:
                flash('Invalid Asset or Employee selected.', 'error')
                return redirect(url_for('alloc.index'))

            # Check Dept Head restriction
            if user_role == 'Department Head' and emp.dept_id != dept_id:
                flash('You can only allocate assets to employees in your department.', 'error')
                return redirect(url_for('alloc.index'))

            # Check if asset is already allocated (Conflict Check)
            current_alloc = Allocation.query.filter_by(asset_id=asset.id, is_active=True).first()
            if current_alloc:
                # Conflict exists!
                holder_name = current_alloc.employee.name
                
                # Check conflict rules
                if user_role in ['Admin', 'Asset Manager']:
                    # Offer Force-Reallocate or Transfer Request
                    if force_reallocate:
                        # Deactivate old allocation
                        current_alloc.is_active = False
                        current_alloc.returned_date = datetime.utcnow()
                        current_alloc.check_in_notes = f"Force-reallocated to {emp.name} by Admin/Manager"
                        current_alloc.returned_condition = asset.condition

                        # Create new allocation
                        exp_return = datetime.strptime(exp_return_str, '%Y-%m-%d') if exp_return_str else None
                        new_alloc = Allocation(
                            asset_id=asset.id,
                            employee_id=emp.id,
                            assigned_date=datetime.utcnow(),
                            expected_return_date=exp_return,
                            is_active=True
                        )
                        db.session.add(new_alloc)
                        db.session.commit()
                        flash(f'Asset {asset.asset_tag} has been force-reallocated from {holder_name} to {emp.name}.', 'success')
                        return redirect(url_for('alloc.index'))
                    else:
                        # Render conflict resolution selector page
                        return render_template(
                            'alloc_conflict.html',
                            asset=asset,
                            holder=current_alloc.employee,
                            target_emp=emp,
                            exp_return_str=exp_return_str,
                            role=user_role
                        )
                elif user_role == 'Department Head':
                    # Check if currently held employee is in their department
                    if current_alloc.employee.dept_id == dept_id:
                        # Offer Transfer Request only
                        return render_template(
                            'alloc_conflict.html',
                            asset=asset,
                            holder=current_alloc.employee,
                            target_emp=emp,
                            exp_return_str=exp_return_str,
                            role=user_role
                        )
                    else:
                        flash(f'Asset is currently held by {holder_name} in another department. You cannot allocate or request transfers across departments.', 'error')
                        return redirect(url_for('alloc.index'))

            # No conflict - Standard allocation
            exp_return = datetime.strptime(exp_return_str, '%Y-%m-%d') if exp_return_str else None
            new_alloc = Allocation(
                asset_id=asset.id,
                employee_id=emp.id,
                assigned_date=datetime.utcnow(),
                expected_return_date=exp_return,
                is_active=True
            )
            asset.status = 'Allocated'
            db.session.add(new_alloc)
            
            try:
                db.session.commit()
                flash(f'Asset {asset.name} successfully allocated to {emp.name}.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating allocation: {e}', 'error')

        # B. REQUEST TRANSFER
        elif action == 'request_transfer':
            target_asset_id = request.form.get('asset_id')
            to_emp_id = request.form.get('to_employee_id')

            asset = Asset.query.get(target_asset_id)
            to_emp = Employee.query.get(to_emp_id)
            if not asset or not to_emp:
                flash('Invalid parameters for transfer.', 'error')
                return redirect(url_for('alloc.index'))

            current_alloc = Allocation.query.filter_by(asset_id=asset.id, is_active=True).first()
            if not current_alloc:
                flash('Asset is not currently allocated, you can allocate it directly.', 'error')
                return redirect(url_for('alloc.index'))

            from_emp = current_alloc.employee

            # Create transfer request
            new_transfer = Transfer(
                asset_id=asset.id,
                from_employee_id=from_emp.id,
                to_employee_id=to_emp.id,
                status='Pending',
                requested_at=datetime.utcnow()
            )
            db.session.add(new_transfer)
            
            try:
                db.session.commit()
                flash(f'Transfer request for {asset.name} from {from_emp.name} to {to_emp.name} has been raised.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {e}', 'error')

        # C. PROCESS TRANSFER (APPROVE / REJECT)
        elif action in ['approve_transfer', 'reject_transfer']:
            transfer_id = request.form.get('transfer_id')
            transfer = Transfer.query.get(transfer_id)
            if not transfer:
                flash('Transfer request not found.', 'error')
                return redirect(url_for('alloc.index'))

            # Check permissions
            is_authorized = False
            if user_role in ['Admin', 'Asset Manager']:
                is_authorized = True
            elif user_role == 'Department Head':
                # Check if asset belongs to their department
                if transfer.asset.dept_id == dept_id:
                    is_authorized = True
            elif user_role == 'Employee':
                # Only if they currently hold the asset
                if transfer.from_employee_id == user_id:
                    is_authorized = True

            if not is_authorized:
                flash('You are not authorized to process this transfer request.', 'error')
                return redirect(url_for('alloc.index'))

            if action == 'approve_transfer':
                # Close old active allocation
                old_alloc = Allocation.query.filter_by(asset_id=transfer.asset_id, is_active=True).first()
                if old_alloc:
                    old_alloc.is_active = False
                    old_alloc.returned_date = datetime.utcnow()
                    old_alloc.check_in_notes = f"Transferred to {transfer.to_employee.name}"
                    old_alloc.returned_condition = transfer.asset.condition

                # Create new allocation
                new_alloc = Allocation(
                    asset_id=transfer.asset_id,
                    employee_id=transfer.to_employee_id,
                    assigned_date=datetime.utcnow(),
                    is_active=True
                )
                db.session.add(new_alloc)

                transfer.status = 'Approved'
                transfer.processed_at = datetime.utcnow()
                flash('Transfer request approved. Asset has been re-allocated.', 'success')
            else:
                transfer.status = 'Rejected'
                transfer.processed_at = datetime.utcnow()
                flash('Transfer request rejected.', 'success')

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {e}', 'error')

        # D. RETURN ASSET
        elif action == 'return_asset':
            alloc_id = request.form.get('allocation_id')
            notes = request.form.get('check_in_notes', '').strip()
            condition = request.form.get('returned_condition', 'Good')

            alloc = Allocation.query.get(alloc_id)
            if not alloc:
                flash('Allocation record not found.', 'error')
                return redirect(url_for('alloc.index'))

            # Check permissions
            is_authorized = False
            if user_role in ['Admin', 'Asset Manager']:
                is_authorized = True
            elif user_role == 'Department Head':
                if alloc.employee.dept_id == dept_id:
                    is_authorized = True
            elif user_role == 'Employee':
                if alloc.employee_id == user_id:
                    is_authorized = True

            if not is_authorized:
                flash('You are not authorized to return this asset.', 'error')
                return redirect(url_for('alloc.index'))

            # Process return
            alloc.is_active = False
            alloc.returned_date = datetime.utcnow()
            alloc.check_in_notes = notes
            alloc.returned_condition = condition

            # Revert asset status to Available
            alloc.asset.status = 'Available'
            alloc.asset.condition = condition

            try:
                db.session.commit()
                flash(f'Asset {alloc.asset.name} successfully returned. Status is now Available.', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Database error: {e}', 'error')

        return redirect(url_for('alloc.index'))

    return render_template(
        'allocations.html',
        active_allocations=active_allocations,
        past_allocations=past_allocations,
        pending_transfers=pending_transfers,
        past_transfers=past_transfers,
        available_assets=available_assets,
        all_assets=all_assets,
        employees_list=employees_list,
        role=user_role
    )
