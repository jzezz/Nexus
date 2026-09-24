import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy.orm import Session

from app import store
from app.config import settings
from app.models import User

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    salt_b64, digest_b64 = password_hash.split("$", maxsplit=1)
    salt = base64.b64decode(salt_b64.encode())
    expected = base64.b64decode(digest_b64.encode())
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(candidate, expected)


def issue_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, object]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise ValueError("Invalid token.") from exc


def register_user(db: Session, email: str, password: str) -> User:
    existing = store.get_user_by_email(db, email)
    if existing:
        raise ValueError("A user with that email already exists.")
    return store.create_user(db, email=email, password_hash=hash_password(password))


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = store.get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials.")
    return user
