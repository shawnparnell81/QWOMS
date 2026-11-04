import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from .db import session
from .models import User, AuthSession

SECRET = os.getenv("QWOMS_SECRET_KEY", "")

def hash_password(password, *, demo_initial=False):
    minimum=10 if demo_initial and os.getenv('QWOMS_DEMO_MODE','').casefold()=='true' else 12
    if len(password) < minimum:
        raise ValueError(f"Password must have at least {minimum} characters")
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

def token_for(user_id, db):
    if not SECRET or len(SECRET) < 32:
        raise RuntimeError("Set QWOMS_SECRET_KEY to a random 32+ character secret")
    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    session_id = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(AuthSession(id=hashlib.sha256(session_id.encode()).hexdigest(), user_id=user_id,
                       csrf_hash=hashlib.sha256(csrf.encode()).hexdigest(), expires_at=expires))
    token = jwt.encode({"sub": str(user_id), "jti": session_id, "exp": expires}, SECRET, algorithm="HS256")
    return token, csrf

def current_user(request: Request, qwoms_token: str | None = Cookie(None),
                 x_qwoms_csrf: str | None = Header(None), db: Session = Depends(session)):
    if not qwoms_token or not SECRET:
        raise HTTPException(401, "Please sign in")
    # SQLite cannot upgrade a stale read snapshot to a write lock. Serialize
    # authenticated mutations before reading account/session state.
    if request.method not in ('GET','HEAD','OPTIONS') and db.bind.dialect.name=='sqlite':
        from sqlalchemy import text
        db.execute(text('UPDATE users SET id=id WHERE 1=0'))
    try:
        payload = jwt.decode(qwoms_token, SECRET, algorithms=["HS256"])
        user = db.get(User, int(payload["sub"]))
        session_id = hashlib.sha256(payload["jti"].encode()).hexdigest()
        active_session = db.get(AuthSession, session_id)
    except Exception:
        raise HTTPException(401, "Session expired")
    if not user or not user.active:
        raise HTTPException(401, "Inactive account")
    if not active_session or active_session.user_id != user.id or active_session.revoked_at:
        raise HTTPException(401, "Session revoked")
    if user.must_change_password and request.url.path not in ('/api/me','/api/me/set-initial-password','/api/me/change-password','/api/auth/logout'):
        raise HTTPException(403,'Choose a new password before using QWOMS')
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        supplied = hashlib.sha256((x_qwoms_csrf or "").encode()).hexdigest()
        if not x_qwoms_csrf or not hmac.compare_digest(supplied, active_session.csrf_hash):
            raise HTTPException(403, "CSRF token required")
    request.state.session_id = session_id
    return user

def require_admin(user: User = Depends(current_user)):
    if not user.is_admin:
        raise HTTPException(403, "Administrator access required")
    return user

IMPORT_CAPABILITIES = {
    'part-master': 'import.part_master', 'drawing': 'import.drawings',
    'form-template': 'import.form_masters', 'work-instruction': 'import.work_instructions',
    'document': 'import.supporting_documents', 'other': 'import.other',
}
CAPABILITIES = tuple(IMPORT_CAPABILITIES.values()) + ('engineering.approve',)

def has_capability(user, capability):
    # Engineering decisions always require an explicit assignment, even for admins.
    return (user.is_admin and capability != 'engineering.approve') or capability in (user.capabilities or [])

def require_capability(user, capability):
    if not has_capability(user, capability):
        raise HTTPException(403, 'Explicit permission required: ' + capability)
