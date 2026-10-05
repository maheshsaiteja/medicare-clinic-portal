# MediCare+ Enterprise Clinic Management System

A high-performance, full-stack healthcare web application and relational database management system built with **MySQL 8.0+**, **Python Flask**, and **Modern CSS/JS**.

---

## 🌟 Upgraded Features & Capabilities

### 1. Robust Relational SQL Architecture (3NF Normalization)
- **7 Fully Relational Entities:** `users`, `department`, `patient`, `doctor`, `appointment`, `prescription`, and `bill`.
- **Auto-Increment Primary Keys:** Enabled on all entities with consistent ID ranges (`PatientID` starting at 101, `DoctorID` at 201, `AppointmentID` at 301, etc.).
- **Data Integrity & Constraints:** `CHECK (Amount >= 0)`, `CHECK (ConsultationFee >= 0)`, `UNIQUE` constraints on phones/usernames/department names, and cascading foreign keys.
- **Audit Columns:** Automatic `created_at` and `updated_at` timestamps for clinical governance.
- **Performance Indexes:** Strategic B-tree indexes on foreign keys, visit dates, and payment statuses for sub-millisecond query execution.

### 2. Advanced SQL Procedures, Triggers & Views
- **Stored Procedures:**
  - `sp_book_appointment`: Validates doctor availability and automatically creates consultation + initial bill.
  - `sp_complete_consultation`: Atomically updates diagnosis, clinical notes, and inserts prescribed medications.
  - `sp_pay_bill`: Records bill payment status, payment mode (`UPI`, `Card`, `Cash`, `Insurance`), and audit timestamp.
- **Triggers:**
  - `trg_appointment_auto_bill`: Automatically generates a pending billing invoice with consultation fee + 5% GST whenever an appointment is created.
  - `trg_prevent_past_appointment`: Prevents booking appointments in the past.
- **SQL Analytical Views:**
  - `patient_appointment_report`: Comprehensive multi-table view joining appointments, patients, doctors, departments, and invoices.
  - `v_doctor_schedules`: Summarizes scheduled vs completed patient loads per doctor.
  - `v_billing_summary`: Department-level gross billed amounts, realized revenue, and outstanding dues.
  - `v_clinic_stats`: Fast summary metrics for high-level administration dashboards.

### 3. Modern Web Application & Clinical Workflows
- **Multi-Role Authentication:** Dedicated portal experiences for **Patients**, **Doctors**, and **Administrators** with 1-click demo login buttons.
- **Patient Self-Registration (`/register`):** New patients can sign up online with DOB, gender, blood group, and contact details.
- **Appointment Booking & Management (`/appointments`):** Interactive booking with doctor consultation fee breakdown, symptoms notes, and status filter tabs.
- **Electronic Prescriptions (`/prescriptions`):** Doctors can prescribe medications with dosage, duration, and instructions directly from appointments.
- **Billing & Instant Invoices (`/bills` & `/bills/<id>/invoice`):** Full itemized invoices with GST calculation, settlement modal, and printable receipt stylesheet (`Ctrl + P`).
- **Executive Analytics (`/analytics`):** Real-time financial reports, department patient loads, and doctor rankings.
- **Fail-Safe Database Adapter:** Primary support for MySQL 8.0+ with seamless zero-crash local SQLite mirror if MySQL server credentials are not configured yet.

---

## 🚀 Quick Start Guide

### Step 1: Initialize Database
To initialize MySQL (or refresh seed data), simply run:
```powershell
python init_db.py
```
> *Note: If you have a root password on MySQL, configure `.env` as shown in Step 2.*

### Step 2: Configure MySQL (Optional / Production)
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```
Edit `.env` with your MySQL credentials:
```ini
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=clinic_management
```

### Step 3: Start the Web Application
```powershell
python app.py
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

---

---

## ☁️ Deploying to Render (render.com) — Fast & Zero Setup

The system is fully configured to deploy on Render in **1 click** with zero external database requirements:

### Method 1: Instant 1-Click Deployment (Recommended)
1. Push your repository to GitHub:
   ```powershell
   git add .
   git commit -m "Optimize Render cloud performance and upgrade UI"
   git push origin main
   ```
2. In [Render Dashboard](https://dashboard.render.com/):
   - Click **New +** -> **Web Service** (or **Blueprint**).
   - Select your GitHub repository (`clinic-management-system`).
   - If setting up manually as a **Web Service**:
     - **Runtime:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt && python init_db.py`
     - **Start Command:** `gunicorn app:app --workers 2 --threads 4 --timeout 60`
     - **Plan:** Free
3. Click **Deploy Web Service**!
   *(The app will start up in under 60 seconds with full sample doctors, patients, appointments, and billing data).*

### ⚡ Why Render Free-Tier Links Take Time & How to Solve It:
> **Why Render takes time to open initially:**  
> On Render's **Free Tier**, inactive web services spin down (sleep) after 15 minutes of inactivity. When you open your `.onrender.com` link after it has slept, Render takes 45–50 seconds to spin up the container ("Cold Start"). Once awake, every page loads in **under 15 milliseconds**!
>
> **How to keep your Render link 100% fast (0-Second Load Time):**
> 1. We built a dedicated, zero-overhead endpoint at `https://your-app.onrender.com/healthz`.
> 2. Create a free account at [cron-job.org](https://cron-job.org/) or [uptimerobot.com](https://uptimerobot.com/).
> 3. Add a free monitor targeting your `/healthz` URL every **10 minutes**.
> 4. Render will **never sleep**, and your live site will open instantly every single time!

---

### Method 2: Optional Aiven Cloud MySQL Integration
If you wish to attach an external managed cloud MySQL database:
1. In your Render Web Service dashboard, go to **Environment** tab.
2. Add the environment variable:
   - `DATABASE_URL`: `mysql://avnadmin:your_password@your-host.aivencloud.com:port/defaultdb?ssl-mode=REQUIRED`
3. Render will automatically redeploy and switch the backend to Aiven Cloud MySQL with SSL/TLS encryption!


---

## 🔑 Demo Login Accounts

| Role | Username | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| **Patient** | `patient101` | `patient123` | Book consultations, view own prescriptions, pay bills |
| **Doctor** | `doctor201` | `doctor123` | Manage appointments, update diagnoses, prescribe medicine |
| **Admin** | `admin` | `admin123` | Full clinic management, analytics, patient directory |

*(1-click demo buttons are provided directly on the `/login` page for fast evaluation)*

---

## 📁 Project Structure

```text
clinic_management_system/
├── app.py                   # Main Flask application with 18 endpoints & dual-engine DB adapter
├── db_config.py             # Unified MySQL & Aiven SSL/TLS cloud connection manager
├── init_db.py               # Safe schema executor & database initializer
├── test_connection.py       # Live connection & SSL diagnostic verification tool
├── render.yaml              # Render Blueprint specification for 1-click cloud deployment
├── Procfile                 # Process file for Render web service
├── runtime.txt              # Python runtime version for cloud environment
├── requirements.txt         # Dependencies (Flask, mysql-connector-python, Werkzeug, Gunicorn)
├── .env.example             # Database configuration template with Aiven URI support
├── database/
│   ├── schema.sql           # Enterprise 3NF MySQL schema, views, procedures & triggers
│   └── queries.sql          # Advanced SQL suite (Joins, Aggregates, Window functions)
├── static/
│   ├── css/style.css        # Modern healthcare design system & print stylesheet
│   └── js/main.js           # Client-side live search, demo autofill, and alert handlers
└── templates/
    ├── base.html            # Core layout with sticky header, status bar & toast notifications
    ├── index.html           # Landing page with hero banner & doctor showcase
    ├── login.html           # Authentication with 1-click demo autofill
    ├── register.html        # New patient registration form
    ├── dashboard.html       # Role-based dashboard with KPI cards & recent visits
    ├── appointments.html    # Appointment schedule with status tabs & prescription modal
    ├── new_appointment.html # Consultation booking form
    ├── doctors.html         # Doctor directory with department filters
    ├── patients.html        # Patient registry with search & blood group badges
    ├── prescriptions.html   # Digital prescription cards
    ├── bills.html           # Invoices list with settlement action
    ├── invoice.html         # Printable official clinical invoice & receipt
    └── analytics.html       # Visual analytics & department performance
```
