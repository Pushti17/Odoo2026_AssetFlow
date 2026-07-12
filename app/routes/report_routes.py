from flask import Blueprint, render_template, redirect, url_for, flash, session, Response
from functools import wraps
from datetime import datetime, timedelta
import csv
import io
from app.database import db
from app.models.user import Employee, Department
from app.models.asset import Asset, Category, Allocation, Transfer
from app.models.booking import ResourceBooking
from app.models.audit import MaintenanceRequest

report_bp = Blueprint('reports', __name__)

# ── Login required decorator ──
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@report_bp.route('/', methods=['GET'])
@login_required
def index():
    user_id = session.get('user_id')
    user_role = session.get('user_role')
    user = Employee.query.get(user_id)
    dept_id = user.dept_id

    # 1. ── ORG-WIDE REPORTS (ADMIN / ASSET MANAGER) ──
    if user_role in ['Admin', 'Asset Manager']:
        # Asset Utilization
        total_assets = Asset.query.count()
        allocated_assets = Asset.query.filter_by(status='Allocated').count()
        idle_assets = Asset.query.filter_by(status='Available').count()
        util_rate = round((allocated_assets / total_assets * 100), 1) if total_assets else 0

        # Most used assets (assets with highest allocation counts)
        most_used_query = db.session.query(
            Asset.name, Asset.asset_tag, db.func.count(Allocation.id).label('alloc_count')
        ).join(Allocation).group_by(Asset.id).order_by(db.desc('alloc_count')).limit(5).all()

        # Maintenance Frequency by Category
        maint_by_cat = db.session.query(
            Category.name, db.func.count(MaintenanceRequest.id).label('req_count')
        ).join(Asset, Asset.category_id == Category.id).join(MaintenanceRequest).group_by(Category.id).all()

        # Assets nearing retirement (depreciated value < 10% of acq cost)
        all_assets_acq = Asset.query.filter(Asset.acquisition_cost.isnot(None), Asset.acquisition_date.isnot(None)).all()
        nearing_retirement = []
        for asset in all_assets_acq:
            years = (datetime.now().date() - asset.acquisition_date).days / 365.25
            dep_val = max(0.0, asset.acquisition_cost - (asset.acquisition_cost * (asset.depreciation_rate / 100.0) * years))
            if dep_val < (asset.acquisition_cost * 0.1): # Less than 10%
                nearing_retirement.append({
                    "tag": asset.asset_tag,
                    "name": asset.name,
                    "cost": asset.acquisition_cost,
                    "current_val": round(dep_val, 2),
                    "years": round(years, 1)
                })

        # Department Allocation Summary
        dept_summary = db.session.query(
            Department.name, db.func.count(Asset.id).label('asset_count')
        ).join(Asset).group_by(Department.id).all()

        # Resource booking heatmap (bookings count by hour of day)
        bookings = ResourceBooking.query.all()
        hour_counts = [0] * 24
        for b in bookings:
            hour_counts[b.start_time.hour] += 1
        peak_hours = []
        for hour, count in enumerate(hour_counts):
            if count > 0:
                peak_hours.append({
                    "hour": f"{hour:02d}:00",
                    "count": count
                })
        peak_hours = sorted(peak_hours, key=lambda x: x['count'], reverse=True)[:5]

        return render_template(
            'reports.html',
            role=user_role,
            total_assets=total_assets,
            allocated_assets=allocated_assets,
            idle_assets=idle_assets,
            util_rate=util_rate,
            most_used_assets=most_used_query,
            maint_by_cat=maint_by_cat,
            nearing_retirement=nearing_retirement[:5],
            dept_summary=dept_summary,
            peak_hours=peak_hours
        )

    # 2. ── DEPARTMENT-SCOPED REPORTS (DEPARTMENT HEAD) ──
    elif user_role == 'Department Head':
        dept_name = user.assigned_department.name if user.assigned_department else "your Department"
        
        # Assets in my department
        dept_assets = Asset.query.filter_by(dept_id=dept_id).all()
        dept_assets_count = len(dept_assets)

        # Allocated vs Available inside department
        dept_allocated = Asset.query.filter_by(dept_id=dept_id, status='Allocated').count()
        dept_idle = Asset.query.filter_by(dept_id=dept_id, status='Available').count()
        dept_util = round((dept_allocated / dept_assets_count * 100), 1) if dept_assets_count else 0

        # Department Maintenance requests
        dept_maint = MaintenanceRequest.query.join(Asset).filter(Asset.dept_id == dept_id).all()
        maint_count = len(dept_maint)
        maint_resolved = len([r for r in dept_maint if r.status == 'Resolved'])
        maint_pending = len([r for r in dept_maint if r.status == 'Pending'])

        # Department Bookings
        dept_bookings = ResourceBooking.query.join(Employee, ResourceBooking.user_id == Employee.id).filter(
            Employee.dept_id == dept_id
        ).all()
        bookings_count = len(dept_bookings)

        # Department Audits summary
        from app.models.audit import AuditItem
        dept_audits = AuditItem.query.join(Asset).filter(Asset.dept_id == dept_id).all()
        audits_count = len(dept_audits)
        audits_verified = len([a for a in dept_audits if a.verification_status == 'Verified'])
        audits_discrepant = len([a for a in dept_audits if a.verification_status == 'Discrepancy'])

        return render_template(
            'reports.html',
            role=user_role,
            dept_name=dept_name,
            dept_assets_count=dept_assets_count,
            dept_allocated=dept_allocated,
            dept_idle=dept_idle,
            dept_util=dept_util,
            maint_count=maint_count,
            maint_resolved=maint_resolved,
            maint_pending=maint_pending,
            bookings_count=bookings_count,
            audits_count=audits_count,
            audits_verified=audits_verified,
            audits_discrepant=audits_discrepant
        )

    # 3. ── PERSONAL SCOPE (EMPLOYEE - V2 ENHANCEMENT) ──
    else:
        # My active allocations
        my_allocations = Allocation.query.filter_by(employee_id=user_id).all()
        total_my_allocs = len(my_allocations)
        active_my_allocs = len([a for a in my_allocations if a.is_active])

        # On-time return rate calculation
        completed_allocs = [a for a in my_allocations if not a.is_active and a.returned_date]
        on_time_returns = 0
        for alloc in completed_allocs:
            if not alloc.expected_return_date or alloc.returned_date <= alloc.expected_return_date:
                on_time_returns += 1
        
        on_time_rate = round((on_time_returns / len(completed_allocs) * 100), 1) if completed_allocs else 100.0

        # My total bookings count
        my_bookings_count = ResourceBooking.query.filter_by(user_id=user_id).count()

        # My raised maintenance requests count
        my_maint_requests = MaintenanceRequest.query.filter_by(raised_by_id=user_id).all()
        my_maint_count = len(my_maint_requests)
        my_maint_resolved = len([r for r in my_maint_requests if r.status == 'Resolved'])

        return render_template(
            'reports.html',
            role=user_role,
            total_my_allocs=total_my_allocs,
            active_my_allocs=active_my_allocs,
            on_time_rate=on_time_rate,
            my_bookings_count=my_bookings_count,
            my_maint_count=my_maint_count,
            my_maint_resolved=my_maint_resolved
        )

# ── CSV CUSTOM EXPORTS ENDPOINT ──
@report_bp.route('/export/<string:export_type>')
@login_required
def export_csv(export_type):
    user_role = session.get('user_role')
    if user_role not in ['Admin', 'Asset Manager']:
        flash('Only admins and asset managers can export system data.', 'error')
        return redirect(url_for('reports.index'))

    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == 'assets':
        # Header
        writer.writerow(['Asset Tag', 'Asset Name', 'Category', 'Serial Number', 'Acquisition Date', 'Cost', 'Condition', 'Location', 'Status'])
        assets = Asset.query.all()
        for a in assets:
            writer.writerow([
                a.asset_tag, a.name, a.category.name, a.serial_number or 'N/A',
                a.acquisition_date.strftime('%Y-%m-%d') if a.acquisition_date else 'N/A',
                a.acquisition_cost or 0.0, a.condition, a.location or 'N/A', a.status
            ])
        filename = "assets_directory_export.csv"

    elif export_type == 'allocations':
        writer.writerow(['Asset Tag', 'Asset Name', 'Allocated To', 'Email', 'Assigned Date', 'Expected Return', 'Returned Date', 'Check-in Notes'])
        allocs = Allocation.query.all()
        for al in allocs:
            writer.writerow([
                al.asset.asset_tag, al.asset.name, al.employee.name, al.employee.email,
                al.assigned_date.strftime('%Y-%m-%d %H:%M'),
                al.expected_return_date.strftime('%Y-%m-%d') if al.expected_return_date else 'Permanent',
                al.returned_date.strftime('%Y-%m-%d %H:%M') if al.returned_date else 'Active',
                al.check_in_notes or '-'
            ])
        filename = "allocations_history_export.csv"

    elif export_type == 'maintenance':
        writer.writerow(['Request ID', 'Asset Tag', 'Asset Name', 'Raised By', 'Priority', 'Status', 'Description', 'Created At'])
        reqs = MaintenanceRequest.query.all()
        for r in reqs:
            writer.writerow([
                r.id, r.asset.asset_tag, r.asset.name, r.raised_by.name,
                r.priority, r.status, r.description, r.created_at.strftime('%Y-%m-%d %H:%M')
            ])
        filename = "maintenance_log_export.csv"

    else:
        flash('Invalid export request.', 'error')
        return redirect(url_for('reports.index'))

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )
