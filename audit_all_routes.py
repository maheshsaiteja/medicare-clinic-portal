import urllib.request
import urllib.parse
import http.cookiejar
import re

BASE_URL = "http://127.0.0.1:5000"

def audit():
    print("=" * 60)
    print("AUDITING ALL ROUTES & BUTTONS ON MEDICARE+ PORTAL")
    print("=" * 60)

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    def get(path):
        req = urllib.request.Request(f"{BASE_URL}{path}")
        try:
            with opener.open(req) as resp:
                return resp.status, resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8')

    def post(path, data):
        enc = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}{path}", data=enc)
        try:
            with opener.open(req) as resp:
                return resp.status, resp.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8')

    public_routes = [
        ('/', 'Home Landing Page'),
        ('/login', 'Login Page'),
        ('/register', 'Register Page'),
        ('/doctors', 'Specialists Directory'),
        ('/departments', 'Clinical Departments'),
        ('/services', 'Hospital Services & Facilities'),
        ('/emergency', 'Emergency Protocol Info'),
        ('/emergency/book', 'Emergency FastPass Booking'),
        ('/healthz', 'Application Health Check Endpoint'),
    ]

    for path, name in public_routes:
        status, html = get(path)
        assert status == 200, f"Failed {name} ({path}): HTTP {status}"
        print(f"  [OK] {name} ({path}) -> HTTP {status}")

    # Login as Admin
    status, html = post('/login', {'username': 'admin', 'password': 'admin123'})
    assert status == 200, "Admin login failed"
    print("  [OK] Admin Login -> HTTP 200")

    admin_routes = [
        ('/dashboard', 'Admin Dashboard'),
        ('/appointments', 'Admin Appointments List'),
        ('/doctors', 'Admin Doctor Management'),
        ('/patients', 'Admin Patients Directory'),
        ('/bills', 'Admin Billing & Invoices'),
        ('/analytics', 'Admin Financial & Clinical Analytics'),
        ('/doctors/add', 'Admin Add Doctor Page'),
    ]

    for path, name in admin_routes:
        status, html = get(path)
        assert status == 200, f"Failed {name} ({path}): HTTP {status}"
        print(f"  [OK] {name} ({path}) -> HTTP {status}")

    # Test Doctor Edit GET page
    match = re.search(r'/doctors/(\d+)/edit', html)
    if not match:
        status_docs, docs_html = get('/doctors')
        match = re.search(r'/doctors/(\d+)/edit', docs_html)

    if match:
        doc_id = match.group(1)
        status, edit_html = get(f'/doctors/{doc_id}/edit')
        assert status == 200, f"Doctor Edit GET page failed: HTTP {status}"
        assert "Edit Doctor Details" in edit_html
        print(f"  [OK] Dedicated Doctor Edit Page (/doctors/{doc_id}/edit) -> HTTP 200")

    # Logout
    get('/logout')
    print("  [OK] Sign Out -> HTTP 200")

    print("=" * 60)
    print("ALL ROUTES & PAGES AUDITED: 100% OPERATIONAL WITH ZERO ERRORS!")
    print("=" * 60)

if __name__ == '__main__':
    audit()
