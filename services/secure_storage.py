# forix/services/secure_storage.py
"""
Forix — Secure File Storage

Encrypts sensitive project files (notes, credentials, API keys, secrets)
using AES-128-CBC via the `cryptography` library (Fernet).

Key derivation:
  Master password → PBKDF2-HMAC-SHA256 (600 000 iterations) → 32-byte key → Fernet

Key storage:
  A per-installation salt is stored in E:/System/secure.salt (plain bytes).
  The derived key is kept only in memory for the session — never written to disk.
  The password hash (bcrypt) is stored in E:/System/secure.hash for re-auth.

Encrypted files:
  Each project can have an encrypted/ subfolder.
  Files are stored as <original_name>.enc
  Metadata (original name, mime, size) is prepended as a JSON header.

Usage:
    from services.secure_storage import SecureStorage
    ss = SecureStorage()
    if ss.unlock("my_master_password"):
        ss.encrypt_file(project_path, source_file)
        ss.decrypt_file(project_path, "secrets.txt.enc", dest_path)
        ss.list_encrypted(project_path)
        ss.store_note(project_path, "secrets.txt", "API_KEY=abc123")
        content = ss.read_note(project_path, "secrets.txt.enc")
"""

import base64
import hashlib
import json
import logging
import os
import struct
from pathlib import Path
from typing import Optional

import config as C

log = logging.getLogger("forix.secure")

# Paths
_SALT_FILE = C.SYSTEM_DIR / "secure.salt"
_HASH_FILE = C.SYSTEM_DIR / "secure.hash"
_ENC_DIR   = "encrypted"
_ENC_EXT   = ".enc"

# PBKDF2 parameters
_ITERATIONS = 600_000
_KEY_LEN    = 32   # 256-bit → Fernet uses 32 bytes (16 AES + 16 HMAC)


def _check_deps() -> bool:
    """Return True if the cryptography package is available."""
    try:
        import cryptography  # noqa
        return True
    except ImportError:
        log.error(
            "secure_storage requires 'cryptography'. "
            "Install it: pip install cryptography"
        )
        return False


def _load_or_create_salt() -> bytes:
    C.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    if _SALT_FILE.exists():
        return _SALT_FILE.read_bytes()
    salt = os.urandom(32)
    _SALT_FILE.write_bytes(salt)
    return salt


def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-HMAC-SHA256 → 32-byte key for Fernet."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_KEY_LEN
    )


def _make_fernet(key_bytes: bytes):
    from cryptography.fernet import Fernet
    # Fernet expects a URL-safe base64-encoded 32-byte key
    return Fernet(base64.urlsafe_b64encode(key_bytes))


class SecureStorage:
    """
    Session-based encrypted file storage.

    Call unlock() once with the master password. After that, encrypt/decrypt
    operations are available until the object is garbage-collected or
    lock() is called.
    """

    def __init__(self):
        self._key:     Optional[bytes] = None
        self._fernet   = None
        self._available = _check_deps()

    # ── Authentication ────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        return self._available

    def is_unlocked(self) -> bool:
        return self._key is not None

    def has_password(self) -> bool:
        return _HASH_FILE.exists()

    def set_password(self, password: str) -> bool:
        """
        Set a new master password.
        Stores a bcrypt hash for re-authentication.
        Returns True on success.
        """
        if not self._available:
            return False
        if not password:
            return False
        try:
            try:
                import bcrypt
                hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
            except ImportError:
                # Fallback: PBKDF2 hash stored as hex (less secure but no bcrypt dep)
                salt = _load_or_create_salt()
                hashed = hashlib.pbkdf2_hmac(
                    "sha256", password.encode(), salt, 200_000).hex().encode()

            C.SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
            _HASH_FILE.write_bytes(hashed)
            return self.unlock(password)
        except Exception as exc:
            log.error("set_password: %s", exc)
            return False

    def unlock(self, password: str) -> bool:
        """
        Verify password and derive the session key.
        Returns True if password is correct or no password is set yet.
        """
        if not self._available:
            return False
        if not password:
            return False
        try:
            # Verify password if hash exists
            if _HASH_FILE.exists():
                stored = _HASH_FILE.read_bytes()
                try:
                    import bcrypt
                    if not bcrypt.checkpw(password.encode(), stored):
                        return False
                except ImportError:
                    salt = _load_or_create_salt()
                    candidate = hashlib.pbkdf2_hmac(
                        "sha256", password.encode(), salt, 200_000).hex().encode()
                    if candidate != stored:
                        return False

            # Derive Fernet key
            salt = _load_or_create_salt()
            self._key    = _derive_key(password, salt)
            self._fernet = _make_fernet(self._key)
            log.info("SecureStorage: unlocked")
            return True
        except Exception as exc:
            log.error("unlock: %s", exc)
            return False

    def lock(self):
        """Wipe the session key from memory."""
        self._key    = None
        self._fernet = None

    # ── File operations ───────────────────────────────────────────────────────

    def _enc_dir(self, project_path: Path) -> Path:
        d = project_path / _ENC_DIR
        d.mkdir(exist_ok=True)
        return d

    def encrypt_file(self, project_path: Path, source: Path) -> Optional[Path]:
        """
        Encrypt source file and store it in project_path/encrypted/.
        Returns the .enc file path, or None on failure.
        """
        if not self._fernet:
            log.warning("encrypt_file: not unlocked")
            return None
        try:
            raw = source.read_bytes()
            meta = json.dumps({
                "name":  source.name,
                "size":  len(raw),
            }).encode("utf-8")
            # Header: 4-byte little-endian meta length + meta + ciphertext
            token    = self._fernet.encrypt(raw)
            meta_len = struct.pack("<I", len(meta))
            payload  = meta_len + meta + token

            dest = self._enc_dir(project_path) / (source.name + _ENC_EXT)
            dest.write_bytes(payload)
            log.info("Encrypted: %s → %s", source.name, dest.name)
            return dest
        except Exception as exc:
            log.error("encrypt_file: %s", exc)
            return None

    def decrypt_file(
        self, project_path: Path, enc_name: str, dest: Optional[Path] = None
    ) -> Optional[bytes]:
        """
        Decrypt a .enc file.
        If dest is given, writes decrypted bytes there.
        Always returns decrypted bytes (or None on failure).
        """
        if not self._fernet:
            log.warning("decrypt_file: not unlocked")
            return None
        try:
            enc_path = self._enc_dir(project_path) / enc_name
            payload  = enc_path.read_bytes()
            meta_len = struct.unpack("<I", payload[:4])[0]
            token    = payload[4 + meta_len:]
            raw      = self._fernet.decrypt(token)
            if dest:
                dest.write_bytes(raw)
            return raw
        except Exception as exc:
            log.error("decrypt_file %s: %s", enc_name, exc)
            return None

    def store_note(self, project_path: Path, name: str, content: str) -> Optional[Path]:
        """
        Encrypt and store a text note.
        `name` should be a filename like "api_keys.txt".
        """
        if not self._fernet:
            return None
        try:
            raw      = content.encode("utf-8")
            token    = self._fernet.encrypt(raw)
            meta     = json.dumps({"name": name, "size": len(raw)}).encode()
            payload  = struct.pack("<I", len(meta)) + meta + token
            dest     = self._enc_dir(project_path) / (name + _ENC_EXT)
            dest.write_bytes(payload)
            return dest
        except Exception as exc:
            log.error("store_note: %s", exc)
            return None

    def read_note(self, project_path: Path, enc_name: str) -> Optional[str]:
        """Decrypt a stored text note and return its string content."""
        raw = self.decrypt_file(project_path, enc_name)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")

    def list_encrypted(self, project_path: Path) -> list[dict]:
        """
        List all encrypted files in a project.
        Returns [{"enc_name": str, "orig_name": str, "size": int}, ...]
        """
        enc_dir = project_path / _ENC_DIR
        if not enc_dir.exists():
            return []
        results = []
        for f in sorted(enc_dir.glob(f"*{_ENC_EXT}")):
            try:
                payload  = f.read_bytes()
                meta_len = struct.unpack("<I", payload[:4])[0]
                meta     = json.loads(payload[4:4+meta_len].decode("utf-8"))
                results.append({
                    "enc_name":  f.name,
                    "orig_name": meta.get("name", f.stem),
                    "size":      meta.get("size", 0),
                    "enc_path":  str(f),
                })
            except Exception:
                results.append({
                    "enc_name":  f.name,
                    "orig_name": f.stem,
                    "size":      0,
                    "enc_path":  str(f),
                })
        return results

    def delete_encrypted(self, project_path: Path, enc_name: str) -> bool:
        """Permanently delete an encrypted file. Cannot be undone."""
        try:
            enc_path = self._enc_dir(project_path) / enc_name
            enc_path.unlink(missing_ok=True)
            return True
        except Exception as exc:
            log.error("delete_encrypted: %s", exc)
            return False


# ── Singleton ─────────────────────────────────────────────────────────────────

_ss_instance: Optional[SecureStorage] = None

def get_secure_storage() -> SecureStorage:
    global _ss_instance
    if _ss_instance is None:
        _ss_instance = SecureStorage()
    return _ss_instance