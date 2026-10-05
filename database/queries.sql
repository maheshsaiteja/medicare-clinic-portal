-- ============================================================================
-- CLINIC MANAGEMENT SYSTEM — ADVANCED SQL QUERY SUITE
-- Comprehensive SQL Queries: Multi-Table Joins, Aggregates, Subqueries,
-- Window Functions, Stored Procedure Calls, and Analytics Views
-- ============================================================================

USE clinic_management;

-- ----------------------------------------------------------------------------
-- 1. MULTI-TABLE RELATIONAL JOINS
-- ----------------------------------------------------------------------------

-- Query 1.1: 4-Way Comprehensive Join (Appointment + Patient + Doctor + Department + Bill)
-- Retrieves complete clinical visit sheet with doctor department and invoice status
SELECT 
    a.AppointmentID,
    p.PatientName,
    p.Phone AS PatientContact,
    d.DoctorName,
    dep.DepartmentName,
    a.AppointmentDate,
    a.Reason,
    a.Status AS VisitStatus,
    COALESCE(b.TotalAmount, 0.00) AS BillAmount,
    COALESCE(b.PaymentStatus, 'Unbilled') AS PaymentStatus
FROM appointment a
INNER JOIN patient p ON a.PatientID = p.PatientID
INNER JOIN doctor d ON a.DoctorID = d.DoctorID
INNER JOIN department dep ON d.DepartmentID = dep.DepartmentID
LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
ORDER BY a.AppointmentDate DESC;

-- Query 1.2: Prescriptions Joined with Patient & Doctor Records
-- Useful for pharmacy dispensing desk
SELECT 
    pr.PrescriptionID,
    p.PatientName,
    d.DoctorName,
    a.AppointmentDate,
    pr.Medicine,
    pr.Dosage,
    pr.Duration,
    pr.Instructions
FROM prescription pr
JOIN appointment a ON pr.AppointmentID = a.AppointmentID
JOIN patient p ON a.PatientID = p.PatientID
JOIN doctor d ON a.DoctorID = d.DoctorID
ORDER BY a.AppointmentDate DESC;

-- ----------------------------------------------------------------------------
-- 2. AGGREGATE FUNCTIONS & GROUP BY WITH HAVING
-- ----------------------------------------------------------------------------

-- Query 2.1: Doctor Performance Metrics (Appointment Count & Total Revenue Generated)
SELECT 
    d.DoctorID,
    d.DoctorName,
    dep.DepartmentName,
    COUNT(a.AppointmentID) AS TotalAppointments,
    SUM(CASE WHEN a.Status = 'Completed' THEN 1 ELSE 0 END) AS CompletedAppointments,
    COALESCE(SUM(b.TotalAmount), 0.00) AS TotalRevenueGenerated
FROM doctor d
INNER JOIN department dep ON d.DepartmentID = dep.DepartmentID
LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID AND b.PaymentStatus = 'Paid'
GROUP BY d.DoctorID, d.DoctorName, dep.DepartmentName
HAVING COUNT(a.AppointmentID) > 0
ORDER BY TotalRevenueGenerated DESC;

-- Query 2.2: Department-wise Revenue & Billing Audit
SELECT 
    dep.DepartmentName,
    COUNT(DISTINCT d.DoctorID) AS ActiveDoctors,
    COUNT(DISTINCT a.AppointmentID) AS TotalBookings,
    COALESCE(SUM(b.Amount), 0.00) AS SubtotalBilled,
    COALESCE(SUM(b.Tax), 0.00) AS TotalTaxCollected,
    COALESCE(SUM(b.TotalAmount), 0.00) AS GrossRevenue,
    COALESCE(SUM(CASE WHEN b.PaymentStatus = 'Paid' THEN b.TotalAmount ELSE 0 END), 0.00) AS RealizedRevenue,
    COALESCE(SUM(CASE WHEN b.PaymentStatus = 'Pending' THEN b.TotalAmount ELSE 0 END), 0.00) AS PendingReceivables
FROM department dep
LEFT JOIN doctor d ON dep.DepartmentID = d.DepartmentID
LEFT JOIN appointment a ON d.DoctorID = a.DoctorID
LEFT JOIN bill b ON a.AppointmentID = b.AppointmentID
GROUP BY dep.DepartmentID, dep.DepartmentName
ORDER BY GrossRevenue DESC;

-- Query 2.3: Billing Collection by Payment Mode
SELECT 
    PaymentMethod,
    COUNT(BillID) AS TransactionCount,
    SUM(TotalAmount) AS TotalCollected,
    ROUND(AVG(TotalAmount), 2) AS AverageBillValue
FROM bill
WHERE PaymentStatus = 'Paid'
GROUP BY PaymentMethod;

-- ----------------------------------------------------------------------------
-- 3. SUBQUERIES & ADVANCED WINDOW FUNCTIONS (MySQL 8.0+)
-- ----------------------------------------------------------------------------

-- Query 3.1: Correlated Subquery — Patients who have visited more than once (Frequent Patients)
SELECT 
    p.PatientID,
    p.PatientName,
    p.Phone,
    p.BloodGroup,
    (SELECT COUNT(*) FROM appointment a WHERE a.PatientID = p.PatientID) AS VisitCount
FROM patient p
WHERE (SELECT COUNT(*) FROM appointment a WHERE a.PatientID = p.PatientID) > 1
ORDER BY VisitCount DESC;

-- Query 3.2: Window Function — Ranked Recent Visits per Doctor (ROW_NUMBER)
-- Retrieves the most recent appointment for every doctor
WITH RankedDoctorVisits AS (
    SELECT 
        a.AppointmentID,
        d.DoctorName,
        p.PatientName,
        a.AppointmentDate,
        a.Status,
        ROW_NUMBER() OVER (PARTITION BY d.DoctorID ORDER BY a.AppointmentDate DESC) AS VisitRank
    FROM appointment a
    JOIN doctor d ON a.DoctorID = d.DoctorID
    JOIN patient p ON a.PatientID = p.PatientID
)
SELECT * FROM RankedDoctorVisits WHERE VisitRank = 1;

-- Query 3.3: Window Function — Running Cumulative Revenue by Date
SELECT 
    b.BillID,
    b.PaidAt,
    b.TotalAmount,
    b.PaymentMethod,
    SUM(b.TotalAmount) OVER (ORDER BY b.PaidAt ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS CumulativeRevenue
FROM bill b
WHERE b.PaymentStatus = 'Paid' AND b.PaidAt IS NOT NULL
ORDER BY b.PaidAt ASC;

-- ----------------------------------------------------------------------------
-- 4. VIEWS DEMONSTRATION & REPORTING
-- ----------------------------------------------------------------------------

-- View 4.1: View all Active & Scheduled Visits
SELECT * FROM patient_appointment_report 
WHERE AppointmentStatus IN ('Scheduled', 'Confirmed')
ORDER BY AppointmentDate ASC;

-- View 4.2: Doctor Schedules & Workload
SELECT * FROM v_doctor_schedules;

-- View 4.3: Financial Summary across Departments
SELECT * FROM v_billing_summary;

-- View 4.4: Quick Executive Dashboard Stats
SELECT * FROM v_clinic_stats;

-- ----------------------------------------------------------------------------
-- 5. STORED PROCEDURES & TRIGGERS DEMO
-- ----------------------------------------------------------------------------

-- Demo 5.1: Call Procedure to Book an Appointment
-- CALL sp_book_appointment(101, 201, '2026-10-15 11:00:00', 'Follow-up Cardiology', 'Routine pulse check', @new_appt_id);
-- SELECT @new_appt_id AS CreatedAppointmentID;

-- Demo 5.2: Call Procedure to Process Bill Payment
-- CALL sp_pay_bill(501, 'UPI');
