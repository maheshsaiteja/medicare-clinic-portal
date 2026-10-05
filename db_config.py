"""
Database Configuration & Cloud Connection Manager for MediCare+
Supports local MySQL, SQLite mirror, Render Cloud, and Aiven Managed Cloud MySQL.
Handles URI parsing (DATABASE_URL / MYSQL_URL / AIVEN_SERVICE_URI), SSL certificates,
and automatic CA certificate creation from environment variables.
"""

import os
import sys
import tempfile
import urllib.parse
from pathlib import Path

# Load .env file if available
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('\'"')
                    os.environ.setdefault(key, val)

load_env()

def get_db_config():
    """
    Parses and unifies database configuration from either a connection URI
    (DATABASE_URL, MYSQL_URL, AIVEN_SERVICE_URI, DB_URI) or individual variables.
    """
    # 1. Check for connection URI
    db_uri = (
        os.getenv('DATABASE_URL') or 
        os.getenv('MYSQL_URL') or 
        os.getenv('AIVEN_SERVICE_URI') or 
        os.getenv('DB_URI')
    )

    host = 'localhost'
    port = 3306
    user = 'root'
    password = ''
    database = 'clinic_management'
    ssl_ca = os.getenv('DB_SSL_CA')
    ssl_mode = 'REQUIRED'

    if db_uri:
        # Standardize scheme (handle mysql://, mysql+pymysql://, mysql2://)
        clean_uri = db_uri
        if clean_uri.startswith('mysql+'):
            clean_uri = 'mysql' + clean_uri[clean_uri.find(':'):]
        
        parsed = urllib.parse.urlparse(clean_uri)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = int(parsed.port)
        if parsed.username:
            user = parsed.username
        if parsed.password:
            password = urllib.parse.unquote(parsed.password)
        
        # Database name from URI path
        path_db = parsed.path.strip('/')
        if path_db:
            database = path_db
        elif 'aivencloud.com' in host.lower():
            # Aiven's default database name
            database = 'defaultdb'

        # Query parameters (e.g. ?ssl-mode=REQUIRED&ssl_ca=...)
        if parsed.query:
            q_params = urllib.parse.parse_qs(parsed.query)
            if 'ssl-mode' in q_params:
                ssl_mode = q_params['ssl-mode'][0]
            elif 'ssl_mode' in q_params:
                ssl_mode = q_params['ssl_mode'][0]
            if 'ssl_ca' in q_params and not ssl_ca:
                ssl_ca = q_params['ssl_ca'][0]
    else:
        # 2. Fall back to individual variables
        host = os.getenv('DB_HOST', host)
        try:
            port = int(os.getenv('DB_PORT', port))
        except (ValueError, TypeError):
            port = 3306
        user = os.getenv('DB_USER', user)
        password = os.getenv('DB_PASSWORD', password)
        database = os.getenv('DB_NAME', database)

    is_aiven = 'aivencloud.com' in host.lower()
    is_cloud = (
        is_aiven or 
        bool(os.getenv('RENDER')) or 
        os.getenv('FLASK_ENV') == 'production' or 
        os.getenv('REQUIRE_MYSQL', '').lower() in ('1', 'true', 'yes') or 
        host not in ('localhost', '127.0.0.1')
    )

    # 3. Resolve CA certificate
    resolved_ca = resolve_ssl_ca(ssl_ca)

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database,
        'ssl_ca': resolved_ca,
        'ssl_mode': ssl_mode,
        'is_aiven': is_aiven,
        'is_cloud': is_cloud
    }

def resolve_ssl_ca(explicit_ca_path=None):
    """
    Finds or materializes the SSL CA certificate:
    1. If DB_SSL_CERT_CONTENT or AIVEN_CA_CERT contains PEM text, writes it to a file.
    2. If DB_SSL_CA contains PEM text directly, writes it to a file.
    3. If explicit_ca_path exists as a file, returns its path.
    4. If 'ca.pem' exists in workspace, returns it.
    5. Returns None if no certificate is provided.
    """
    cert_content = os.getenv('DB_SSL_CERT_CONTENT') or os.getenv('AIVEN_CA_CERT')
    
    # If the user pasted raw certificate text into DB_SSL_CA
    if explicit_ca_path and 'BEGIN CERTIFICATE' in explicit_ca_path:
        cert_content = explicit_ca_path
        explicit_ca_path = None

    if cert_content and 'BEGIN CERTIFICATE' in cert_content:
        target_path = os.path.join(os.path.dirname(__file__), 'aiven_ca.pem')
        try:
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(cert_content.strip() + '\n')
            return target_path
        except Exception as e:
            print(f"[Warning] Failed to write CA certificate to {target_path}: {e}")

    if explicit_ca_path and os.path.exists(explicit_ca_path):
        return explicit_ca_path

    # Check for default ca.pem in workspace
    default_ca = os.path.join(os.path.dirname(__file__), 'ca.pem')
    if os.path.exists(default_ca):
        return default_ca

    return None

_connection_pool = None
_pool_lock = None

def get_mysql_connection(database=None, timeout=15):
    """
    Creates and returns a MySQL connection via connection pooling or direct connect,
    configured with SSL encryption for Aiven and cloud databases.
    Connection pooling eliminates TLS handshake latency on repeated queries.
    """
    import mysql.connector

    cfg = get_db_config()
    target_db = database if database is not None else cfg['database']

    # Use connection pooling for the primary application database
    is_primary_db = (database is None or database == cfg['database'])
    if is_primary_db:
        global _connection_pool, _pool_lock
        if _pool_lock is None:
            import threading
            _pool_lock = threading.Lock()

        if _connection_pool is None:
            with _pool_lock:
                if _connection_pool is None:
                    try:
                        from mysql.connector import pooling
                        pool_kwargs = {
                            'host': cfg['host'],
                            'port': cfg['port'],
                            'user': cfg['user'],
                            'password': cfg['password'],
                            'database': cfg['database'],
                            'ssl_disabled': False,
                            'connection_timeout': timeout,
                            'charset': 'utf8mb4',
                            'use_pure': True
                        }
                        if cfg['ssl_ca']:
                            pool_kwargs['ssl_ca'] = cfg['ssl_ca']
                            pool_kwargs['ssl_verify_cert'] = True
                        else:
                            pool_kwargs['ssl_verify_cert'] = False
                            pool_kwargs['ssl_verify_identity'] = False

                        _connection_pool = pooling.MySQLConnectionPool(
                            pool_name="medicare_pool",
                            pool_size=5,
                            pool_reset_session=True,
                            **pool_kwargs
                        )
                    except Exception as pool_err:
                        _connection_pool = None

        if _connection_pool is not None:
            try:
                return _connection_pool.get_connection()
            except Exception:
                pass

    # Direct connection fallback
    kwargs = {
        'host': cfg['host'],
        'port': cfg['port'],
        'user': cfg['user'],
        'password': cfg['password'],
        'ssl_disabled': False,
        'connection_timeout': timeout,
        'charset': 'utf8mb4',
        'use_pure': True
    }

    if target_db:
        kwargs['database'] = target_db

    if cfg['ssl_ca']:
        kwargs['ssl_ca'] = cfg['ssl_ca']
        kwargs['ssl_verify_cert'] = True
    else:
        kwargs['ssl_verify_cert'] = False
        kwargs['ssl_verify_identity'] = False

    return mysql.connector.connect(**kwargs)

def get_display_engine_name():
    """Returns human-friendly engine name for UI badges and diagnostics."""
    cfg = get_db_config()
    if cfg['is_aiven']:
        return f"Aiven Cloud MySQL ({cfg['database']})"
    elif cfg['is_cloud']:
        return f"Cloud MySQL ({cfg['database']})"
    else:
        return f"MySQL 8.0+ ({cfg['database']})"
