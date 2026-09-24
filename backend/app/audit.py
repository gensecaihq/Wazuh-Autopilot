from sqlalchemy.orm import Session

from .models import AuditLog


def audit(db: Session, action: str, *, actor_id: str | None = None, actor_name: str = "system",
          actor_type: str = "system", target: str = "", detail: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, actor_name=actor_name, actor_type=actor_type, action=action,
                    target=target, detail=detail or {}, ip=ip))


def audit_user(db: Session, principal, action: str, target: str = "", detail: dict | None = None,
               ip: str | None = None) -> None:
    audit(db, action, actor_id=principal.id, actor_name=principal.name, actor_type="user",
          target=target, detail=detail, ip=ip)
