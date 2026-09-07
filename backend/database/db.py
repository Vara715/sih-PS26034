"""
SQLite Database & Cryptographic Audit Ledger
----------------------------------------------
Stores inspection history, OCR results, rule findings, and SHA-256 evidence hashes
to guarantee audit trail integrity.
"""

import sqlite3
import hashlib
import hmac
import base64
import time
import secrets
import json
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("legal_metrology.database")

DB_FILE_PATH = os.path.join(os.path.dirname(__file__), "inspections.db")
JWT_SECRET = os.getenv("JWT_SECRET", "legal_metrology_sih26034_secret_key_2026")
JWT_EXPIRATION_SECONDS = 86400 * 7  # 7-day session token

_DB_INITIALIZED = False


def get_db_connection():
    """Establishes SQLite connection."""
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False):
    """Initializes database tables if they do not exist (cached to avoid redundant per-query calls)."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED and not force:
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_mode TEXT NOT NULL,
            product_category TEXT NOT NULL,
            overall_status TEXT NOT NULL,
            verdict_title TEXT NOT NULL,
            blur_score REAL,
            brightness_score REAL,
            ocr_text TEXT,
            extracted_json TEXT,
            rule_results_json TEXT,
            image_sha256 TEXT NOT NULL,
            evidence_hash TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            badge_or_license TEXT,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

    _DB_INITIALIZED = True

    # Seed default demo accounts if users table is empty
    seed_default_users()


def hash_password(password: str) -> str:
    """Hashes password using PBKDF2-HMAC-SHA256 with cryptographic per-user salt."""
    salt = secrets.token_hex(16)
    iterations = 100000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations)
    return f"pbkdf2:sha256:{iterations}:{salt}:{key.hex()}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifies plain password against PBKDF2 hash or legacy SHA-256 hash."""
    if not password_hash or not plain_password:
        return False
    try:
        if password_hash.startswith("pbkdf2:sha256:"):
            parts = password_hash.split(":")
            if len(parts) == 5:
                _, _, iters_str, salt_hex, hash_hex = parts
                computed = hashlib.pbkdf2_hmac(
                    "sha256", plain_password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters_str)
                ).hex()
                return hmac.compare_digest(computed, hash_hex)
        # Backward-compatible check for legacy SHA-256 hash
        legacy_hash = hashlib.sha256(f"legal_metrology_salt_{plain_password}".encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy_hash, password_hash)
    except Exception as e:
        logger.warning(f"Password verification error: {e}")
        return False


def create_access_token(data: dict, expires_in: int = JWT_EXPIRATION_SECONDS) -> str:
    """Generates standard HS256 JWT token using Python standard library without external dependencies."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = dict(data)
    payload["exp"] = int(time.time()) + expires_in
    payload["iat"] = int(time.time())

    header_b64 = base64.urlsafe_b64encode(json.dumps(header, separators=(',', ':')).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, separators=(',', ':')).encode()).decode().rstrip("=")

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates standard HS256 JWT token."""
    if not token or not isinstance(token, str):
        return None
    try:
        parts = token.strip().split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()

        sig_padding = (4 - len(sig_b64) % 4) % 4
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + "=" * sig_padding)
        if not hmac.compare_digest(expected_sig, sig_bytes):
            return None

        payload_padding = (4 - len(payload_b64) % 4) % 4
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + "=" * payload_padding)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception as e:
        logger.debug(f"JWT decode error: {e}")
        return None


def seed_default_users():
    """Seeds default accounts for Officer, Consumer, and Manufacturer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM users")
    count = cursor.fetchone()["count"]

    if count == 0:
        now = datetime.now().isoformat()
        # Credentials configurable via environment variables
        officer_pwd = os.getenv("DEMO_OFFICER_PASSWORD", "officer123")
        consumer_pwd = os.getenv("DEMO_CONSUMER_PASSWORD", "consumer123")
        mfg_pwd = os.getenv("DEMO_MFG_PASSWORD", "mfg123")

        defaults = [
            ("Inspector Sharma", "officer@metrology.gov.in", hash_password(officer_pwd), "inspector", "INS-8021-GOI", now),
            ("Rahul Citizen", "consumer@metrology.gov.in", hash_password(consumer_pwd), "public", "PUBLIC-USER", now),
            ("ABC Packaging Ltd", "manufacturer@abcfoods.in", hash_password(mfg_pwd), "manufacturer", "LMO-2026-DEL-049", now)
        ]
        cursor.executemany("""
            INSERT INTO users (username, email, password_hash, role, badge_or_license, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, defaults)
        conn.commit()
    conn.close()


def create_user(username: str, email: str, password: str, role: str, badge_or_license: str = "") -> Dict[str, Any]:
    """Creates a new registered user in SQLite database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    email_lower = email.strip().lower()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email_lower,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("An account with this email address already exists.")

    pwd_hash = hash_password(password)
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO users (username, email, password_hash, role, badge_or_license, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (username.strip(), email_lower, pwd_hash, role, badge_or_license.strip(), now))

    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    token = create_access_token({
        "user_id": user_id,
        "username": username.strip(),
        "email": email_lower,
        "role": role
    })

    return {
        "id": user_id,
        "username": username.strip(),
        "email": email_lower,
        "role": role,
        "badge_or_license": badge_or_license.strip(),
        "access_token": token
    }


def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates user credentials against SQLite database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    email_lower = email.strip().lower()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_lower,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        return None

    if not verify_password(password, user_row["password_hash"]):
        return None

    token = create_access_token({
        "user_id": user_row["id"],
        "username": user_row["username"],
        "email": user_row["email"],
        "role": user_row["role"]
    })

    return {
        "id": user_row["id"],
        "username": user_row["username"],
        "email": user_row["email"],
        "role": user_row["role"],
        "badge_or_license": user_row["badge_or_license"],
        "access_token": token
    }


def generate_sha256_hash(data_bytes: bytes) -> str:
    """Generates SHA-256 hash string for raw binary image data."""
    return hashlib.sha256(data_bytes).hexdigest()


def generate_evidence_ledger_hash(image_sha256: str, timestamp: str, status: str, extracted_json_str: str) -> str:
    """Generates cryptographic proof combining image hash, timestamp, status, and payload."""
    payload = f"{image_sha256}|{timestamp}|{status}|{extracted_json_str}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_inspection(
    inspection_id: str,
    user_mode: str,
    product_category: str,
    overall_status: str,
    verdict_title: str,
    blur_score: float,
    brightness_score: float,
    ocr_text: str,
    extracted_data: Dict[str, Any],
    rule_results: List[Dict[str, Any]],
    image_bytes: bytes
) -> Dict[str, Any]:
    """Saves a completed inspection record to SQLite database ledger."""
    init_db()
    
    timestamp = datetime.now().isoformat()
    image_sha256 = generate_sha256_hash(image_bytes)
    extracted_json_str = json.dumps(extracted_data)
    rule_results_json_str = json.dumps(rule_results)
    
    evidence_hash = generate_evidence_ledger_hash(
        image_sha256=image_sha256,
        timestamp=timestamp,
        status=overall_status,
        extracted_json_str=extracted_json_str
    )

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO inspections (
            id, timestamp, user_mode, product_category, overall_status, verdict_title,
            blur_score, brightness_score, ocr_text, extracted_json, rule_results_json,
            image_sha256, evidence_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inspection_id, timestamp, user_mode, product_category, overall_status, verdict_title,
        blur_score, brightness_score, ocr_text, extracted_json_str, rule_results_json_str,
        image_sha256, evidence_hash
    ))

    conn.commit()
    conn.close()

    return {
        "inspection_id": inspection_id,
        "timestamp": timestamp,
        "image_sha256": image_sha256,
        "evidence_hash": evidence_hash
    }


def get_all_inspections(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieves recent inspection history with offset pagination."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM inspections WHERE id NOT LIKE 'TEST-%' ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()
    conn.close()

    inspections = []
    for row in rows:
        inspections.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "user_mode": row["user_mode"],
            "product_category": row["product_category"],
            "overall_status": row["overall_status"],
            "verdict_title": row["verdict_title"],
            "blur_score": row["blur_score"],
            "brightness_score": row["brightness_score"],
            "image_sha256": row["image_sha256"],
            "evidence_hash": row["evidence_hash"]
        })

    return inspections


def clear_all_inspections() -> int:
    """Clears all inspection history records from SQLite database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inspections")
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def get_inspection_by_id(inspection_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single detailed inspection record by ID."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    extracted_data = {}
    if row["extracted_json"]:
        try:
            extracted_data = json.loads(row["extracted_json"])
        except Exception:
            extracted_data = {}

    rule_results = []
    if row["rule_results_json"]:
        try:
            rule_results = json.loads(row["rule_results_json"])
        except Exception:
            rule_results = []

    return {
        "id": row["id"],
        "timestamp": row["timestamp"],
        "user_mode": row["user_mode"],
        "product_category": row["product_category"],
        "overall_status": row["overall_status"],
        "verdict_title": row["verdict_title"],
        "blur_score": row["blur_score"],
        "brightness_score": row["brightness_score"],
        "ocr_text": row["ocr_text"] or "",
        "extracted_data": extracted_data,
        "rule_results": rule_results,
        "image_sha256": row["image_sha256"] or "",
        "evidence_hash": row["evidence_hash"] or ""
    }
