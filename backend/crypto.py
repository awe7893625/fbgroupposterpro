"""
AES-256-CBC encryption for at-rest secrets (FB cookies, proxy creds, future vault items).

Why this design:
- Old version derived the key from `uuid.getnode()` (MAC address). Changing the network
  card / docking a USB-C dongle would silently change the key and brick all stored secrets.
- New version reads/creates a random 32-byte salt at `~/.fbgroupposter/vault.salt`
  (perm 0o600), then derives the AES key with PBKDF2-HMAC-SHA256.
- A future v1.2 will mix in a user passphrase to this KDF for at-rest defense; for MVP we
  rely on filesystem permissions on the salt file.
- `decrypt()` falls back to the legacy MAC-based key on failure, so existing DBs encrypted
  with v1.0 still open. New writes always use the new key.
"""

import base64
import hashlib
import logging
import os
import secrets
import uuid
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger(__name__)

VAULT_DIR = Path.home() / ".fbgroupposter"
SALT_PATH = VAULT_DIR / "vault.salt"
KDF_ITERATIONS = 200_000
KEY_LEN = 32  # AES-256


def _get_salt() -> bytes:
    """Return the 32-byte salt, creating one if missing. File mode 0o600."""
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_PATH.exists():
        salt = SALT_PATH.read_bytes()
        if len(salt) >= 32:
            return salt
        logger.warning(
            "vault.salt is corrupt, regenerating (existing secrets may not decrypt)"
        )
    salt = secrets.token_bytes(32)
    # Best-effort restrictive permission. On Windows os.chmod is a no-op for 0o600 semantics
    # but the file is created in the user's profile dir which is already user-private.
    SALT_PATH.write_bytes(salt)
    try:
        os.chmod(SALT_PATH, 0o600)
    except OSError:
        pass
    return salt


def _derive_key(salt: bytes, passphrase: bytes = b"fbgroupposter-v1") -> bytes:
    """Stable key derivation from on-disk salt. Passphrase is a constant for v1.1.

    v1.2 will let users supply their own passphrase here.
    """
    return hashlib.pbkdf2_hmac("sha256", passphrase, salt, KDF_ITERATIONS, KEY_LEN)


def _get_key() -> bytes:
    return _derive_key(_get_salt())


def _legacy_key() -> bytes:
    """Old MAC-based key for reading v1.0 secrets."""
    machine_id = str(uuid.getnode()).encode()
    return hashlib.sha256(machine_id).digest()


def encrypt(plaintext: str) -> str:
    key = _get_key()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    return base64.b64encode(cipher.iv + ct_bytes).decode()


def _try_decrypt(ciphertext: str, key: bytes) -> str:
    raw = base64.b64decode(ciphertext)
    iv = raw[:16]
    ct = raw[16:]
    cipher = AES.new(key, iv=iv, mode=AES.MODE_CBC)
    return unpad(cipher.decrypt(ct), AES.block_size).decode()


def decrypt(ciphertext: str) -> str:
    """Decrypt with the current key; on failure, try the legacy MAC-based key for backward compat."""
    try:
        return _try_decrypt(ciphertext, _get_key())
    except (ValueError, KeyError):
        # Old v1.0 ciphertext, fall back.
        return _try_decrypt(ciphertext, _legacy_key())


def reencrypt_legacy(ciphertext: str) -> str:
    """Convert a legacy-encrypted blob to the current scheme. Use this in migrations."""
    return encrypt(_try_decrypt(ciphertext, _legacy_key()))
