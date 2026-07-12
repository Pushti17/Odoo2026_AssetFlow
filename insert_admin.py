from app import create_app
from app.database import db
from app.models.user import Employee
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # Check if admin already exists
    email = 'admin@assetflow.com'
    admin = Employee.query.filter_by(email=email).first()
    
    if admin:
        print(f"Admin user already exists with email: {email}")
    else:
        password = 'adminpassword'
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        
        new_admin = Employee(
            name='Admin User',
            email=email,
            password_hash=hashed_pw,
            role='Admin',
            status='Active'
        )
        
        try:
            db.session.add(new_admin)
            db.session.commit()
            print("Successfully inserted admin employee into the database!")
            print(f"Email: {email}")
            print(f"Password: {password}")
            print("Role: Admin")
        except Exception as e:
            db.session.rollback()
            print(f"Error inserting admin user: {e}")
