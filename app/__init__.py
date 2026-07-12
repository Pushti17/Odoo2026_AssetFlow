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
    #from app.routes.admin_routes import admin_routes_bp
    #from app.routes.asset_routes import asset_bp
    #from app.routes.alloc_routes import alloc_bp
    #from app.routes.booking_routes import booking_bp
    #from app.routes.audit_routes import audit_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    #app.register_blueprint(admin_routes_bp, url_prefix='/admin')
    #app.register_blueprint(asset_bp, url_prefix='/assets')
    #app.register_blueprint(alloc_bp, url_prefix='/allocations')
    #app.register_blueprint(booking_bp, url_prefix='/bookings')
    #app.register_blueprint(audit_bp, url_prefix='/audits')

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

    return app