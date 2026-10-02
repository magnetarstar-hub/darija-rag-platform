import json

from sqlalchemy.orm import Session

from .models import AuditLog
from .safety import redact


def audit(db: Session, tenant_id: str | None, user_id: str | None, action: str, resource: str | None = None, **detail) -> None:
    safe = redact(json.dumps(detail, ensure_ascii=False, default=str)) if detail else None
    db.add(AuditLog(tenant_id=tenant_id, user_id=user_id, action=action, resource=resource, detail=safe))
    db.commit()
