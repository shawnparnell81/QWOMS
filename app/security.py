import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from .db import session
from .models import User

SECRET = os.getenv("QWOMS_SECRET_KEY", "")

def hash_password(password):
    if len(password) < 12:
        raise ValueError("Password must have at least 12 characters")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 450_000)
    return "pbkdf2_sha256$450000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()

def verify_password(password, saved):
    try:
        name, rounds, salt, expected = saved.split("$")
        if name != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(calculated, base64.b64decode(expected))
    except Exception:
        return False

def token_for(user_id):
    if not SECRET or len(SECRET) < 32:
        raise RuntimeError("Set QWOMS_SECRET_KEY to a random 32+ character secret")
    return jwt.encode({"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm="HS256")

def current_user(qwoms_token: str | None = Cookie(None), db: Session = Depends(session)):
    if not qwoms_token or not SECRET:
        raise HTTPException(401, "Please sign in")
    try:
        payload = jwt.decode(qwoms_token, SECRET, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
    except Exception:
        raise HTTPException(401, "Session expired")
    if not user or not user.active:
        raise HTTPException(401, "Inactive account")
    return user

def require_admin(user: User = Depends(current_user)):
    if user.role != "Management":
        raise HTTPException(403, "Management access required")
    return user
