"""
Clinic Management System — Database Setup & Verification Tool
Automates MySQL schema execution, seed data insertion, and health checks for
Local MySQL and Aiven Cloud MySQL.
"""

import os
import sys
import re

# Safe UTF-8 console output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import db_config

def init_mysql(force=False):
    cfg = db_config.get_db_config()
    target_type = "Aiven Cloud MySQL" if cfg['is_aiven'] else ("Cloud MySQL" if cfg['is_cloud'] else "Local MySQL")

    print("=" * 65)
    print(f"   MEDICARE CLINIC DATABASE INITIALIZATION ({target_type})")
    print("=" * 65)
    print(f"Target Database : {cfg['database']} on {cfg['host']}:{cfg['port']}")
    print(f"Connecting as   : '{cfg['user']}' (SSL Mode: {cfg['ssl_mode']})...")

    try:
        import mysql.connector
        from mysql.connector import Error
    except ImportError:
        print("[!] Error: mysql-connector-python is not installed.")
        print("    Run: pip install -r requirements.txt")
        return False

    try:
        # Try connecting directly to target database
        conn = None
        try:
            conn = db_config.get_mysql_connection(database=cfg['database'], timeout=15)
            print(f"[+] Connected to database `{cfg['database']}` successfully!")
        except Exception as conn_err:
            # If database does not exist yet, attempt to create it (for local MySQL or admin user)
            print(f"[*] Database `{cfg['database']}` not reachable directly ({conn_err}).")
            print("[*] Attempting admin server connection to create database if missing...")
            try:
                # Try connecting without specifying database or using defaultdb
                admin_db = 'defaultdb' if cfg['is_aiven'] else None
                admin_conn = db_config.get_mysql_connection(database=admin_db, timeout=15)
                admin_cur = admin_conn.cursor()
                admin_cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
                admin_cur.close()
                admin_conn.close()
                print(f"[+] Database `{cfg['database']}` created/verified.")
                conn = db_config.get_mysql_connection(database=cfg['database'], timeout=15)
            except Exception as admin_err:
                print(f"[!] Could not auto-create database `{cfg['database']}`: {admin_err}")
                raise conn_err

        # Check if tables already exist and contain data
        if not force and not os.getenv('INIT_DB_FORCE'):
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM `users`;")
                user_count = cur.fetchone()[0]
                cur.close()
                if user_count and user_count > 0:
                    print(f"\n[*] Database `{cfg['database']}` is already initialized with {user_count} users.")
                    print("    Preserving existing data. Schema execution skipped.")
                    print("    (To force re-initialization and reset seed data, run: python init_db.py --force)\n")
                    conn.close()
                    return True
            except Exception:
                # Tables don't exist yet, proceed with schema execution
                pass

        cursor = conn.cursor()

        schema_file = os.path.join(os.path.dirname(__file__), 'database', 'schema.sql')
        if not os.path.exists(schema_file):
            print(f"[!] schema.sql not found at {schema_file}")
            return False

        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print("[*] Executing schema.sql definitions, views, procedures, and seed data...")

        # Parse SQL handling DELIMITER blocks for triggers and stored procedures
        statements = []
        current_delimiter = ';'
        current_stmt = []

        for line in sql_content.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith('DELIMITER'):
                parts = stripped.split()
                if len(parts) > 1:
                    current_delimiter = parts[1]
                continue

            if stripped.endswith(current_delimiter):
                trimmed = stripped[:-len(current_delimiter)]
                current_stmt.append(line[:line.rfind(current_delimiter)])
                stmt_text = '\n'.join(current_stmt).strip()
                if stmt_text:
                    statements.append(stmt_text)
                current_stmt = []
            else:
                current_stmt.append(line)

        if current_stmt:
            stmt_text = '\n'.join(current_stmt).strip()
            if stmt_text:
                statements.append(stmt_text)

        executed = 0
        for stmt in statements:
            clean_lines = [l for l in stmt.splitlines() if not l.strip().startswith('--') and not l.strip().startswith('/*')]
            clean_stmt = '\n'.join(clean_lines).strip()
            if not clean_stmt:
                continue
            try:
                cursor.execute(clean_stmt)
                executed += 1
            except Error as e:
                # Ignore non-fatal drops or notices
                if 'DROP' not in clean_stmt.upper() and 'IF EXISTS' not in clean_stmt.upper():
                    print(f"    [Notice] Statement notice: {e}")

        conn.commit()
        print(f"[+] Successfully executed {executed} SQL statements.")

        # Print entity counts
        tables = ['users', 'department', 'patient', 'doctor', 'appointment', 'prescription', 'bill']
        print("\n--- Current Record Counts in MySQL ---")
        for tbl in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                cnt = cursor.fetchone()[0]
                print(f"  * {tbl.ljust(15)} : {cnt} records")
            except Exception:
                pass

        cursor.close()
        conn.close()
        print(f"\n[SUCCESS] {target_type} is fully initialized and ready!\n")
        return True

    except Exception as ex:
        print(f"\n[!] MySQL Connection / Execution failed: {ex}")
        print("\n[*] Check your configuration:")
        print(f"    Target Database : {cfg['database']}")
        print(f"    Host            : {cfg['host']}")
        print(f"    User            : {cfg['user']}")
        print(f"    Is Aiven Cloud  : {cfg['is_aiven']}")
        return False

def init_sqlite_fallback():
    """Generates an embedded SQLite database as an immediate offline backup."""
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), 'clinic_local.db')
    print(f"[*] Creating local SQLite mirror database at {db_path}...")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    DROP VIEW IF EXISTS patient_appointment_report;
    DROP VIEW IF EXISTS v_doctor_schedules;
    DROP VIEW IF EXISTS v_billing_summary;
    DROP VIEW IF EXISTS v_clinic_stats;

    DROP TABLE IF EXISTS bill;
    DROP TABLE IF EXISTS prescription;
    DROP TABLE IF EXISTS appointment;
    DROP TABLE IF EXISTS doctor;
    DROP TABLE IF EXISTS patient;
    DROP TABLE IF EXISTS department;
    DROP TABLE IF EXISTS users;

    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('patient','doctor','admin')),
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE department (
        DepartmentID INTEGER PRIMARY KEY AUTOINCREMENT,
        DepartmentName TEXT NOT NULL UNIQUE,
        Description TEXT,
        HeadOfDepartment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE patient (
        PatientID INTEGER PRIMARY KEY AUTOINCREMENT,
        PatientName TEXT NOT NULL,
        DOB TEXT NOT NULL,
        Gender TEXT NOT NULL,
        Phone TEXT NOT NULL UNIQUE,
        Email TEXT,
        BloodGroup TEXT,
        Address TEXT,
        EmergencyContact TEXT,
        UserID INTEGER UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (UserID) REFERENCES users(user_id) ON DELETE SET NULL
    );

    CREATE TABLE doctor (
        DoctorID INTEGER PRIMARY KEY AUTOINCREMENT,
        DoctorName TEXT NOT NULL,
        Specialization TEXT NOT NULL,
        Qualifications TEXT DEFAULT 'MBBS, MD',
        Phone TEXT NOT NULL UNIQUE,
        Email TEXT,
        DepartmentID INTEGER NOT NULL,
        ConsultationFee REAL DEFAULT 500.00,
        RoomNumber TEXT DEFAULT 'Room 101',
        AvailableDays TEXT DEFAULT 'Mon - Sat',
        UserID INTEGER UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (DepartmentID) REFERENCES department(DepartmentID),
        FOREIGN KEY (UserID) REFERENCES users(user_id) ON DELETE SET NULL
    );

    CREATE TABLE appointment (
        AppointmentID INTEGER PRIMARY KEY AUTOINCREMENT,
        PatientID INTEGER NOT NULL,
        DoctorID INTEGER NOT NULL,
        AppointmentDate TEXT NOT NULL,
        Reason TEXT DEFAULT 'General Consultation',
        Symptoms TEXT,
        Diagnosis TEXT,
        DoctorNotes TEXT,
        Status TEXT DEFAULT 'Scheduled',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (PatientID) REFERENCES patient(PatientID) ON DELETE CASCADE,
        FOREIGN KEY (DoctorID) REFERENCES doctor(DoctorID)
    );

    CREATE TABLE prescription (
        PrescriptionID INTEGER PRIMARY KEY AUTOINCREMENT,
        AppointmentID INTEGER NOT NULL,
        Medicine TEXT NOT NULL,
        Dosage TEXT NOT NULL,
        Duration TEXT NOT NULL,
        Instructions TEXT DEFAULT 'Take after meals',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (AppointmentID) REFERENCES appointment(AppointmentID) ON DELETE CASCADE
    );

    CREATE TABLE bill (
        BillID INTEGER PRIMARY KEY AUTOINCREMENT,
        AppointmentID INTEGER NOT NULL UNIQUE,
        Amount REAL NOT NULL,
        Tax REAL DEFAULT 0.0,
        TotalAmount REAL,
        PaymentStatus TEXT DEFAULT 'Pending',
        PaymentMethod TEXT DEFAULT 'Pending',
        PaidAt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (AppointmentID) REFERENCES appointment(AppointmentID) ON DELETE CASCADE
    );

    -- Views
    CREATE VIEW patient_appointment_report AS
    SELECT 
        a.AppointmentID, p.PatientID, p.PatientName, p.Phone AS PatientPhone,
        d.DoctorID, d.DoctorName, d.Specialization, dep.DepartmentName,
        a.AppointmentDate, a.Reason, a.Diagnosis, a.Status AS AppointmentStatus,
        b.BillID, b.TotalAmount, b.PaymentStatus
    FROM appointment a
    JOIN patient p ON a.PatientID = p.PatientID
    JOIN doctor d ON a.DoctorID = d.DoctorID
    JOIN department dep ON d.DepartmentID = dep.DepartmentID
    LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID;

    -- Seed Data
    INSERT INTO users (user_id, username, password, role) VALUES
    (1, 'patient101', 'patient123', 'patient'),
    (2, 'patient102', 'patient123', 'patient'),
    (3, 'patient103', 'patient123', 'patient'),
    (4, 'doctor201', 'doctor123', 'doctor'),
    (5, 'doctor202', 'doctor123', 'doctor'),
    (6, 'doctor203', 'doctor123', 'doctor'),
    (7, 'admin', 'admin123', 'admin');

    INSERT INTO department (DepartmentID, DepartmentName, Description, HeadOfDepartment) VALUES
    (1, 'Cardiology', 'Specialized care for heart and cardiovascular disorders', 'Dr. Priya Sharma'),
    (2, 'General Medicine', 'Primary care, fever, routine diagnoses and preventive healthcare', 'Dr. Arjun Verma'),
    (3, 'Dermatology', 'Advanced skin, hair, nail treatments and dermatological surgery', 'Dr. Meera Iyer'),
    (4, 'Pediatrics', 'Comprehensive pediatric care from infants to adolescents', 'Dr. Rajesh Patel');

    INSERT INTO patient (PatientID, PatientName, DOB, Gender, Phone, Email, BloodGroup, Address, EmergencyContact, UserID) VALUES
    (101, 'Ravi Kumar', '2002-04-15', 'Male', '9876543210', 'ravi.kumar@example.com', 'B+', '42 Rosewood Avenue, City Center', '9876500001', 1),
    (102, 'Anjali Rao', '2001-08-20', 'Female', '9876543211', 'anjali.rao@example.com', 'O+', '15 Lakeview Residency, West End', '9876500002', 2),
    (103, 'Kiran Teja', '2003-01-10', 'Male', '9876543212', 'kiran.teja@example.com', 'A+', '88 Palm Grove, East Ring Road', '9876500003', 3),
    (104, 'Sneha Kapoor', '1998-11-05', 'Female', '9876543213', 'sneha.k@example.com', 'AB+', '12 Hilltop Terrace, Sector 4', '9876500004', NULL),
    (105, 'Vikram Mehta', '1995-07-22', 'Male', '9876543214', 'vikram.m@example.com', 'O-', '23 Maple Crest, Tech Zone', '9876500005', NULL);

    INSERT INTO doctor (DoctorID, DoctorName, Specialization, Qualifications, Phone, Email, DepartmentID, ConsultationFee, RoomNumber, AvailableDays, UserID) VALUES
    (201, 'Dr. Priya Sharma', 'Cardiologist', 'MBBS, MD, DM', '9000000001', 'dr.priya@clinic.org', 1, 850.00, 'Cabin 101', 'Mon, Wed, Fri', 4),
    (202, 'Dr. Arjun Verma', 'General Physician', 'MBBS, MD', '9000000002', 'dr.arjun@clinic.org', 2, 500.00, 'Cabin 102', 'Mon - Sat', 5),
    (203, 'Dr. Meera Iyer', 'Dermatologist', 'MBBS, MD', '9000000003', 'dr.meera@clinic.org', 3, 650.00, 'Cabin 201', 'Tue, Thu, Sat', 6),
    (204, 'Dr. Rajesh Patel', 'Pediatrician', 'MBBS, DCH', '9000000004', 'dr.rajesh@clinic.org', 4, 600.00, 'Cabin 202', 'Mon - Fri', NULL);

    INSERT INTO appointment (AppointmentID, PatientID, DoctorID, AppointmentDate, Reason, Symptoms, Diagnosis, DoctorNotes, Status) VALUES
    (301, 101, 201, '2026-10-05 10:00:00', 'Cardiac checkup', 'Mild chest discomfort after stairs', 'Mild sinus tachycardia', 'Rest recommended; ECG clean', 'Confirmed'),
    (302, 102, 202, '2026-10-04 11:30:00', 'Viral fever and fatigue', 'Fever of 101F, body aches, sore throat', 'Acute viral nasopharyngitis', 'Hydration and 3 days rest advised', 'Completed'),
    (303, 103, 201, '2026-10-06 09:30:00', 'Routine BP evaluation', 'Occasional dizziness', NULL, NULL, 'Scheduled'),
    (304, 104, 203, '2026-10-04 14:00:00', 'Skin allergy consultation', 'Dry itchy rash on forearm', 'Contact dermatitis', 'Avoid chemical soaps; topical balm', 'Completed'),
    (305, 105, 204, '2026-10-07 16:00:00', 'Child wellness & vaccination', 'Routine booster dose', NULL, NULL, 'Scheduled'),
    (306, 101, 202, '2026-10-02 09:00:00', 'Seasonal allergy', 'Sneezing and runny nose', 'Allergic rhinitis', 'Antihistamines prescribed', 'Completed');

    INSERT INTO prescription (PrescriptionID, AppointmentID, Medicine, Dosage, Duration, Instructions) VALUES
    (401, 302, 'Paracetamol', '650 mg', '3 days', 'Take 1 tablet after meals when fever occurs'),
    (402, 302, 'Cetirizine', '10 mg', '5 days', 'Take 1 tablet at night before sleeping'),
    (403, 301, 'Aspirin (Ecosprin)', '75 mg', '14 days', 'Take once daily after breakfast'),
    (404, 304, 'Hydrocortisone Cream', '1%', '7 days', 'Apply thin layer twice daily on affected area'),
    (405, 304, 'Loratadine', '10 mg', '5 days', 'Take 1 tablet once daily morning'),
    (406, 306, 'Montelukast + Levocetirizine', '10mg/5mg', '10 days', 'Take 1 tablet at bedtime');

    INSERT INTO bill (BillID, AppointmentID, Amount, Tax, TotalAmount, PaymentStatus, PaymentMethod, PaidAt) VALUES
    (501, 301, 850.00, 42.50, 892.50, 'Pending', 'Pending', NULL),
    (502, 302, 500.00, 25.00, 525.00, 'Paid', 'UPI', '2026-10-04 12:15:00'),
    (503, 303, 850.00, 42.50, 892.50, 'Pending', 'Pending', NULL),
    (504, 304, 650.00, 32.50, 682.50, 'Paid', 'Card', '2026-10-04 14:45:00'),
    (505, 305, 600.00, 30.00, 630.00, 'Pending', 'Pending', NULL),
    (506, 306, 500.00, 25.00, 525.00, 'Paid', 'Cash', '2026-10-02 09:40:00');
    """)
    conn.commit()
    conn.close()
    print("[+] Local SQLite fallback database created and seeded successfully!")

if __name__ == '__main__':
    force_run = '--force' in sys.argv or '-f' in sys.argv
    success = init_mysql(force=force_run)
    cfg = db_config.get_db_config()

    if not success:
        if cfg['is_cloud']:
            print("[FATAL] Cloud database initialization failed. Exiting.")
            sys.exit(1)
        else:
            # Generate SQLite mirror locally only
            init_sqlite_fallback()
