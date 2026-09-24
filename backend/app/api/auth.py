import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..audit import audit, audit_user
from ..config import VERSION, get_config
from ..db import get_db, utcnow
from ..models import ApiToken, User
from ..rbac import ROLES
from ..security import (Principal, create_access_token, get_principal, hash_api_token, hash_password, require,
                        validate_password_strength, verify_password)
from ..serializers import iso, user_out
from ..settings_store import get_section, set_section
from .common import client_ip, not_found

router = APIRouter()


class LoginIn(BaseModel):
    email: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        audit(db, "auth.failed", actor_name=body.email[:120], actor_type="user", ip=client_ip(request))
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    user.last_login_at = utcnow()
    token, ttl = create_access_token(user)
    audit(db, "auth.login", actor_id=user.id, actor_name=user.name, actor_type="user", target=user.email,
          ip=client_ip(request))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "expires_in": ttl, "user": user_out(user)}


@router.get("/auth/me")
def me(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    if principal.kind == "token":
        return {"id": principal.id, "email": "", "name": principal.name, "role": principal.role,
                "role_label": ROLES[principal.role]["label"], "permissions": principal.permissions, "active": True,
                "last_login_at": None, "created_at": None, "avatar_initials": "AT"}
    return user_out(db.get(User, principal.id))


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    user = db.get(User, principal.id)
    if not user or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    validate_password_strength(body.new_password)
    user.password_hash = hash_password(body.new_password)
    audit_user(db, principal, "auth.password_changed", user.email)
    db.commit()
    return {"ok": True}


# -- users -------------------------------------------------------------------
class UserIn(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    role: str
    password: str


class UserPatch(BaseModel):
    name: str | None = None
    role: str | None = None
    active: bool | None = None
    password: str | None = None


@router.get("/users")
def list_users(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Full records for user managers; a name directory (for assignee pickers) for anyone with cases:read."""
    perms = principal.permissions
    if "users:manage" not in perms and "cases:read" not in perms:
        raise HTTPException(403, "missing permission: users:manage")
    rows = db.query(User).order_by(User.created_at).all()
    if "users:manage" in perms:
        return {"items": [user_out(u) for u in rows], "total": len(rows)}
    items = [{k: v for k, v in user_out(u).items() if k in {"id", "name", "role", "role_label", "avatar_initials", "active"}}
             for u in rows if u.active]
    return {"items": items, "total": len(items)}


@router.post("/users")
def create_user(body: UserIn, principal: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, f"Unknown role {body.role}")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Invalid email")
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "A user with that email already exists")
    validate_password_strength(body.password)
    user = User(email=email, name=body.name, role=body.role, password_hash=hash_password(body.password))
    db.add(user)
    audit_user(db, principal, "user.created", email, {"role": body.role})
    db.commit()
    return user_out(user)


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserPatch, principal: Principal = Depends(require("users:manage")),
                db: Session = Depends(get_db)):
    user = db.get(User, user_id) or not_found("user")
    changes = {}
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(400, f"Unknown role {body.role}")
        if user.id == principal.id and body.role != "admin":
            raise HTTPException(400, "You cannot remove your own admin role")
        changes["role"] = [user.role, body.role]
        user.role = body.role
    if body.active is not None:
        if user.id == principal.id and not body.active:
            raise HTTPException(400, "You cannot deactivate yourself")
        user.active = body.active
        changes["active"] = body.active
    if body.name:
        user.name = body.name
    if body.password:
        validate_password_strength(body.password)
        user.password_hash = hash_password(body.password)
        changes["password"] = "reset"
    audit_user(db, principal, "user.updated", user.email, changes)
    db.commit()
    return user_out(user)


@router.delete("/users/{user_id}")
def delete_user(user_id: str, principal: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    user = db.get(User, user_id) or not_found("user")
    if user.id == principal.id:
        raise HTTPException(400, "You cannot delete yourself")
    audit_user(db, principal, "user.deleted", user.email)
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/roles")
def roles(_: Principal = Depends(get_principal)):
    return [{"id": k, **v} for k, v in ROLES.items()]


# -- API tokens ----------------------------------------------------------------
class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = "analyst"
    expires_days: int | None = 90


def _token_out(t: ApiToken, raw: str | None = None) -> dict:
    out = {"id": t.id, "name": t.name, "role": t.role, "prefix": t.prefix, "created_at": iso(t.created_at),
           "expires_at": iso(t.expires_at), "last_used_at": iso(t.last_used_at)}
    if raw:
        out["token"] = raw
    return out


@router.get("/api-tokens")
def list_tokens(_: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    rows = db.query(ApiToken).order_by(ApiToken.created_at.desc()).all()
    return {"items": [_token_out(t) for t in rows], "total": len(rows)}


@router.post("/api-tokens")
def create_token(body: TokenIn, principal: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(400, f"Unknown role {body.role}")
    raw = "apk_" + secrets.token_urlsafe(32)
    t = ApiToken(name=body.name, role=body.role, prefix=raw[:10], token_hash=hash_api_token(raw),
                 created_by=principal.id,
                 expires_at=utcnow() + timedelta(days=body.expires_days) if body.expires_days else None)
    db.add(t)
    audit_user(db, principal, "api_token.created", body.name, {"role": body.role})
    db.commit()
    return _token_out(t, raw)


@router.delete("/api-tokens/{token_id}")
def delete_token(token_id: str, principal: Principal = Depends(require("users:manage")), db: Session = Depends(get_db)):
    t = db.get(ApiToken, token_id) or not_found("token")
    audit_user(db, principal, "api_token.revoked", t.name)
    db.delete(t)
    db.commit()
    return {"ok": True}


# -- first-run setup -------------------------------------------------------------
@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    complete = bool(get_section(db, "setup").get("complete")) and db.query(User).count() > 0
    return {"setup_complete": complete, "demo_mode": get_config().demo_mode, "version": VERSION,
            "org_name": get_section(db, "org").get("name")}


class SetupIn(BaseModel):
    org_name: str
    admin_email: str
    admin_name: str
    admin_password: str
    wazuh: dict = {}
    model: dict = {}
    autonomy_level: str = "recommend"


@router.post("/setup/complete")
def setup_complete(body: SetupIn, request: Request, db: Session = Depends(get_db)):
    if get_section(db, "setup").get("complete") and db.query(User).count() > 0:
        raise HTTPException(409, "Setup has already been completed")
    validate_password_strength(body.admin_password)
    email = body.admin_email.strip().lower()
    db.add(User(email=email, name=body.admin_name, role="admin", password_hash=hash_password(body.admin_password)))
    set_section(db, "org", {"name": body.org_name,
                            "logo_initials": "".join(w[0] for w in body.org_name.split()[:2]).upper()})
    if body.wazuh:
        set_section(db, "wazuh", {k: v for k, v in body.wazuh.items() if k in {"mcp_url", "api_key", "verify_tls"}})
    if body.model:
        set_section(db, "model", body.model)
    if body.autonomy_level in {"observe", "recommend", "supervised", "autonomous"}:
        policy = get_section(db, "policy")
        policy["autonomy_level"] = body.autonomy_level
        set_section(db, "policy", policy)
    set_section(db, "setup", {"complete": True})
    audit(db, "setup.completed", actor_name=body.admin_name, actor_type="user", target=body.org_name,
          ip=client_ip(request))
    db.commit()
    return {"ok": True}
