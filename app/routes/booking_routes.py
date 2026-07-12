from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from datetime import datetime
from app.database import db
from app.models.asset import Asset
from app.models.booking import ResourceBooking
from app.models.user import Employee

# 1. Define the Resource Booking Blueprint
booking_bp = Blueprint('bookings', __name__)


# ==========================================
# HELPER: OVERLAP VALIDATION FUNCTION
# ==========================================
def check_time_overlap(asset_id, start_time, end_time, exclude_booking_id=None):
    """
    Checks if a requested booking time slot overlaps with any active booking.
    Mathematical Overlap Rule: 
    Existing_Start < Requested_End AND Existing_End > Requested_Start
    """
    query = ResourceBooking.query.filter(
        ResourceBooking.asset_id == asset_id,
        ResourceBooking.status.in_(['Upcoming', 'Ongoing']),
        ResourceBooking.start_time < end_time,
        ResourceBooking.end_time > start_time
    )

    # If rescheduling, exclude the current booking from checking against itself
    if exclude_booking_id:
        query = query.filter(ResourceBooking.id != exclude_booking_id)

    return query.first()


# ==========================================
# 1. JINJA2 TEMPLATE RENDER ROUTE
# ==========================================
@booking_bp.route('/', methods=['GET'])
def booking_page():
    """
    Renders the Resource Booking UI (booking.html) populated with Jinja2 data.
    """
    # Session check guard
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    # Fetch all assets flagged as shared/bookable
    resources = Asset.query.filter_by(is_bookable=True).all()

    # Fetch active user's personal booking history
    user_bookings = ResourceBooking.query.filter_by(
        user_id=session['user_id']
    ).order_by(ResourceBooking.start_time.desc()).all()

    return render_template(
        'booking.html',
        user_name=session.get('user_name', 'Employee'),
        user_role=session.get('user_role', 'Employee'),
        resources=resources,
        user_bookings=user_bookings
    )


# ==========================================
# 2. GET ALL BOOKABLE SHARED RESOURCES (API)
# ==========================================
@booking_bp.route('/resources', methods=['GET'])
def get_bookable_resources():
    """
    Fetches all assets flagged as shared/bookable resources.
    """
    resources = Asset.query.filter_by(is_bookable=True).all()
    result = [{
        "id": r.id,
        "asset_tag": r.asset_tag,
        "name": r.name,
        "location": r.location,
        "condition": r.condition,
        "status": r.status
    } for r in resources]

    return jsonify(result), 200


# ==========================================
# 3. CALENDAR VIEW OF EXISTING BOOKINGS (API)
# ==========================================
@booking_bp.route('/calendar/<int:asset_id>', methods=['GET'])
def get_resource_calendar(asset_id):
    """
    Returns all upcoming/ongoing bookings for a resource formatted for calendar/grid rendering.
    """
    asset = Asset.query.get_or_404(asset_id)
    if not asset.is_bookable:
        return jsonify({"error": "This asset is not marked as a shared bookable resource."}), 400

    bookings = ResourceBooking.query.filter(
        ResourceBooking.asset_id == asset_id,
        ResourceBooking.status.in_(['Upcoming', 'Ongoing'])
    ).all()

    events = []
    for b in bookings:
        user = Employee.query.get(b.user_id)
        events.append({
            "id": b.id,
            "title": f"Booked by {user.name if user else 'Unknown'}",
            "purpose": b.purpose,
            "start": b.start_time.isoformat(),
            "end": b.end_time.isoformat(),
            "status": b.status,
            "user_id": b.user_id
        })

    return jsonify({"asset_id": asset.id, "asset_name": asset.name, "bookings": events}), 200


# ==========================================
# 4. CREATE BOOKING WITH OVERLAP VALIDATION (API)
# ==========================================
@booking_bp.route('/create', methods=['POST'])
def create_booking():
    """
    Creates a new time-slot reservation with strict overlap detection.
    """
    data = request.get_json() or {}

    asset_id = data.get('asset_id')
    start_time_str = data.get('start_time')
    end_time_str = data.get('end_time')
    purpose = data.get('purpose', '')

    user_id = session.get('user_id') or data.get('user_id')

    if not asset_id or not start_time_str or not end_time_str or not user_id:
        return jsonify({"error": "asset_id, start_time, end_time, and user_id are required fields."}), 400

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
    except ValueError:
        return jsonify({"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)."}), 400

    if start_time >= end_time:
        return jsonify({"error": "Booking start time must be before end time."}), 400

    asset = Asset.query.get_or_404(asset_id)
    if not asset.is_bookable:
        return jsonify({"error": "Selected asset is not marked as a shared bookable resource."}), 400

    # CRITICAL: Overlap Validation Check
    conflicting_booking = check_time_overlap(asset.id, start_time, end_time)
    if conflicting_booking:
        conflict_user = Employee.query.get(conflicting_booking.user_id)
        holder_name = conflict_user.name if conflict_user else "another user"
        
        return jsonify({
            "error": f"Requested {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')} - conflict - slot is unavailable (Held by {holder_name})."
        }), 409  # 409 Conflict HTTP Code

    # Create new booking entry
    new_booking = ResourceBooking(
        asset_id=asset.id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
        status='Upcoming'
    )

    db.session.add(new_booking)
    db.session.commit()

    return jsonify({
        "message": f"Successfully reserved '{asset.name}' from {start_time_str} to {end_time_str}.",
        "booking_id": new_booking.id,
        "status": new_booking.status
    }), 201


# ==========================================
# 5. CANCEL BOOKING (API)
# ==========================================
@booking_bp.route('/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking(booking_id):
    """
    Cancels an upcoming or ongoing booking slot.
    """
    booking = ResourceBooking.query.get_or_404(booking_id)

    current_user_id = session.get('user_id')
    current_role = session.get('user_role', 'Employee')

    if current_user_id and booking.user_id != current_user_id and current_role not in ['Admin', 'Asset Manager']:
        return jsonify({"error": "You do not have permission to cancel this booking."}), 403

    if booking.status in ['Completed', 'Cancelled']:
        return jsonify({"error": f"Booking is already {booking.status.lower()}."}), 400

    booking.status = 'Cancelled'
    db.session.commit()

    return jsonify({"message": f"Booking #{booking.id} cancelled successfully."}), 200