"""
Diagnostic & Verification Tool for MediCare+ Clinic Management System
Tests connection to local MySQL or Aiven Cloud MySQL with SSL verification.
Usage:
    python test_connection.py
"""

import sys
import os

# Safe UTF-8 output handling on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import db_config

def mask_secret(s):
    if not s:
        return "(empty)"
    if len(s) <= 4:
        return "****"
    return s[:2] + "*" * (len(s) - 4) + s[-2:]

def run_diagnostics():
    print("=" * 65)
    print("   MEDICARE+ DATABASE CONNECTION & HEALTH DIAGNOSTIC")
    print("=" * 65)

    cfg = db_config.get_db_config()
    target_type = "Aiven Cloud MySQL" if cfg['is_aiven'] else ("Cloud MySQL" if cfg['is_cloud'] else "Local MySQL")
    print(f"Target Service       : {target_type}")
    print(f"Host                 : {cfg['host']}")
    print(f"Port                 : {cfg['port']}")
    print(f"User                 : {cfg['user']}")
    print(f"Password             : {mask_secret(cfg['password'])}")
    print(f"Target Database      : {cfg['database']}")
    print(f"SSL CA Certificate   : {cfg['ssl_ca'] if cfg['ssl_ca'] else 'Auto TLS Mode (No CA file specified)'}")
    print("-" * 65)
    print("Attempting SSL connection to MySQL server...")

    try:
        conn = db_config.get_mysql_connection(timeout=12)
        cur = conn.cursor()
        print("[+] SUCCESS: Connected to MySQL server successfully!")

        # Query basic metadata
        cur.execute("SELECT VERSION(), CURRENT_USER(), DATABASE();")
        row = cur.fetchone()
        version, user, active_db = row if row else ("Unknown", "Unknown", "Unknown")
        print(f"  * MySQL Version    : {version}")
        print(f"  * Authenticated As : {user}")
        print(f"  * Active Database  : {active_db}")

        # Check SSL Cipher
        try:
            cur.execute("SHOW STATUS LIKE 'Ssl_cipher';")
            ssl_row = cur.fetchone()
            ssl_cipher = ssl_row[1] if (ssl_row and len(ssl_row) > 1 and ssl_row[1]) else "None / Unencrypted"
            print(f"  * SSL/TLS Cipher   : {ssl_cipher}")
        except Exception:
            pass

        # Check tables & schema integrity
        expected_tables = ['users', 'department', 'patient', 'doctor', 'appointment', 'prescription', 'bill']
        print("\nChecking relational database entities...")
        found_tables = []
        for tbl in expected_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
                count = cur.fetchone()[0]
                print(f"  [OK] Table '{tbl.ljust(14)}': {str(count).rjust(4)} records")
                found_tables.append(tbl)
            except Exception:
                print(f"  [--] Table '{tbl.ljust(14)}': NOT FOUND or uninitialized")

        cur.close()
        conn.close()

        print("-" * 65)
        if len(found_tables) == len(expected_tables):
            print("STATUS: HEALTHY & READY FOR DEPLOYMENT!")
            print(f"The web application can now run on Render and connect to {target_type}.")
        elif len(found_tables) == 0:
            print("STATUS: CONNECTED BUT TABLES NOT INITIALIZED YET.")
            print("Run the initialization command below to create the schema and seed data:")
            print("    python init_db.py")
        else:
            print(f"STATUS: PARTIAL SCHEMA ({len(found_tables)}/{len(expected_tables)} tables found).")
            print("Run the initialization command to ensure complete schema:")
            print("    python init_db.py --force")
        print("=" * 65)
        return True

    except Exception as ex:
        print("\n[!] CONNECTION FAILED:")
        print(f"    Error: {ex}\n")
        print("-" * 65)
        print("TROUBLESHOOTING GUIDE:")
        if cfg['is_aiven']:
            print("  1. Verify your Aiven MySQL Service is running in the Aiven Console (state: RUNNING).")
            print("  2. In Aiven Console, copy the 'Service URI' and set it as:")
            print("     DATABASE_URL=mysql://avnadmin:PASSWORD@HOST:PORT/defaultdb?ssl-mode=REQUIRED")
            print("  3. Verify that your IP or 0.0.0.0/0 is allowed in Aiven 'Advanced configuration -> IP filters'")
            print("     (Aiven enables all IPs by default unless IP filter rules are configured).")
        else:
            print("  1. Verify MySQL service is active and listening on port 3306.")
            print("  2. Double-check your DB_PASSWORD in .env.")
            print("  3. If you want to use Aiven Cloud MySQL, set DATABASE_URL or DB_HOST in your .env.")
        print("=" * 65)
        return False

if __name__ == '__main__':
    success = run_diagnostics()
    sys.exit(0 if success else 1)
