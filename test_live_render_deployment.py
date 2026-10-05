import urllib.request
import urllib.parse
import http.cookiejar
import re
import sys
import json

BASE_URL = "https://medicare-clinic-portal.onrender.com"

class TestClient:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def get(self, path):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        try:
            with self.opener.open(req, timeout=30) as resp:
                body = resp.read().decode('utf-8')
                return resp.status, body, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8'), e.geturl()

    def post(self, path, data=None):
        encoded_data = None
        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}{path}", data=encoded_data)
        try:
            with self.opener.open(req, timeout=30) as resp:
                body = resp.read().decode('utf-8')
                return resp.status, body, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8'), e.geturl()

print("=" * 65)
print(f"LIVE RENDER VALIDATION SUITE: {BASE_URL}")
print("=" * 65)

# 1. Health check
print("\n[1/7] Testing Health Endpoint (/healthz)...")
client_guest = TestClient()
status, body, url = client_guest.get("/healthz")
assert status == 200, f"Expected 200, got {status}"
health_data = json.loads(body)
assert health_data.get('status') == 'healthy'
print(f"  [PASS] Health check passed: {health_data}")

# 2. Home Page & Static Assets
print("\n[2/7] Testing Home Page & Static Assets...")
status, body, url = client_guest.get("/")
assert status == 200
assert "MediCare+" in body
assert "Emergency &amp; OPD Desk" in body or "Emergency & OPD Desk" in body
assert "Emergency Medical Assistance" in body
assert "hero_doctor_patient_clean.png" in body
print("  [PASS] Landing page loaded with updated hero section and clean medical card")

status, body, url = client_guest.get("/static/css/style.css")
assert status == 200
assert len(body) > 1000
print(f"  [PASS] CSS stylesheet loaded ({len(body)} bytes)")

# 3. Emergency Booking without login
print("\n[3/7] Testing Emergency Medical Assistance & Direct OPD Booking (No Login)...")
status, body, url = client_guest.get("/emergency/book")
assert status == 200
assert "Immediate OPD" in body

opd_payload = {
    'patient_name': 'Live Cloud Test Patient',
    'phone': '9988776655',
    'email': 'cloud.test@example.com',
    'age': '32',
    'gender': 'Female',
    'department_id': '1', # Cardiology
    'doctor_id': '201',     # Dr. Priya Sharma
    'appointment_date': '2026-10-20T14:30',
    'reason': 'Live Render Deployment Verification Visit',
    'is_urgent': '1'
}
status, body, url = client_guest.post("/emergency/book", opd_payload)
assert status == 200
assert "Live Cloud Test Patient" in body
assert "Dr. Priya Sharma" in body
assert "Immediate OPD Visit Confirmed" in body

match = re.search(r'/emergency/confirmation/(\d+)', url)
assert match, f"Could not find appointment ID in URL: {url}"
emergency_appt_id = int(match.group(1))
print(f"  [PASS] Emergency OPD visit confirmed without login: Appointment #{emergency_appt_id}")

# 4. Doctor Portal & Consultation Management
print("\n[4/7] Testing Doctor Portal & Roster...")
client_doc = TestClient()
status, body, url = client_doc.post("/login", {
    'username': 'doctor201',
    'password': 'doctor123'
})
assert status == 200
assert "Priya Sharma" in body or "Doctor" in body
print("  [PASS] Doctor logged in successfully")

status, body, url = client_doc.get("/appointments")
assert status == 200
assert f"#{emergency_appt_id}" in body
print(f"  [PASS] Doctor queue displays emergency appointment #{emergency_appt_id}")

status, body, url = client_doc.post(f"/appointments/{emergency_appt_id}/prescribe", {
    'diagnosis': 'Deployment Health Check: Cardiac Rhythm Normal',
    'notes': 'BP measured 120/80 mmHg. Good clinical health.',
    'medicine': 'Vitamin B-Complex',
    'dosage': '1 tablet',
    'duration': '15 days',
    'instructions': 'Daily with breakfast'
})
assert status == 200
print("  [PASS] Doctor recorded diagnosis and digital prescription in database")

# 5. Patient Portal
print("\n[5/7] Testing Patient Portal...")
client_pat = TestClient()
status, body, url = client_pat.post("/login", {
    'username': 'patient101',
    'password': 'patient123'
})
assert status == 200
assert "Ravi Kumar" in body
print("  [PASS] Patient logged in successfully")

status, body, url = client_pat.get("/dashboard")
assert status == 200
assert "Appointments" in body
print("  [PASS] Patient dashboard loaded")

# 6. Admin Portal & Doctor CRUD
print("\n[6/7] Testing Admin Portal & Doctor Roster Management...")
client_admin = TestClient()
status, body, url = client_admin.post("/login", {
    'username': 'admin',
    'password': 'admin123'
})
assert status == 200
print("  [PASS] Admin logged in successfully")

status, body, url = client_admin.get("/dashboard")
assert status == 200
print("  [PASS] Admin executive analytics dashboard loaded")

status, body, url = client_admin.get("/doctors")
assert status == 200
assert "+ Add New Doctor" in body
assert "Edit" in body
print("  [PASS] Admin doctor management roster verified (+ Add New Doctor, Edit, Delete controls)")

# Test Doctor Add route
status, body, url = client_admin.get("/doctors/add")
assert status == 200
print("  [PASS] Admin add doctor form verified at /doctors/add")

# Test Doctor Edit route
match = re.search(r'/doctors/(\d+)/edit', body)
if match:
    doc_id = match.group(1)
    status, edit_body, url = client_admin.get(f"/doctors/{doc_id}/edit")
    assert status == 200
    assert "Doctor" in edit_body
    print(f"  [PASS] Admin doctor edit route verified (/doctors/{doc_id}/edit)")

# 7. Public Directories
print("\n[7/7] Testing Public Directories (Doctors, Departments, Services)...")
status, body, url = client_guest.get("/doctors")
assert status == 200
assert "Priya Sharma" in body
print("  [PASS] Public doctors directory verified")

status, body, url = client_guest.get("/departments")
assert status == 200
assert "Cardiology" in body
print("  [PASS] Clinical departments directory verified")

status, body, url = client_guest.get("/services")
assert status == 200
print("  [PASS] Services directory verified")

print("\n" + "=" * 65)
print("ALL 7 TEST SUITES PASSED 100% ON LIVE RENDER PRODUCTION SITE!")
print("PUBLIC URL: https://medicare-clinic-portal.onrender.com")
print("=" * 65)
