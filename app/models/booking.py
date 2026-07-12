from datetime import datetime
from app.database import db

class ResourceBooking(db.Model):
    """
    Manages time-slot reservations for shared resources with overlap validation.
    """
    __tablename__ = 'resource_bookings'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('assets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    
    purpose = db.Column(db.String(255), nullable=True)
    
    # Statuses: Upcoming, Ongoing, Completed, Cancelled
    status = db.Column(db.String(20), default='Upcoming', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('Employee', backref='resource_bookings')