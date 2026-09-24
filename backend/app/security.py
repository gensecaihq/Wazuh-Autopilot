import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_config
from .db import get_db, utcnow
from .models import ApiToken, User
from .rbac import has_permission, permissions_for

_PBKDF2_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(400, "Password must be at least 10 characters")


def create_access_token(user: User) -> tuple[str, int]:
    cfg = get_config()
    ttl = cfg.token_ttl_minutes * 60
    payload = {"sub": user.id, "role": user.role, "exp": utcnow() + timedelta(seconds=ttl), "iat": utcnow()}
    return jwt.encode(payload, cfg.secret_key, algorithm="HS256"), ttl


def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class Principal:
    id: str
    name: str
    email: str
    role: str
    kind: str  # "user" | "token"

    @property
    def permissions(self) -> list[str]:
        return permissions_for(self.role)


def _principal_from_token(token: str, db: Session) -> Principal:
    if token.startswith("apk_"):
        row = db.query(ApiToken).filter_by(token_hash=hash_api_token(token)).first()
        if not row or (row.expires_at and row.expires_at < utcnow()):
            raise HTTPException(401, "Invalid or expired API token")
        row.last_used_at = utcnow()
        db.commit()
        return Principal(row.id, row.name, "", row.role, "token")
    try:
        payload = jwt.decode(token, get_config().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired session")
    user = db.get(User, payload.get("sub"))
    if not user or not user.active:
        raise HTTPException(401, "User not found or disabled")
    return Principal(user.id, user.name, user.email, user.role, "user")


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.query_params.get("token", "")
    if not token:
        raise HTTPException(401, "Authentication required")
    return _principal_from_token(token, db)


def require(permission: str):
    def dep(principal: Principal = Depends(get_principal)) -> Principal:
        if not has_permission(principal.role, permission):
            raise HTTPException(403, f"missing permission: {permission}")
        return principal

    return dep


def require_or_setup(permission: str):
    """Permission check that is skipped while first-run setup is incomplete (setup wizard)."""

    def dep(request: Request, db: Session = Depends(get_db)) -> Principal | None:
        from .settings_store import get_section
        if not get_section(db, "setup").get("complete") or db.query(User).count() == 0:
            return None
        principal = get_principal(request, db)
        if not has_permission(principal.role, permission):
            raise HTTPException(403, f"missing permission: {permission}")
        return principal

    return dep
