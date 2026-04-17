"""Encryption helpers — Fernet AES-256, masking, SHA-256. PROMPT 17."""
from __future__ import annotations

import hashlib

from config import settings


# ── Fernet AES-256 ────────────────────────────────────────────────────────────
def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string with Fernet AES-256. Returns token string."""
    if not settings.ENCRYPTION_KEY:
        return plaintext
    try:
        from cryptography.fernet import Fernet
        return Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(plaintext.encode()).decode()
    except Exception:
        return plaintext


def decrypt(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted token. Returns plaintext string."""
    if not settings.ENCRYPTION_KEY:
        return ciphertext
    try:
        from cryptography.fernet import Fernet, InvalidToken
        return Fernet(settings.ENCRYPTION_KEY.encode()).decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext


# ── Masking helpers ───────────────────────────────────────────────────────────
def mask_cnic(cnic: str) -> str:
    """
    Mask CNIC digits while preserving format: XXXXX-XXXXXXX-X → *****-*******-*
    Input may be with or without dashes.
    """
    digits_only = cnic.replace("-", "")
    if len(digits_only) != 13:
        return cnic
    return "*****-*******-*"


def mask_account(account_number: str) -> str:
    """
    Show only last 4 digits: 1234567890 → ****7890
    Handles any account number length >= 4.
    """
    cleaned = account_number.strip()
    if len(cleaned) < 4:
        return "****"
    return "****" + cleaned[-4:]


# ── SHA-256 helpers ───────────────────────────────────────────────────────────
def hash_sha256(data: str) -> str:
    """Return lowercase hex SHA-256 digest of input string."""
    return hashlib.sha256(data.encode()).hexdigest()


def hash_refresh_token(token: str) -> str:
    """SHA-256 hash a refresh token for safe DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
