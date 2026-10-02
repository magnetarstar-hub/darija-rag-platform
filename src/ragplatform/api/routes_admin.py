from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import audit
from ..models import AuditLog, Group, User, UserGroup
from ..security import hash_password
from .deps import EMAIL_RE, get_db, require_roles

router = APIRouter(tags=["admin"])
Role = Literal["admin", "editor", "viewer"]


class UserCreate(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    role: Role = "viewer"
    group_ids: list[str] = []


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    group_ids: list[str] | None = None


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def _validate_groups(db: Session, tenant_id: str, group_ids: list[str]) -> None:
    if not group_ids:
        return
    found = set(db.scalars(select(Group.id).where(Group.tenant_id == tenant_id, Group.id.in_(group_ids))))
    if found != set(group_ids):
        raise HTTPException(400, "Unknown group id")


def _user_out(db: Session, u: User) -> dict:
    gids = list(db.scalars(select(UserGroup.group_id).where(UserGroup.user_id == u.id)))
    return {"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active, "group_ids": gids}


@router.post("/users", status_code=201)
def create_user(body: UserCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    _validate_groups(db, admin.tenant_id, body.group_ids)
    user = User(tenant_id=admin.tenant_id, email=body.email.lower(), password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email already registered") from None
    db.add_all(UserGroup(user_id=user.id, group_id=g) for g in set(body.group_ids))
    db.commit()
    audit(db, admin.tenant_id, admin.id, "user.create", user.id, role=body.role)
    return _user_out(db, user)


@router.get("/users")
def list_users(admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return [_user_out(db, u) for u in db.scalars(select(User).where(User.tenant_id == admin.tenant_id))]


@router.patch("/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None or user.tenant_id != admin.tenant_id:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(400, "You cannot demote or deactivate yourself")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.group_ids is not None:
        _validate_groups(db, admin.tenant_id, body.group_ids)
        db.execute(delete(UserGroup).where(UserGroup.user_id == user.id))
        db.add_all(UserGroup(user_id=user.id, group_id=g) for g in set(body.group_ids))
    db.commit()
    audit(db, admin.tenant_id, admin.id, "user.update", user.id, **body.model_dump(exclude_none=True))
    return _user_out(db, user)


@router.post("/groups", status_code=201)
def create_group(body: GroupCreate, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    group = Group(tenant_id=admin.tenant_id, name=body.name)
    db.add(group)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Group already exists") from None
    audit(db, admin.tenant_id, admin.id, "group.create", group.id)
    return {"id": group.id, "name": group.name}


@router.get("/groups")
def list_groups(user: User = Depends(require_roles("admin", "editor")), db: Session = Depends(get_db)):
    return [{"id": g.id, "name": g.name} for g in db.scalars(select(Group).where(Group.tenant_id == user.tenant_id))]


@router.get("/audit")
def audit_log(limit: int = 100, admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    q = select(AuditLog).where(AuditLog.tenant_id == admin.tenant_id).order_by(AuditLog.id.desc()).limit(min(limit, 500))
    return [
        {"id": a.id, "user_id": a.user_id, "action": a.action, "resource": a.resource, "detail": a.detail,
         "created_at": a.created_at.isoformat()}
        for a in db.scalars(q)
    ]
