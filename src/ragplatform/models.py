import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # globally unique
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))  # admin | editor | viewer
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))


class UserGroup(Base):
    __tablename__ = "user_groups"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id"), primary_key=True)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("tenant_id", "sha256"), Index("ix_documents_tenant_status", "tenant_id", "status"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(Integer)
    visibility: Mapped[str] = mapped_column(String(16), default="tenant")  # tenant | restricted
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|processing|ready|failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    flagged_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DocumentGroup(Base):
    __tablename__ = "document_groups"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("groups.id"), primary_key=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    resource: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # PII-redacted JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
