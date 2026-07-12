from flask import Flask, redirect, url_for
from app.config import Config
from app.database import db
from .routes.auth_routes import auth_bp

def create_app():
    # 1. Initialize Flask app
    app = Flask(__name__, template_folder='template')

    # 2. Load configurations
    app.config.from_object(Config)

    # 3. Bind SQLAlchemy instance with Flask app
    db.init_app(app)

    # 4. Import & Register Blueprints (Routes)
    from app.routes.auth_routes import auth_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.alloc_routes import alloc_bp
    from app.routes.asset_routes import asset_bp
    from app.routes.booking_routes import booking_bp
    from app.routes.report_routes import report_bp
    from app.routes.notification_routes import notification_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(alloc_bp, url_prefix='/allocations')
    app.register_blueprint(asset_bp, url_prefix='/assets')
    app.register_blueprint(booking_bp, url_prefix='/bookings')
    app.register_blueprint(report_bp, url_prefix='/reports')
    app.register_blueprint(notification_bp, url_prefix='/notifications')

    # Root redirect — '/' → login page
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    # 5. Auto-create MySQL Tables on startup
    with app.app_context():
        # Import all model schemas so SQLAlchemy detects them
        from app.models import user, asset, booking, audit
        
        # Creates all MySQL tables defined in your models if they don't exist
        db.create_all()

    @app.context_processor
    def inject_unread_notif_count():
        from flask import session
        if session.get('user_id'):
            from app.models.audit import Notification
            user_id = session.get('user_id')
            user_role = session.get('user_role')
            if user_role == 'Admin':
                count = Notification.query.filter_by(is_read=False).count()
            elif user_role == 'Asset Manager':
                count = Notification.query.filter(
                    Notification.notification_type.in_(['Asset Assigned', 'Maintenance Approved', 'Audits', 'Transfers']),
                    Notification.is_read == False
                ).count()
            elif user_role == 'Department Head':
                count = Notification.query.filter_by(dept_id=session.get('dept_id'), is_read=False).count()
            else:
                count = Notification.query.filter_by(user_id=user_id, is_read=False).count()
            return dict(unread_notif_count=count)
        return dict(unread_notif_count=0)

    return app