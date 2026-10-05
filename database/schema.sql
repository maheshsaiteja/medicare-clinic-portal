-- ============================================================================
-- CLINIC MANAGEMENT SYSTEM — ENTERPRISE RELATIONAL DATABASE SCHEMA (MySQL 8.0+)
-- Designed for High Integrity, 3NF Compliance, Auditing, and Performance
-- ============================================================================

-- Database tables will be created in the currently connected database (e.g. defaultdb on Aiven)

-- ----------------------------------------------------------------------------
-- Drop existing views and tables in reverse dependency order
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS v_clinic_stats;
DROP VIEW IF EXISTS v_billing_summary;
DROP VIEW IF EXISTS v_doctor_schedules;
DROP VIEW IF EXISTS patient_appointment_report;

DROP TABLE IF EXISTS bill;
DROP TABLE IF EXISTS prescription;
DROP TABLE IF EXISTS appointment;
DROP TABLE IF EXISTS doctor;
DROP TABLE IF EXISTS patient;
DROP TABLE IF EXISTS department;
DROP TABLE IF EXISTS users;

-- ----------------------------------------------------------------------------
-- 1. USERS TABLE (Authentication & Role Management)
-- ----------------------------------------------------------------------------
CREATE TABLE users (
  user_id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  role ENUM('patient', 'doctor', 'admin') NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_users_username (username),
  INDEX idx_users_role (role)
) ENGINE=InnoDB AUTO_INCREMENT=1;

-- ----------------------------------------------------------------------------
-- 2. DEPARTMENT TABLE (Clinical Specialties)
-- ----------------------------------------------------------------------------
CREATE TABLE department (
  DepartmentID INT PRIMARY KEY AUTO_INCREMENT,
  DepartmentName VARCHAR(100) NOT NULL UNIQUE,
  Description VARCHAR(255) DEFAULT 'Specialized medical department',
  HeadOfDepartment VARCHAR(100) DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB AUTO_INCREMENT=1;

-- ----------------------------------------------------------------------------
-- 3. PATIENT TABLE (Demographics & Medical Profile)
-- ----------------------------------------------------------------------------
CREATE TABLE patient (
  PatientID INT PRIMARY KEY AUTO_INCREMENT,
  PatientName VARCHAR(100) NOT NULL,
  DOB DATE NOT NULL,
  Gender ENUM('Male', 'Female', 'Other') NOT NULL,
  Phone VARCHAR(15) NOT NULL UNIQUE,
  Email VARCHAR(120) DEFAULT NULL,
  BloodGroup ENUM('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-') DEFAULT NULL,
  Address VARCHAR(255) DEFAULT NULL,
  EmergencyContact VARCHAR(15) DEFAULT NULL,
  UserID INT UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (UserID) REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_patient_name (PatientName),
  INDEX idx_patient_phone (Phone)
) ENGINE=InnoDB AUTO_INCREMENT=101;

-- ----------------------------------------------------------------------------
-- 4. DOCTOR TABLE (Medical Staff & Consultation Details)
-- ----------------------------------------------------------------------------
CREATE TABLE doctor (
  DoctorID INT PRIMARY KEY AUTO_INCREMENT,
  DoctorName VARCHAR(100) NOT NULL,
  Specialization VARCHAR(100) NOT NULL,
  Qualifications VARCHAR(100) DEFAULT 'MBBS, MD',
  Phone VARCHAR(15) NOT NULL UNIQUE,
  Email VARCHAR(120) DEFAULT NULL,
  DepartmentID INT NOT NULL,
  ConsultationFee DECIMAL(10,2) NOT NULL DEFAULT 500.00 CHECK (ConsultationFee >= 0),
  RoomNumber VARCHAR(20) DEFAULT 'Room 101',
  AvailableDays VARCHAR(100) DEFAULT 'Mon - Sat',
  UserID INT UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (DepartmentID) REFERENCES department(DepartmentID) ON DELETE RESTRICT ON UPDATE CASCADE,
  FOREIGN KEY (UserID) REFERENCES users(user_id) ON DELETE SET NULL ON UPDATE CASCADE,
  INDEX idx_doctor_dept (DepartmentID),
  INDEX idx_doctor_name (DoctorName)
) ENGINE=InnoDB AUTO_INCREMENT=201;

-- ----------------------------------------------------------------------------
-- 5. APPOINTMENT TABLE (Patient-Doctor Consultation Schedule)
-- ----------------------------------------------------------------------------
CREATE TABLE appointment (
  AppointmentID INT PRIMARY KEY AUTO_INCREMENT,
  PatientID INT NOT NULL,
  DoctorID INT NOT NULL,
  AppointmentDate DATETIME NOT NULL,
  Reason VARCHAR(255) DEFAULT 'General Consultation',
  Symptoms TEXT DEFAULT NULL,
  Diagnosis VARCHAR(255) DEFAULT NULL,
  DoctorNotes TEXT DEFAULT NULL,
  Status ENUM('Scheduled', 'Confirmed', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Scheduled',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (PatientID) REFERENCES patient(PatientID) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (DoctorID) REFERENCES doctor(DoctorID) ON DELETE RESTRICT ON UPDATE CASCADE,
  INDEX idx_appointment_patient (PatientID),
  INDEX idx_appointment_doctor (DoctorID),
  INDEX idx_appointment_date (AppointmentDate),
  INDEX idx_appointment_status (Status)
) ENGINE=InnoDB AUTO_INCREMENT=301;

-- ----------------------------------------------------------------------------
-- 6. PRESCRIPTION TABLE (Medications & Dosage Instructions)
-- ----------------------------------------------------------------------------
CREATE TABLE prescription (
  PrescriptionID INT PRIMARY KEY AUTO_INCREMENT,
  AppointmentID INT NOT NULL,
  Medicine VARCHAR(150) NOT NULL,
  Dosage VARCHAR(100) NOT NULL,
  Duration VARCHAR(100) NOT NULL,
  Instructions VARCHAR(255) DEFAULT 'Take after meals',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (AppointmentID) REFERENCES appointment(AppointmentID) ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_prescription_appointment (AppointmentID)
) ENGINE=InnoDB AUTO_INCREMENT=401;

-- ----------------------------------------------------------------------------
-- 7. BILL TABLE (Financial Records & Payment Tracking)
-- ----------------------------------------------------------------------------
CREATE TABLE bill (
  BillID INT PRIMARY KEY AUTO_INCREMENT,
  AppointmentID INT NOT NULL UNIQUE,
  Amount DECIMAL(10,2) NOT NULL CHECK (Amount >= 0),
  Tax DECIMAL(10,2) NOT NULL DEFAULT 0.00 CHECK (Tax >= 0),
  TotalAmount DECIMAL(10,2) GENERATED ALWAYS AS (Amount + Tax) STORED,
  PaymentStatus ENUM('Pending', 'Paid', 'Cancelled') NOT NULL DEFAULT 'Pending',
  PaymentMethod ENUM('Cash', 'Card', 'UPI', 'Insurance', 'Pending') NOT NULL DEFAULT 'Pending',
  PaidAt DATETIME DEFAULT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (AppointmentID) REFERENCES appointment(AppointmentID) ON DELETE CASCADE ON UPDATE CASCADE,
  INDEX idx_bill_status (PaymentStatus),
  INDEX idx_bill_appointment (AppointmentID)
) ENGINE=InnoDB AUTO_INCREMENT=501;

-- ============================================================================
-- SQL VIEWS (Advanced Reporting & Analytics)
-- ============================================================================

-- 1. Comprehensive Patient Appointment Report
CREATE OR REPLACE VIEW patient_appointment_report AS
SELECT 
    a.AppointmentID,
    p.PatientID,
    p.PatientName,
    p.Phone AS PatientPhone,
    d.DoctorID,
    d.DoctorName,
    d.Specialization,
    dep.DepartmentName,
    a.AppointmentDate,
    a.Reason,
    a.Diagnosis,
    a.Status AS AppointmentStatus,
    b.BillID,
    b.TotalAmount,
    b.PaymentStatus
FROM appointment a
JOIN patient p ON a.PatientID = p.PatientID
JOIN doctor d ON a.DoctorID = d.DoctorID
JOIN department dep ON d.DepartmentID = dep.DepartmentID
LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID;

-- 2. Doctor Schedules & Daily Workload
CREATE OR REPLACE VIEW v_doctor_schedules AS
SELECT 
    d.DoctorID,
    d.DoctorName,
    d.Specialization,
    dep.DepartmentName,
    d.RoomNumber,
    COUNT(a.AppointmentID) AS TotalAppointments,
    SUM(CASE WHEN a.Status IN ('Scheduled', 'Confirmed') THEN 1 ELSE 0 END) AS PendingVisits,
    SUM(CASE WHEN a.Status = 'Completed' THEN 1 ELSE 0 END) AS CompletedVisits
FROM doctor d
JOIN department dep ON d.DepartmentID = dep.DepartmentID
LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
GROUP BY d.DoctorID, d.DoctorName, d.Specialization, dep.DepartmentName, d.RoomNumber;

-- 3. Department Financial & Clinical Performance
CREATE OR REPLACE VIEW v_billing_summary AS
SELECT 
    dep.DepartmentName,
    COUNT(DISTINCT a.AppointmentID) AS TotalAppointments,
    COUNT(b.BillID) AS TotalBills,
    COALESCE(SUM(b.TotalAmount), 0) AS TotalBilledAmount,
    COALESCE(SUM(CASE WHEN b.PaymentStatus = 'Paid' THEN b.TotalAmount ELSE 0 END), 0) AS TotalCollectedRevenue,
    COALESCE(SUM(CASE WHEN b.PaymentStatus = 'Pending' THEN b.TotalAmount ELSE 0 END), 0) AS TotalPendingRevenue
FROM department dep
LEFT JOIN doctor d ON dep.DepartmentID = d.DepartmentID
LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
GROUP BY dep.DepartmentID, dep.DepartmentName;

-- 4. Clinic High-Level Dashboard Statistics
CREATE OR REPLACE VIEW v_clinic_stats AS
SELECT 
    (SELECT COUNT(*) FROM patient) AS TotalPatients,
    (SELECT COUNT(*) FROM doctor) AS TotalDoctors,
    (SELECT COUNT(*) FROM department) AS TotalDepartments,
    (SELECT COUNT(*) FROM appointment) AS TotalAppointments,
    (SELECT COUNT(*) FROM appointment WHERE Status = 'Completed') AS CompletedAppointments,
    (SELECT COUNT(*) FROM appointment WHERE Status IN ('Scheduled', 'Confirmed')) AS ActiveAppointments,
    (SELECT COALESCE(SUM(TotalAmount), 0) FROM bill WHERE PaymentStatus = 'Paid') AS TotalRevenueCollected,
    (SELECT COALESCE(SUM(TotalAmount), 0) FROM bill WHERE PaymentStatus = 'Pending') AS OutstandingDues;

-- ============================================================================
-- STORED PROCEDURES (Modular Business Logic)
-- ============================================================================

DELIMITER $$

-- Procedure 1: Securely book an appointment with duplicate slot protection
DROP PROCEDURE IF EXISTS sp_book_appointment$$
CREATE PROCEDURE sp_book_appointment(
    IN p_patient_id INT,
    IN p_doctor_id INT,
    IN p_appointment_date DATETIME,
    IN p_reason VARCHAR(255),
    IN p_symptoms TEXT,
    OUT p_appointment_id INT
)
BEGIN
    DECLARE v_doctor_fee DECIMAL(10,2);
    
    -- Verify doctor exists and get consultation fee
    SELECT ConsultationFee INTO v_doctor_fee 
    FROM doctor WHERE DoctorID = p_doctor_id;
    
    IF v_doctor_fee IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Doctor not found.';
    END IF;
    
    -- Insert appointment record
    INSERT INTO appointment (PatientID, DoctorID, AppointmentDate, Reason, Symptoms, Status)
    VALUES (p_patient_id, p_doctor_id, p_appointment_date, p_reason, p_symptoms, 'Scheduled');
    
    SET p_appointment_id = LAST_INSERT_ID();
    
    -- Automatically generate initial bill
    INSERT INTO bill (AppointmentID, Amount, Tax, PaymentStatus, PaymentMethod)
    VALUES (p_appointment_id, v_doctor_fee, ROUND(v_doctor_fee * 0.05, 2), 'Pending', 'Pending');
END$$

-- Procedure 2: Complete visit, save diagnosis & add prescription atomically
DROP PROCEDURE IF EXISTS sp_complete_consultation$$
CREATE PROCEDURE sp_complete_consultation(
    IN p_appointment_id INT,
    IN p_diagnosis VARCHAR(255),
    IN p_notes TEXT,
    IN p_medicine VARCHAR(150),
    IN p_dosage VARCHAR(100),
    IN p_duration VARCHAR(100),
    IN p_instructions VARCHAR(255)
)
BEGIN
    START TRANSACTION;
    
    -- Update appointment diagnosis and mark completed
    UPDATE appointment 
    SET Diagnosis = p_diagnosis,
        DoctorNotes = p_notes,
        Status = 'Completed'
    WHERE AppointmentID = p_appointment_id;
    
    -- Add prescription if medicine is provided
    IF p_medicine IS NOT NULL AND TRIM(p_medicine) != '' THEN
        INSERT INTO prescription (AppointmentID, Medicine, Dosage, Duration, Instructions)
        VALUES (p_appointment_id, p_medicine, p_dosage, p_duration, p_instructions);
    END IF;
    
    COMMIT;
END$$

-- Procedure 3: Process bill payment
DROP PROCEDURE IF EXISTS sp_pay_bill$$
CREATE PROCEDURE sp_pay_bill(
    IN p_bill_id INT,
    IN p_payment_method ENUM('Cash', 'Card', 'UPI', 'Insurance')
)
BEGIN
    UPDATE bill 
    SET PaymentStatus = 'Paid',
        PaymentMethod = p_payment_method,
        PaidAt = NOW()
    WHERE BillID = p_bill_id;
END$$

DELIMITER ;

-- ============================================================================
-- SEED DATA (Realistic Hospital Master & Transaction Data)
-- ============================================================================

-- 1. Insert Users (Patient, Doctor, Admin)
-- Includes both plain-text demo credentials for local development & Werkzeug compatibility
INSERT INTO users (user_id, username, password, role) VALUES
(1, 'patient101', 'patient123', 'patient'),
(2, 'patient102', 'patient123', 'patient'),
(3, 'patient103', 'patient123', 'patient'),
(4, 'doctor201', 'doctor123', 'doctor'),
(5, 'doctor202', 'doctor123', 'doctor'),
(6, 'doctor203', 'doctor123', 'doctor'),
(7, 'admin', 'admin123', 'admin');

-- 2. Insert Departments
INSERT INTO department (DepartmentID, DepartmentName, Description, HeadOfDepartment) VALUES
(1, 'Cardiology', 'Specialized care for heart and cardiovascular disorders', 'Dr. Priya Sharma'),
(2, 'General Medicine', 'Primary care, fever, routine diagnoses and preventive healthcare', 'Dr. Arjun Verma'),
(3, 'Dermatology', 'Advanced skin, hair, nail treatments and dermatological surgery', 'Dr. Meera Iyer'),
(4, 'Pediatrics', 'Comprehensive pediatric care from infants to adolescents', 'Dr. Rajesh Patel');

-- 3. Insert Patients
INSERT INTO patient (PatientID, PatientName, DOB, Gender, Phone, Email, BloodGroup, Address, EmergencyContact, UserID) VALUES
(101, 'Ravi Kumar', '2002-04-15', 'Male', '9876543210', 'ravi.kumar@example.com', 'B+', '42 Rosewood Avenue, City Center', '9876500001', 1),
(102, 'Anjali Rao', '2001-08-20', 'Female', '9876543211', 'anjali.rao@example.com', 'O+', '15 Lakeview Residency, West End', '9876500002', 2),
(103, 'Kiran Teja', '2003-01-10', 'Male', '9876543212', 'kiran.teja@example.com', 'A+', '88 Palm Grove, East Ring Road', '9876500003', 3),
(104, 'Sneha Kapoor', '1998-11-05', 'Female', '9876543213', 'sneha.k@example.com', 'AB+', '12 Hilltop Terrace, Sector 4', '9876500004', NULL),
(105, 'Vikram Mehta', '1995-07-22', 'Male', '9876543214', 'vikram.m@example.com', 'O-', '23 Maple Crest, Tech Zone', '9876500005', NULL);

-- 4. Insert Doctors
INSERT INTO doctor (DoctorID, DoctorName, Specialization, Qualifications, Phone, Email, DepartmentID, ConsultationFee, RoomNumber, AvailableDays, UserID) VALUES
(201, 'Dr. Priya Sharma', 'Cardiologist', 'MBBS, MD, DM (Cardiology)', '9000000001', 'dr.priya@clinic.org', 1, 850.00, 'Cabin 101', 'Mon, Wed, Fri', 4),
(202, 'Dr. Arjun Verma', 'General Physician', 'MBBS, MD (Internal Medicine)', '9000000002', 'dr.arjun@clinic.org', 2, 500.00, 'Cabin 102', 'Mon - Sat', 5),
(203, 'Dr. Meera Iyer', 'Dermatologist', 'MBBS, MD (DVL)', '9000000003', 'dr.meera@clinic.org', 3, 650.00, 'Cabin 201', 'Tue, Thu, Sat', 6),
(204, 'Dr. Rajesh Patel', 'Pediatrician', 'MBBS, DCH, DNB', '9000000004', 'dr.rajesh@clinic.org', 4, 600.00, 'Cabin 202', 'Mon - Fri', NULL);

-- 5. Insert Appointments
INSERT INTO appointment (AppointmentID, PatientID, DoctorID, AppointmentDate, Reason, Symptoms, Diagnosis, DoctorNotes, Status) VALUES
(301, 101, 201, '2026-10-05 10:00:00', 'Cardiac checkup', 'Mild chest discomfort after stairs', 'Mild sinus tachycardia', 'Rest recommended; ECG clean', 'Confirmed'),
(302, 102, 202, '2026-10-04 11:30:00', 'Viral fever and fatigue', 'Fever of 101F, body aches, sore throat', 'Acute viral nasopharyngitis', 'Hydration and 3 days rest advised', 'Completed'),
(303, 103, 201, '2026-10-06 09:30:00', 'Routine BP evaluation', 'Occasional dizziness', NULL, NULL, 'Scheduled'),
(304, 104, 203, '2026-10-04 14:00:00', 'Skin allergy consultation', 'Dry itchy rash on forearm', 'Contact dermatitis', 'Avoid chemical soaps; topical balm', 'Completed'),
(305, 105, 204, '2026-10-07 16:00:00', 'Child wellness & vaccination', 'Routine booster dose', NULL, NULL, 'Scheduled'),
(306, 101, 202, '2026-10-02 09:00:00', 'Seasonal allergy', 'Sneezing and runny nose', 'Allergic rhinitis', 'Antihistamines prescribed', 'Completed');

-- 6. Insert Prescriptions
INSERT INTO prescription (PrescriptionID, AppointmentID, Medicine, Dosage, Duration, Instructions) VALUES
(401, 302, 'Paracetamol', '650 mg', '3 days', 'Take 1 tablet after meals when fever occurs'),
(402, 302, 'Cetirizine', '10 mg', '5 days', 'Take 1 tablet at night before sleeping'),
(403, 301, 'Aspirin (Ecosprin)', '75 mg', '14 days', 'Take once daily after breakfast'),
(404, 304, 'Hydrocortisone Cream', '1%', '7 days', 'Apply thin layer twice daily on affected area'),
(405, 304, 'Loratadine', '10 mg', '5 days', 'Take 1 tablet once daily morning'),
(406, 306, 'Montelukast + Levocetirizine', '10mg/5mg', '10 days', 'Take 1 tablet at bedtime');

-- 7. Insert Bills (Corresponding to appointments)
INSERT INTO bill (BillID, AppointmentID, Amount, Tax, PaymentStatus, PaymentMethod, PaidAt) VALUES
(501, 301, 850.00, 42.50, 'Pending', 'Pending', NULL),
(502, 302, 500.00, 25.00, 'Paid', 'UPI', '2026-10-04 12:15:00'),
(503, 303, 850.00, 42.50, 'Pending', 'Pending', NULL),
(504, 304, 650.00, 32.50, 'Paid', 'Card', '2026-10-04 14:45:00'),
(505, 305, 600.00, 30.00, 'Pending', 'Pending', NULL),
(506, 306, 500.00, 25.00, 'Paid', 'Cash', '2026-10-02 09:40:00');

-- ============================================================================
-- TRIGGERS (Automated Data Integrity & Events)
-- ============================================================================

DELIMITER $$

-- Trigger 1: Auto-generate bill when an appointment is inserted if not already generated
DROP TRIGGER IF EXISTS trg_appointment_auto_bill$$
CREATE TRIGGER trg_appointment_auto_bill
AFTER INSERT ON appointment
FOR EACH ROW
BEGIN
    DECLARE v_fee DECIMAL(10,2);
    SELECT ConsultationFee INTO v_fee FROM doctor WHERE DoctorID = NEW.DoctorID;
    
    IF v_fee IS NOT NULL THEN
        INSERT IGNORE INTO bill (AppointmentID, Amount, Tax, PaymentStatus, PaymentMethod)
        VALUES (NEW.AppointmentID, v_fee, ROUND(v_fee * 0.05, 2), 'Pending', 'Pending');
    END IF;
END$$

-- Trigger 2: Prevent scheduling appointments in the past
DROP TRIGGER IF EXISTS trg_prevent_past_appointment$$
CREATE TRIGGER trg_prevent_past_appointment
BEFORE INSERT ON appointment
FOR EACH ROW
BEGIN
    IF NEW.AppointmentDate < NOW() - INTERVAL 10 MINUTE THEN
        SIGNAL SQLSTATE '45000' 
        SET MESSAGE_TEXT = 'Cannot schedule an appointment in the past.';
    END IF;
END$$

DELIMITER ;
