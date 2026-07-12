from flask import Blueprint, render_template, redirect, url_for, flash, session, request, jsonify
from functools import wraps
from datetime import datetime
from app.database import db
from app.models.user import Employee, Department
from app.models.asset import Asset, Category, Allocation
from app.models.audit import MaintenanceRequest

asset_bp = Blueprint('asset', __name__)

# ── Login required decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@asset_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    user = Employee.query.get(user_id)
    dept_id = user.dept_id

    # 1. ── REGISTER ASSET (POST) ──
    if request.method == 'POST':
        if user_role not in ['Admin', 'Asset Manager']:
            flash('You do not have permission to register assets.', 'error')
            return redirect(url_for('asset.index'))

        name = request.form.get('name', '').strip()
        category_id = request.form.get('category_id')
        serial_number = request.form.get('serial_number', '').strip() or None
        acquisition_date_str = request.form.get('acquisition_date')
        acquisition_cost_str = request.form.get('acquisition_cost')
        condition = request.form.get('condition', 'Good')
        location = request.form.get('location', '').strip()
        is_bookable = request.form.get('is_bookable') == 'true'
        photo_url = request.form.get('photo_url', '').strip() or None
        depreciation_str = request.form.get('depreciation_rate')

        if not name or not category_id:
            flash('Name and Category are required.', 'error')
            return redirect(url_for('asset.index'))

        # Generate asset tag AF-0001
        asset_tag = Asset.generate_asset_tag()

        # Parse numbers & dates
        acq_date = datetime.strptime(acquisition_date_str, '%Y-%m-%d').date() if acquisition_date_str else None
        acq_cost = float(acquisition_cost_str) if acquisition_cost_str else None
        depreciation = float(depreciation_str) if depreciation_str else 10.0

        new_asset = Asset(
            asset_tag=asset_tag,
            serial_number=serial_number,
            name=name,
            category_id=category_id,
            acquisition_date=acq_date,
            acquisition_cost=acq_cost,
            condition=condition,
            location=location,
            is_bookable=is_bookable,
            photo_url=photo_url,
            depreciation_rate=depreciation,
            status='Available'
        )
        db.session.add(new_asset)
        
        try:
            db.session.commit()
            flash(f'Asset {asset_tag} successfully registered.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering asset: {e}', 'error')
        return redirect(url_for('asset.index'))

    # 2. ── SEARCH & FILTERING ──
    q = request.args.get('q', '').strip()
    cat_filter = request.args.get('category')
    status_filter = request.args.get('status')
    location_filter = request.args.get('location', '').strip()

    query = Asset.query

    # Apply role scope restrictions
    if user_role == 'Department Head':
        # Can only view their own department's assets
        query = query.filter_by(dept_id=dept_id)
    elif user_role == 'Employee':
        # Can only see personal (allocated to them) + shared/bookable assets
        personal_allocations = Allocation.query.filter_by(employee_id=user_id, is_active=True).all()
        personal_asset_ids = [alloc.asset_id for alloc in personal_allocations]
        query = query.filter(
            (Asset.id.in_(personal_asset_ids)) | (Asset.is_bookable == True)
        )

    # Search query
    if q:
        query = query.filter(
            (Asset.asset_tag.like(f'%{q}%')) |
            (Asset.serial_number.like(f'%{q}%')) |
            (Asset.name.like(f'%{q}%')) |
            (Asset.location.like(f'%{q}%'))
        )

    if cat_filter:
        query = query.filter_by(category_id=cat_filter)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if location_filter:
        query = query.filter(Asset.location.like(f'%{location_filter}%'))

    assets = query.all()
    categories = Category.query.all()

    return render_template(
        'assets.html',
        assets=assets,
        categories=categories,
        role=user_role,
        q=q,
        cat_filter=cat_filter,
        status_filter=status_filter,
        location_filter=location_filter
    )

@asset_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit(id):
    user_role = session.get('user_role')
    if user_role not in ['Admin', 'Asset Manager']:
        flash('You do not have permission to edit assets.', 'error')
        return redirect(url_for('asset.index'))

    asset = Asset.query.get_or_404(id)
    asset.name = request.form.get('name', '').strip()
    asset.category_id = request.form.get('category_id')
    asset.serial_number = request.form.get('serial_number', '').strip() or None
    
    acq_date_str = request.form.get('acquisition_date')
    asset.acquisition_date = datetime.strptime(acq_date_str, '%Y-%m-%d').date() if acq_date_str else None
    
    acq_cost_str = request.form.get('acquisition_cost')
    asset.acquisition_cost = float(acq_cost_str) if acq_cost_str else None
    
    asset.condition = request.form.get('condition', 'Good')
    asset.location = request.form.get('location', '').strip()
    asset.is_bookable = request.form.get('is_bookable') == 'true'
    asset.photo_url = request.form.get('photo_url', '').strip() or None
    
    depreciation_str = request.form.get('depreciation_rate')
    asset.depreciation_rate = float(depreciation_str) if depreciation_str else 10.0

    try:
        db.session.commit()
        flash(f'Asset {asset.asset_tag} updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating asset: {e}', 'error')

    return redirect(url_for('asset.index'))

@asset_bp.route('/retire/<int:id>', methods=['POST'])
@login_required
def retire(id):
    user_role = session.get('user_role')
    if user_role not in ['Admin', 'Asset Manager']:
        flash('You do not have permission to retire or dispose assets.', 'error')
        return redirect(url_for('asset.index'))

    asset = Asset.query.get_or_404(id)
    action = request.form.get('retire_action', 'Retired') # Retired or Disposed

    # Ensure it's not active in allocations
    active_alloc = Allocation.query.filter_by(asset_id=asset.id, is_active=True).first()
    if active_alloc:
        flash('Cannot retire asset while it is currently allocated.', 'error')
        return redirect(url_for('asset.index'))

    asset.status = action
    
    try:
        db.session.commit()
        flash(f'Asset {asset.asset_tag} status updated to {action}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Database error: {e}', 'error')

    return redirect(url_for('asset.index'))

@asset_bp.route('/details/<int:id>')
@login_required
def details(id):
    user_role = session.get('user_role')
    user_id = session.get('user_id')
    user = Employee.query.get(user_id)
    dept_id = user.dept_id

    asset = Asset.query.get_or_404(id)

    # Scoping checks
    if user_role == 'Department Head' and asset.dept_id != dept_id:
        flash('You can only view assets in your department.', 'error')
        return redirect(url_for('asset.index'))
    elif user_role == 'Employee':
        # Check if allocated to them or shared
        active_alloc = Allocation.query.filter_by(asset_id=asset.id, employee_id=user_id, is_active=True).first()
        if not active_alloc and not asset.is_bookable:
            flash('Access denied.', 'error')
            return redirect(url_for('asset.index'))

    # Load history
    allocations_history = Allocation.query.filter_by(asset_id=asset.id).order_by(Allocation.id.desc()).all()
    maintenance_history = MaintenanceRequest.query.filter_by(asset_id=asset.id).order_by(MaintenanceRequest.id.desc()).all()

    # Calculate dynamic depreciation value: Cost - (Cost * (depreciation_rate/100) * years)
    years_since_acq = 0
    depreciated_value = asset.acquisition_cost or 0.0
    if asset.acquisition_date and asset.acquisition_cost:
        years_since_acq = (datetime.now().date() - asset.acquisition_date).days / 365.25
        # Linear depreciation
        depreciated_value = max(0.0, asset.acquisition_cost - (asset.acquisition_cost * (asset.depreciation_rate / 100.0) * years_since_acq))

    return render_template(
        'asset_details.html',
        asset=asset,
        allocations_history=allocations_history,
        maintenance_history=maintenance_history,
        years_since_acq=round(years_since_acq, 2),
        depreciated_value=round(depreciated_value, 2),
        role=user_role
    )
