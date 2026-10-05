import os
import sys
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------------------------------------------------
# ENVIRONMENT & CONFIGURATION
# -----------------------------------------------------------------------------
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('\'"'))

load_env()

app = Flask(__name__)

# Security: Read SECRET_KEY strictly from environment variable (no hardcoded fallback)
app.secret_key = os.getenv('SECRET_KEY')
if not app.secret_key:
    # Fail fast if SECRET_KEY is not defined in environment
    raise RuntimeError(
        "CRITICAL SECURITY CONFIGURATION ERROR: 'SECRET_KEY' environment variable is not set. "
        "Please configure SECRET_KEY in your environment variables or .env file."
    )

# Database & Cloud Configuration
import db_config
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), 'clinic_local.db')

# -----------------------------------------------------------------------------
# DATABASE ADAPTER (MySQL Primary with SSL for Aiven & Controlled Local Fallback)
# -----------------------------------------------------------------------------
def get_db():
    cfg = db_config.get_db_config()
    # 1. Primary MySQL Connection (Configured for Aiven Cloud MySQL with SSL/TLS)
    try:
        conn = db_config.get_mysql_connection(timeout=10)
        return conn, 'mysql'
    except Exception as e:
        # On Render or cloud databases, fail loudly to prevent silent SQLite data loss
        if cfg['is_cloud']:
            print(f"[FATAL] MySQL connection to {cfg['host']}:{cfg['port']}/{cfg['database']} failed: {e}")
            raise RuntimeError(
                f"Cloud MySQL connection failed: {e}. "
                f"SQLite fallback is disabled on Render to avoid data loss."
            )
        print(f"[Notice] Local MySQL unavailable ({e}). Using local mirror.")

    # 2. Local fallback (ONLY for offline local development on localhost)
    if not os.path.exists(SQLITE_DB_PATH):
        try:
            import init_db
            init_db.init_sqlite_fallback()
        except Exception:
            pass

    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn, 'sqlite'

def query_db(query, params=(), one=False, commit=False):
    conn, engine = get_db()
    try:
        if engine == 'mysql':
            cur = conn.cursor(dictionary=True)
            cur.execute(query, params)
            if commit:
                conn.commit()
                last_id = cur.lastrowid
                cur.close()
                conn.close()
                return last_id
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return (rows[0] if rows else None) if one else rows
        else:
            sqlite_query = query.replace('%s', '?')
            cur = conn.cursor()
            cur.execute(sqlite_query, params)
            if commit:
                conn.commit()
                last_id = cur.lastrowid
                cur.close()
                conn.close()
                return last_id
            rows = [dict(row) for row in cur.fetchall()]
            cur.close()
            conn.close()
            return (rows[0] if rows else None) if one else rows
    except Exception as e:
        if commit:
            try:
                conn.rollback()
            except Exception:
                pass
        conn.close()
        raise e

def is_mysql_connected():
    try:
        conn, engine = get_db()
        conn.close()
        return engine == 'mysql'
    except Exception:
        return False

@app.context_processor
def inject_db_mode():
    mysql_active = is_mysql_connected()
    return {
        'db_engine': db_config.get_display_engine_name() if mysql_active else 'Local SQLite Mirror',
        'is_mysql': mysql_active,
        'current_year': datetime.now().year
    }

# Custom template filter for clean date display
@app.template_filter('clean_date')
def clean_date_filter(val):
    if not val:
        return ''
    s = str(val).replace('T', ' ')
    if len(s) > 19:
        s = s[:19]
    return s

# -----------------------------------------------------------------------------
# AUTHENTICATION & ACCESS DECORATORS
# -----------------------------------------------------------------------------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to access your clinic portal.', 'info')
                return redirect(url_for('login'))
            if role and session.get('role') != role and session.get('role') != 'admin':
                flash('Access restricted: Insufficient permissions.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

def verify_user_password(stored_password, provided_password):
    if stored_password.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password

# -----------------------------------------------------------------------------
# PUBLIC ROUTES
# -----------------------------------------------------------------------------
@app.route('/')
def index():
    try:
        doctors = query_db("""
            SELECT d.DoctorID, d.DoctorName, d.Specialization, d.ConsultationFee, 
                   d.RoomNumber, dep.DepartmentName
            FROM doctor d
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            ORDER BY d.DoctorID LIMIT 4
        """)
        stats = {
            'patients': query_db("SELECT COUNT(*) AS c FROM patient", one=True)['c'],
            'doctors': query_db("SELECT COUNT(*) AS c FROM doctor", one=True)['c'],
            'appointments': query_db("SELECT COUNT(*) AS c FROM appointment", one=True)['c'],
            'departments': query_db("SELECT COUNT(*) AS c FROM department", one=True)['c']
        }
    except Exception:
        doctors = []
        stats = {'patients': 5, 'doctors': 4, 'appointments': 6, 'departments': 4}
    return render_template('index.html', featured_doctors=doctors, stats=stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        try:
            # Automatic role detection: find user by username directly without role dropdown
            user = query_db(
                "SELECT * FROM users WHERE username = %s AND is_active = 1",
                (username,),
                one=True
            )
            if user and verify_user_password(user['password'], password):
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']

                if user['role'] == 'doctor':
                    doc = query_db("SELECT DoctorID, DoctorName FROM doctor WHERE UserID = %s", (user['user_id'],), one=True)
                    session['doctor_id'] = doc['DoctorID'] if doc else None
                    session['doctor_name'] = doc['DoctorName'] if doc else user['username']
                elif user['role'] == 'patient':
                    pat = query_db("SELECT PatientID, PatientName FROM patient WHERE UserID = %s", (user['user_id'],), one=True)
                    session['patient_id'] = pat['PatientID'] if pat else None
                    session['patient_name'] = pat['PatientName'] if pat else user['username']

                displayName = session.get('doctor_name') or session.get('patient_name') or username
                flash(f'Welcome back, {displayName}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password. Please verify your credentials.', 'danger')
        except Exception as e:
            flash(f'Database error during sign-in: {str(e)}', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role', 'patient').lower()
        if role not in ('patient', 'doctor'):
            role = 'patient'

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        dob = request.form.get('dob')
        gender = request.form.get('gender', 'Male')
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        blood_group = request.form.get('blood_group', '')
        address = request.form.get('address', '').strip()
        specialization = request.form.get('specialization', 'General Medicine').strip()

        if not all([username, password, name, phone]):
            flash('Please complete all required fields.', 'warning')
            return render_template('register.html')

        try:
            existing_user = query_db("SELECT user_id FROM users WHERE username = %s", (username,), one=True)
            if existing_user:
                flash('Username is already taken. Please choose another username.', 'danger')
                return render_template('register.html')

            hashed_pwd = generate_password_hash(password)
            user_id = query_db(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, hashed_pwd, role),
                commit=True
            )

            if role == 'doctor':
                # Create doctor record
                query_db(
                    """INSERT INTO doctor (DoctorName, Specialization, Phone, Email, DepartmentID, ConsultationFee, RoomNumber, UserID)
                       VALUES (%s, %s, %s, %s, 2, 500.00, 'Consultation Room', %s)""",
                    (name, specialization, phone, email or None, user_id),
                    commit=True
                )
            else:
                # Create patient record
                dob_val = dob if dob else '2000-01-01'
                query_db(
                    """INSERT INTO patient (PatientName, DOB, Gender, Phone, Email, BloodGroup, Address, UserID)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (name, dob_val, gender, phone, email or None, blood_group or None, address or None, user_id),
                    commit=True
                )

            flash(f'Account created successfully as {role.capitalize()}! Please sign in with username: {username}', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Registration error: {str(e)}', 'danger')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out safely.', 'info')
    return redirect(url_for('index'))

# -----------------------------------------------------------------------------
# DASHBOARD
# -----------------------------------------------------------------------------
@app.route('/dashboard')
@login_required()
def dashboard():
    role = session['role']

    # Tailor stats cards depending on role
    if role == 'patient' and session.get('patient_id'):
        stats = {
            'appointments': query_db("SELECT COUNT(*) AS c FROM appointment WHERE PatientID = %s", (session['patient_id'],), one=True)['c'],
            'prescriptions': query_db("""
                SELECT COUNT(*) AS c FROM prescription pr
                JOIN appointment a ON pr.AppointmentID = a.AppointmentID
                WHERE a.PatientID = %s
            """, (session['patient_id'],), one=True)['c'],
            'pending_bills': query_db("""
                SELECT COUNT(*) AS c FROM bill b
                JOIN appointment a ON b.AppointmentID = a.AppointmentID
                WHERE a.PatientID = %s AND b.PaymentStatus = 'Pending'
            """, (session['patient_id'],), one=True)['c'],
            'doctors': query_db("SELECT COUNT(*) AS c FROM doctor", one=True)['c']
        }
    else:
        stats = {
            'patients': query_db("SELECT COUNT(*) AS c FROM patient", one=True)['c'],
            'doctors': query_db("SELECT COUNT(*) AS c FROM doctor", one=True)['c'],
            'appointments': query_db("SELECT COUNT(*) AS c FROM appointment", one=True)['c'],
            'pending_bills': query_db("SELECT COUNT(*) AS c FROM bill WHERE PaymentStatus = 'Pending'", one=True)['c']
        }

    recent_appointments = []

    if role == 'doctor' and session.get('doctor_id'):
        recent_appointments = query_db("""
            SELECT a.AppointmentID, p.PatientName, p.Phone AS PatientPhone, a.AppointmentDate, a.Reason, a.Status,
                   b.BillID, b.TotalAmount, b.PaymentStatus
            FROM appointment a
            JOIN patient p ON a.PatientID = p.PatientID
            LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
            WHERE a.DoctorID = %s
            ORDER BY a.AppointmentDate DESC LIMIT 6
        """, (session['doctor_id'],))
    elif role == 'patient' and session.get('patient_id'):
        recent_appointments = query_db("""
            SELECT a.AppointmentID, d.DoctorName, d.Specialization, dep.DepartmentName,
                   a.AppointmentDate, a.Reason, a.Status, b.BillID, b.TotalAmount, b.PaymentStatus
            FROM appointment a
            JOIN doctor d ON a.DoctorID = d.DoctorID
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
            WHERE a.PatientID = %s
            ORDER BY a.AppointmentDate DESC LIMIT 6
        """, (session['patient_id'],))
    else: # Admin
        recent_appointments = query_db("""
            SELECT a.AppointmentID, p.PatientName, d.DoctorName, dep.DepartmentName,
                   a.AppointmentDate, a.Status, b.BillID, b.TotalAmount, b.PaymentStatus
            FROM appointment a
            JOIN patient p ON a.PatientID = p.PatientID
            JOIN doctor d ON a.DoctorID = d.DoctorID
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
            ORDER BY a.AppointmentDate DESC LIMIT 8
        """)

    revenue_stats = {}
    if role in ('admin', 'doctor'):
        rev = query_db("""
            SELECT 
                COALESCE(SUM(CASE WHEN PaymentStatus='Paid' THEN TotalAmount ELSE 0 END), 0) AS collected,
                COALESCE(SUM(CASE WHEN PaymentStatus='Pending' THEN TotalAmount ELSE 0 END), 0) AS pending
            FROM bill
        """, one=True)
        revenue_stats = rev or {'collected': 0, 'pending': 0}

    return render_template(
        'dashboard.html',
        stats=stats,
        recent=recent_appointments,
        revenue=revenue_stats
    )

# -----------------------------------------------------------------------------
# PATIENTS
# -----------------------------------------------------------------------------
@app.route('/patients')
@login_required()
def patients():
    search = request.args.get('q', '').strip()
    if session['role'] == 'patient':
        rows = query_db("""
            SELECT p.*, u.username
            FROM patient p
            LEFT JOIN users u ON p.UserID = u.user_id
            WHERE p.UserID = %s
        """, (session['user_id'],))
    else:
        if search:
            rows = query_db("""
                SELECT p.*, COUNT(a.AppointmentID) AS VisitCount
                FROM patient p
                LEFT JOIN appointment a ON p.PatientID = a.PatientID
                WHERE p.PatientName LIKE %s OR p.Phone LIKE %s OR p.BloodGroup = %s
                GROUP BY p.PatientID
                ORDER BY p.PatientID DESC
            """, (f'%{search}%', f'%{search}%', search))
        else:
            rows = query_db("""
                SELECT p.*, COUNT(a.AppointmentID) AS VisitCount
                FROM patient p
                LEFT JOIN appointment a ON p.PatientID = a.PatientID
                GROUP BY p.PatientID
                ORDER BY p.PatientID DESC
            """)
    return render_template('patients.html', patients=rows, search_query=search)

# -----------------------------------------------------------------------------
# DOCTORS
# -----------------------------------------------------------------------------
@app.route('/doctors')
def doctors():
    dept_filter = request.args.get('dept', '')
    departments = query_db("SELECT * FROM department ORDER BY DepartmentName")

    if dept_filter:
        doc_rows = query_db("""
            SELECT d.*, dep.DepartmentName
            FROM doctor d
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            WHERE dep.DepartmentName = %s
            ORDER BY d.DoctorID
        """, (dept_filter,))
    else:
        doc_rows = query_db("""
            SELECT d.*, dep.DepartmentName
            FROM doctor d
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            ORDER BY d.DoctorID
        """)

    return render_template('doctors.html', doctors=doc_rows, departments=departments, selected_dept=dept_filter)

# -----------------------------------------------------------------------------
# APPOINTMENTS
# -----------------------------------------------------------------------------
@app.route('/appointments')
@login_required()
def appointments():
    status_filter = request.args.get('status', '')
    role = session['role']

    base_query = """
        SELECT a.AppointmentID, a.PatientID, p.PatientName, p.Phone AS PatientPhone,
               d.DoctorID, d.DoctorName, d.Specialization, dep.DepartmentName,
               a.AppointmentDate, a.Reason, a.Symptoms, a.Diagnosis, a.DoctorNotes, a.Status,
               b.BillID, b.TotalAmount, b.PaymentStatus
        FROM appointment a
        JOIN patient p ON a.PatientID = p.PatientID
        JOIN doctor d ON a.DoctorID = d.DoctorID
        JOIN department dep ON d.DepartmentID = dep.DepartmentID
        LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
    """
    conditions = []
    params = []

    if role == 'patient':
        conditions.append("p.UserID = %s")
        params.append(session['user_id'])
    elif role == 'doctor' and session.get('doctor_id'):
        conditions.append("a.DoctorID = %s")
        params.append(session['doctor_id'])

    if status_filter:
        conditions.append("a.Status = %s")
        params.append(status_filter)

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY a.AppointmentDate DESC"
    appts = query_db(base_query, tuple(params))
    return render_template('appointments.html', appointments=appts, active_filter=status_filter)

@app.route('/appointments/new', methods=['GET', 'POST'])
@login_required('patient')
def new_appointment():
    patient = query_db("SELECT * FROM patient WHERE UserID = %s", (session['user_id'],), one=True)
    if not patient:
        flash('Patient record not found. Please complete your profile.', 'warning')
        return redirect(url_for('dashboard'))

    doctors = query_db("""
        SELECT d.DoctorID, d.DoctorName, d.Specialization, d.ConsultationFee, dep.DepartmentName
        FROM doctor d
        JOIN department dep ON d.DepartmentID = dep.DepartmentID
        ORDER BY d.DoctorName
    """)

    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        appt_date = request.form.get('appointment_date')
        reason = request.form.get('reason', 'General Consultation').strip()
        symptoms = request.form.get('symptoms', '').strip()

        if not doctor_id or not appt_date:
            flash('Please select a doctor and appointment date.', 'warning')
            return render_template('new_appointment.html', patient=patient, doctors=doctors)

        # Standardize datetime string from datetime-local input
        clean_date = appt_date.replace('T', ' ')
        if len(clean_date) == 16:
            clean_date += ':00'

        try:
            new_appt_id = query_db(
                """INSERT INTO appointment (PatientID, DoctorID, AppointmentDate, Reason, Symptoms, Status)
                   VALUES (%s, %s, %s, %s, %s, 'Scheduled')""",
                (patient['PatientID'], doctor_id, clean_date, reason, symptoms),
                commit=True
            )

            # Check if bill already generated by MySQL trigger
            existing_bill = query_db("SELECT BillID FROM bill WHERE AppointmentID = %s", (new_appt_id,), one=True)
            if not existing_bill:
                doc = query_db("SELECT ConsultationFee FROM doctor WHERE DoctorID = %s", (doctor_id,), one=True)
                fee = float(doc['ConsultationFee']) if doc else 500.00
                tax = round(fee * 0.05, 2)
                total = fee + tax
                query_db(
                    """INSERT INTO bill (AppointmentID, Amount, Tax, TotalAmount, PaymentStatus, PaymentMethod)
                       VALUES (%s, %s, %s, %s, 'Pending', 'Pending')""",
                    (new_appt_id, fee, tax, total),
                    commit=True
                )

            flash('Appointment booked successfully! Our clinic team will attend to you.', 'success')
            return redirect(url_for('appointments'))
        except Exception as e:
            flash(f'Failed to schedule appointment: {str(e)}', 'danger')

    return render_template('new_appointment.html', patient=patient, doctors=doctors)

@app.route('/appointments/<int:appointment_id>/status', methods=['POST'])
@login_required()
def update_appointment_status(appointment_id):
    new_status = request.form.get('status')
    diagnosis = request.form.get('diagnosis', '').strip()
    doctor_notes = request.form.get('notes', '').strip()

    try:
        if session['role'] == 'doctor':
            query_db(
                """UPDATE appointment 
                   SET Status = %s, 
                       Diagnosis = COALESCE(NULLIF(%s, ''), Diagnosis),
                       DoctorNotes = COALESCE(NULLIF(%s, ''), DoctorNotes)
                   WHERE AppointmentID = %s AND DoctorID = %s""",
                (new_status, diagnosis, doctor_notes, appointment_id, session.get('doctor_id')),
                commit=True
            )
        elif session['role'] == 'admin':
            query_db(
                "UPDATE appointment SET Status = %s WHERE AppointmentID = %s",
                (new_status, appointment_id),
                commit=True
            )
        flash(f'Appointment #{appointment_id} updated to {new_status}.', 'success')
    except Exception as e:
        flash(f'Error updating appointment: {str(e)}', 'danger')

    return redirect(url_for('appointments'))

@app.route('/appointments/<int:appointment_id>/prescribe', methods=['POST'])
@login_required('doctor')
def add_prescription(appointment_id):
    medicine = request.form.get('medicine', '').strip()
    dosage = request.form.get('dosage', '').strip()
    duration = request.form.get('duration', '').strip()
    instructions = request.form.get('instructions', 'Take after meals').strip()
    diagnosis = request.form.get('diagnosis', '').strip()

    if not medicine or not dosage or not duration:
        flash('Medicine name, dosage, and duration are required.', 'warning')
        return redirect(url_for('appointments'))

    try:
        query_db(
            """INSERT INTO prescription (AppointmentID, Medicine, Dosage, Duration, Instructions)
               VALUES (%s, %s, %s, %s, %s)""",
            (appointment_id, medicine, dosage, duration, instructions),
            commit=True
        )
        if diagnosis:
            query_db(
                "UPDATE appointment SET Diagnosis = %s, Status = 'Completed' WHERE AppointmentID = %s",
                (diagnosis, appointment_id),
                commit=True
            )
        flash('Prescription added successfully.', 'success')
    except Exception as e:
        flash(f'Failed to add prescription: {str(e)}', 'danger')

    return redirect(url_for('prescriptions'))

# -----------------------------------------------------------------------------
# PRESCRIPTIONS
# -----------------------------------------------------------------------------
@app.route('/prescriptions')
@login_required()
def prescriptions():
    role = session['role']
    # Always include DoctorName, Specialization, and PatientName for full transparency
    if role == 'patient':
        items = query_db("""
            SELECT pr.*, a.AppointmentDate, a.Diagnosis, 
                   p.PatientName, p.Phone AS PatientPhone,
                   d.DoctorName, d.Specialization, dep.DepartmentName
            FROM prescription pr
            JOIN appointment a ON pr.AppointmentID = a.AppointmentID
            JOIN patient p ON a.PatientID = p.PatientID
            JOIN doctor d ON a.DoctorID = d.DoctorID
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            WHERE p.UserID = %s
            ORDER BY pr.PrescriptionID DESC
        """, (session['user_id'],))
    elif role == 'doctor':
        items = query_db("""
            SELECT pr.*, a.AppointmentDate, a.Diagnosis, 
                   p.PatientName, p.Phone AS PatientPhone,
                   d.DoctorName, d.Specialization, dep.DepartmentName
            FROM prescription pr
            JOIN appointment a ON pr.AppointmentID = a.AppointmentID
            JOIN patient p ON a.PatientID = p.PatientID
            JOIN doctor d ON a.DoctorID = d.DoctorID
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            WHERE a.DoctorID = %s
            ORDER BY pr.PrescriptionID DESC
        """, (session.get('doctor_id'),))
    else: # Admin
        items = query_db("""
            SELECT pr.*, a.AppointmentDate, a.Diagnosis, 
                   p.PatientName, p.Phone AS PatientPhone,
                   d.DoctorName, d.Specialization, dep.DepartmentName
            FROM prescription pr
            JOIN appointment a ON pr.AppointmentID = a.AppointmentID
            JOIN patient p ON a.PatientID = p.PatientID
            JOIN doctor d ON a.DoctorID = d.DoctorID
            JOIN department dep ON d.DepartmentID = dep.DepartmentID
            ORDER BY pr.PrescriptionID DESC
        """)

    return render_template('prescriptions.html', prescriptions=items)

# -----------------------------------------------------------------------------
# BILLING & INVOICES
# -----------------------------------------------------------------------------
@app.route('/bills')
@login_required()
def bills():
    role = session['role']
    status_filter = request.args.get('status', '')

    base_query = """
        SELECT b.*, a.AppointmentDate, a.Reason, p.PatientName, p.Phone, d.DoctorName, dep.DepartmentName
        FROM bill b
        JOIN appointment a ON b.AppointmentID = a.AppointmentID
        JOIN patient p ON a.PatientID = p.PatientID
        JOIN doctor d ON a.DoctorID = d.DoctorID
        JOIN department dep ON d.DepartmentID = dep.DepartmentID
    """
    conditions = []
    params = []

    if role == 'patient':
        conditions.append("p.UserID = %s")
        params.append(session['user_id'])

    if status_filter:
        conditions.append("b.PaymentStatus = %s")
        params.append(status_filter)

    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    base_query += " ORDER BY b.BillID DESC"
    all_bills = query_db(base_query, tuple(params))
    return render_template('bills.html', bills=all_bills, active_status=status_filter)

@app.route('/bills/<int:bill_id>/pay', methods=['POST'])
@login_required()
def pay_bill(bill_id):
    payment_method = request.form.get('payment_method', 'UPI')
    try:
        paid_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        query_db(
            """UPDATE bill 
               SET PaymentStatus = 'Paid', PaymentMethod = %s, PaidAt = %s
               WHERE BillID = %s""",
            (payment_method, paid_at, bill_id),
            commit=True
        )
        flash(f'Payment of Bill #{bill_id} recorded successfully via {payment_method}!', 'success')
    except Exception as e:
        flash(f'Failed to process payment: {str(e)}', 'danger')

    return redirect(url_for('bills'))

@app.route('/bills/<int:bill_id>/invoice')
@login_required()
def invoice(bill_id):
    bill_data = query_db("""
        SELECT b.*, a.AppointmentID, a.AppointmentDate, a.Reason, a.Diagnosis,
               p.PatientID, p.PatientName, p.Phone, p.Email, p.Address,
               d.DoctorID, d.DoctorName, d.Specialization, d.RoomNumber,
               dep.DepartmentName
        FROM bill b
        JOIN appointment a ON b.AppointmentID = a.AppointmentID
        JOIN patient p ON a.PatientID = p.PatientID
        JOIN doctor d ON a.DoctorID = d.DoctorID
        JOIN department dep ON d.DepartmentID = dep.DepartmentID
        WHERE b.BillID = %s
    """, (bill_id,), one=True)

    if not bill_data:
        flash('Invoice not found.', 'danger')
        return redirect(url_for('bills'))

    # If patient, verify ownership
    if session['role'] == 'patient':
        pat = query_db("SELECT PatientID FROM patient WHERE UserID = %s", (session['user_id'],), one=True)
        if not pat or pat['PatientID'] != bill_data['PatientID']:
            flash('Access denied.', 'danger')
            return redirect(url_for('bills'))

    prescriptions_list = query_db("""
        SELECT * FROM prescription WHERE AppointmentID = %s
    """, (bill_data['AppointmentID'],))

    return render_template('invoice.html', bill=bill_data, prescriptions=prescriptions_list)

# -----------------------------------------------------------------------------
# CLINIC ANALYTICS & EXECUTIVE REPORTING
# -----------------------------------------------------------------------------
@app.route('/analytics')
@login_required()
def analytics():
    dept_stats = query_db("""
        SELECT dep.DepartmentName,
               COUNT(DISTINCT d.DoctorID) AS DoctorCount,
               COUNT(a.AppointmentID) AS TotalBookings,
               COALESCE(SUM(b.TotalAmount), 0) AS Revenue
        FROM department dep
        LEFT JOIN doctor d ON dep.DepartmentID = d.DepartmentID
        LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
        LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
        GROUP BY dep.DepartmentID, dep.DepartmentName
        ORDER BY Revenue DESC
    """)

    top_doctors = query_db("""
        SELECT d.DoctorName, d.Specialization, dep.DepartmentName,
               COUNT(a.AppointmentID) AS PatientCount,
               COALESCE(SUM(CASE WHEN b.PaymentStatus='Paid' THEN b.TotalAmount ELSE 0 END), 0) AS RevenueEarned
        FROM doctor d
        JOIN department dep ON d.DepartmentID = dep.DepartmentID
        LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
        LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
        GROUP BY d.DoctorID, d.DoctorName, d.Specialization, dep.DepartmentName
        ORDER BY PatientCount DESC LIMIT 5
    """)

    payment_breakdown = query_db("""
        SELECT PaymentMethod, COUNT(BillID) AS Count, SUM(TotalAmount) AS Total
        FROM bill
        WHERE PaymentStatus = 'Paid'
        GROUP BY PaymentMethod
    """)

    status_counts = query_db("""
        SELECT Status, COUNT(*) AS count
        FROM appointment
        GROUP BY Status
    """)

    return render_template(
        'analytics.html',
        departments=dept_stats,
        top_doctors=top_doctors,
        payments=payment_breakdown,
        status_counts=status_counts
    )

# -----------------------------------------------------------------------------
# DATABASE DIAGNOSTICS & STATUS
# -----------------------------------------------------------------------------
@app.route('/system-status')
@login_required('admin')
def system_status():
    counts = {}
    for tbl in ['users', 'department', 'patient', 'doctor', 'appointment', 'prescription', 'bill']:
        try:
            cnt = query_db(f"SELECT COUNT(*) AS c FROM {tbl}", one=True)['c']
            counts[tbl] = cnt
        except Exception:
            counts[tbl] = 'Error'

    cfg = db_config.get_db_config()
    active_engine = db_config.get_display_engine_name() if is_mysql_connected() else 'Local SQLite Mirror'
    return render_template('system_status.html', counts=counts, db_engine=active_engine, db_config=cfg)

if __name__ == '__main__':
    cfg = db_config.get_db_config()
    print("[*] Starting MediCare Clinic Management System...")
    print(f"[*] Active Database Engine: {db_config.get_display_engine_name() if is_mysql_connected() else 'Local SQLite Mirror'}")
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False if cfg['is_cloud'] else True, host='0.0.0.0' if cfg['is_cloud'] else '127.0.0.1', port=port)
