import urllib.request
import urllib.parse
import http.cookiejar
import re

BASE_URL = "http://127.0.0.1:5000"

class TestClient:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def get(self, path):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        try:
            with self.opener.open(req) as resp:
                body = resp.read().decode('utf-8')
                return resp.status, body, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8'), e.geturl()

    def post(self, path, data=None):
        encoded_data = b""
        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}{path}", data=encoded_data)
        try:
            with self.opener.open(req) as resp:
                body = resp.read().decode('utf-8')
                return resp.status, body, resp.geturl()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8'), e.geturl()

def run_tests():
    print("=" * 65)
    print("VERIFYING USER SPECIFIC ENHANCEMENTS")
    print("=" * 65)

    # 1. Verify Home Page matches ChatGPT image elements
    print("\n[1] Checking Hero Section & ChatGPT Image Alignment...")
    c_guest = TestClient()
    status, body, url = c_guest.get("/")
    assert status == 200
    assert "hero-doctor-center-photo" in body
    assert "hero_doctor_patient_clean.png" in body
    assert "Access Patient Portal" in body
    assert "Register as Patient" in body
    assert "OPD Timings" in body
    assert "Digital Pharmacy" in body
    assert "Cashless Billing" in body
    assert "Emergency Assistance" in body
    print("  [PASS] Hero section verified with doctor-patient graphic, rich cards & emergency button")

    # 2. Verify Login Page: Admin is HIDDEN, only Patient and Doctor buttons shown
    print("\n[2] Checking Login Page (Admin Hidden, Only Patient & Doctor Shown)...")
    status, body, url = c_guest.get("/login")
    assert status == 200
    assert "Patient Portal Demo" in body
    assert "Doctor Console Demo" in body
    assert "Admin Desk Demo" not in body, "Admin Demo button must be hidden from public login!"
    print("  [PASS] Verified: Admin demo button is hidden from public login view")

    # 3. Verify Admin can still log in with admin/admin123
    print("\n[3] Checking Admin Login with Credentials...")
    c_admin = TestClient()
    status, body, url = c_admin.post("/login", {'username': 'admin', 'password': 'admin123'})
    assert status == 200
    assert "Administration" in body or "ADMIN" in body
    print("  [PASS] Verified: Admin logs in successfully to Admin Console")

    # 4. Verify Admin Doctors Page shows Edit & Delete actions
    print("\n[4] Checking Admin Doctors Page for Edit & Delete Actions...")
    status, body, url = c_admin.get("/doctors")
    assert status == 200
    assert "Edit" in body or "editDocModal" in body
    assert "delete" in body.lower()
    print("  [PASS] Verified: Admin doctors view renders Edit and Delete action controls")

    # 5. Add a temporary doctor, edit them with SQL, and delete them with SQL
    print("\n[5] Testing SQL-backed Doctor Add -> Edit -> Delete Flow...")
    # Add temporary test doctor
    c_admin.post("/doctors/add", {
        'doctor_name': 'Dr. Test Surgeon',
        'department_id': '1',
        'specialization': 'Cardiac Surgeon',
        'qualifications': 'MBBS, MS, MCh',
        'consultation_fee': '750',
        'room_number': 'Cabin 999',
        'available_days': 'Mon - Wed',
        'phone': '9111222333',
        'email': 'dr.test@clinic.org',
        'username': 'drtestsurgeon',
        'password': 'doctor123'
    })

    # Find the doctor in doctors list
    status, body, url = c_admin.get("/doctors")
    assert "Dr. Test Surgeon" in body
    match_doc = re.search(r'Dr\. Test Surgeon.*?editDocModal-(\d+)', body, re.DOTALL)
    assert match_doc, "Could not find edit modal for newly created doctor"
    test_doc_id = int(match_doc.group(1))
    print(f"  [PASS] Identified newly created test doctor #{test_doc_id}")

    # Edit doctor via SQL UPDATE
    status_edit, body_edit, url_edit = c_admin.post(f"/doctors/{test_doc_id}/edit", {
        'doctor_name': 'Dr. Test Surgeon Senior',
        'department_id': '1',
        'specialization': 'Senior Chief Cardiac Surgeon',
        'qualifications': 'MBBS, MS, MCh, FACS',
        'consultation_fee': '999',
        'room_number': 'Suite 1000',
        'available_days': 'Daily',
        'phone': '9111222333',
        'email': 'dr.chief@clinic.org'
    })
    assert status_edit == 200
    assert "Dr. Test Surgeon Senior" in body_edit
    assert "Senior Chief Cardiac Surgeon" in body_edit
    print(f"  [PASS] Successfully executed SQL UPDATE for Dr. #{test_doc_id}")

    # Delete doctor via SQL DELETE
    status_del, body_del, url_del = c_admin.post(f"/doctors/{test_doc_id}/delete")
    if status_del != 200:
        print(f"DEBUG DELETE FAILED: status={status_del}, url={url_del}, body={body_del[:400]}")
    assert status_del == 200
    assert "deleted successfully" in body_del
    # After redirect & flash message consumed, verify doctor is gone from list
    status_list, body_list, _ = c_admin.get("/doctors")
    assert "Dr. Test Surgeon Senior" not in body_list
    print(f"  [PASS] Successfully executed SQL DELETE for Dr. #{test_doc_id}")

    # 6. Verify department badge color in dashboard.html matches user_dept_target.png
    print("\n[6] Checking Department Badge Color in Dashboard...")
    status, body, url = c_admin.get("/dashboard")
    assert status == 200
    assert 'background:#f1f5f9; color:var(--text-body);' in body
    print("  [PASS] Verified: Department badge color updated to target slate palette")

    print("\n" + "=" * 65)
    print("ALL USER ENHANCEMENT TESTS PASSED 100%!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
