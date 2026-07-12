AssetFlow - Enterprise Asset Lifecycle & Resource Management ERP

================================================================================
TECHNICAL ARCHITECTURE AND TECH STACK
Framework and Language
• Python 3.10+: Core programming language utilized for backend development due to its robustness, clean module structure, and rich library ecosystem.
• Flask: Micro web framework used to construct modular API blueprints, application factories, session authentication, and Jinja2 view rendering.

Database and Persistence
• MySQL 8.0: 
• Flask-SQLAlchemy: Object-Relational Mapping (ORM) framework 

Security and Cryptography
• Werkzeug Security: Cryptographic library used to generate salted password hashes (pbkdf2:sha256) during registration and verify hashes during login, ensuring raw passwords are never saved in database storage.
• Cryptography: Utility package required by PyMySQL to facilitate modern, encrypted authentication handshake protocols with modern MySQL 8.0+ deployments.
• python-dotenv: Environment isolation library used to parse environment variables from non-tracked .env files, preventing API secrets and database passwords from being committed to version control.

Frontend and Rendering
• Jinja2: Server-side templating engine used for dynamic HTML generation, session-aware navbar injection, and conditional UI rendering based on active user roles.
• Tailwind CSS (CDN): Utility-first CSS framework used for responsive layout structuring and UI components.

================================================================================
WHY THIS STACK?
Relational Data Integrity
Asset management relies heavily on relational mappings. For example, an Allocation belongs to an Asset AND an Employee, while a Department belongs to a Parent Department. MySQL combined with SQLAlchemy foreign key constraints guarantees data consistency and prevents orphaned records.

Modular Blueprint Architecture
Splitting business logic across domain-specific blueprints (auth_routes, admin_routes, asset_routes, alloc_routes, booking_routes, audit_routes) ensures separation of concerns and allows parallel development across project contributors.

Preventive Validation Engine
Shared resource management requires strict mathematical checking (Start_1 < End_2 AND End_1 > Start_2) to reject schedule conflicts at the database query layer before commit execution.

================================================================================
KEY FEATURES AND FUNCTIONAL MODULES
Authentication and Role Governance
• Self-service employee signup defaulting exclusively to the non-elevated Employee role.
• Secure login, session state initialization, and session termination endpoints.
• Admin-only role promotion endpoint for designating Asset Manager and Department Head profiles.

Organization Setup (Admin Console)
• Department Management: Create and structure organizational departments, map Department Heads, set active/inactive flags, and support multi-level parent/child hierarchies.
• Category Management: Configure asset categories (e.g., Electronics, Vehicles, Furniture) and set default warranty periods.
• Employee Directory: Centralized view of all system users, account statuses, and assigned departments.

Asset Master and Lifecycle Tracking
• Automatic incremental Asset Tag generation (e.g., AF-0001, AF-0002).
• Lifecycle status tracking (Available, Allocated, Reserved, Under Maintenance, Lost, Retired, Disposed).
• Search and filter interface by Tag, Serial Number, Category, Department, or Physical Location.
• Detailed lifecycle logs tracking allocation history and repair requests.

Allocation, Return, and Transfer Workflow
• Asset assignment to employees with expected return dates.
• Double-allocation prevention: Blocks checkout if an asset is currently marked as held by another user.
• Peer-to-peer transfer request workflow requiring approval before re-allocation.
• Return check-in processing with condition note logging and automatic status reset to Available.

Resource Booking (Shared Resources)
• Time-slot scheduling interface for shared resources (e.g., Conference Rooms, Shared Equipment).
• Mathematical overlap detection blocking conflicting reservations for the same asset.
• Schedule calendar grid rendering available and occupied slots.
• Cancellation and slot rescheduling workflows.

Maintenance and Verification Audits
• Maintenance ticket submission for damaged or malfunctioning assets.
• Approval workflow for Asset Managers to transition assets to Under Maintenance and restore them to Available upon resolution.
• Audit cycle creation and physical verification logs to identify lost or missing inventory.

================================================================================
LOCAL SETUP AND INSTALLATION
Prerequisites:
• Python 3.10 or higher installed.
• MySQL Server running locally or accessible via network.

Clone Repository and Setup Virtual Environment
git clone https://github.com/YourRepo/AssetFlow.git
cd AssetFlow

python -m venv venv
venv\Scripts\activate

Install Dependencies
pip install -r requirements.txt

Configure Database and Environment
a. Create a MySQL database instance:
CREATE DATABASE assetflow_db;

b. Create a .env file in the root directory (refer to .env.example):
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=assetflow_db
SECRET_KEY=your_secret_key_here

Run Application
python run.py
