import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import Settings
from .models import User

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, dk_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        dk = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=_N, r=_R, p=_P, dklen=32)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except ValueError:
        return False


DUMMY_HASH = hash_password("dummy-password-for-timing")  # verified on unknown users to equalize timing


def create_token(settings: Settings, user: User) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": user.id,
        "tid": user.tenant_id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def decode_token(settings: Settings, token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "tid"]})
