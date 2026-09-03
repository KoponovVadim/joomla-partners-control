import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from django.core.exceptions import ImproperlyConfigured


def _fernet():
    raw = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    if not raw:
        raise ImproperlyConfigured("CREDENTIAL_ENCRYPTION_KEY не задан")
    try:
        key = raw.encode()
        Fernet(key)
    except (ValueError, TypeError):
        key = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def encrypt_secret(value):
    return _fernet().encrypt(value.encode()).decode() if value else ""


def decrypt_secret(value):
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ImproperlyConfigured("Неверный ключ шифрования credentials") from exc


def encrypt_password(value):
    return encrypt_secret(value)


def decrypt_password(value):
    return decrypt_secret(value)
