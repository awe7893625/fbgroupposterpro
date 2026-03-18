import base64
import hashlib

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def _get_key() -> bytes:
    """Derive AES-256 key from machine UUID."""
    import uuid

    machine_id = str(uuid.getnode()).encode()
    return hashlib.sha256(machine_id).digest()


def encrypt(plaintext: str) -> str:
    key = _get_key()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(plaintext.encode(), AES.block_size))
    return base64.b64encode(cipher.iv + ct_bytes).decode()


def decrypt(ciphertext: str) -> str:
    key = _get_key()
    raw = base64.b64decode(ciphertext)
    iv = raw[:16]
    ct = raw[16:]
    cipher = AES.new(key, iv=iv, mode=AES.MODE_CBC)
    return unpad(cipher.decrypt(ct), AES.block_size).decode()
