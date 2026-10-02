import hashlib
import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..acl import AccessScope, visible_documents
from ..audit import audit
from ..config import Settings
from ..ingestion import SUPPORTED, process_document
from ..models import Document, DocumentGroup, Group, User
from ..queue import enqueue_ingestion
from ..services import Services
from .deps import get_db, get_services, get_settings, require_roles, scope_of

router = APIRouter(prefix="/documents", tags=["documents"])
Visibility = Literal["tenant", "restricted"]


class PermissionsUpdate(BaseModel):
    visibility: Visibility
    group_ids: list[str] = []


def _group_ids(db: Session, doc_id: str) -> list[str]:
    return list(db.scalars(select(DocumentGroup.group_id).where(DocumentGroup.document_id == doc_id)))


def _out(db: Session, d: Document) -> dict:
    return {
        "id": d.id, "filename": d.filename, "status": d.status, "error": d.error, "visibility": d.visibility,
        "group_ids": _group_ids(db, d.id), "owner_id": d.owner_id, "n_chunks": d.n_chunks,
        "flagged_chunks": d.flagged_chunks, "created_at": d.created_at.isoformat(),
    }


def _validate_groups(db: Session, tenant_id: str, group_ids: list[str]) -> None:
    if group_ids and set(db.scalars(select(Group.id).where(Group.tenant_id == tenant_id, Group.id.in_(group_ids)))) != set(group_ids):
        raise HTTPException(400, "Unknown group id")


def _get_visible(db: Session, scope: AccessScope, doc_id: str) -> Document:
    doc = db.scalar(visible_documents(scope).where(Document.id == doc_id))
    if doc is None:  # 404 (not 403) so existence of other users' documents is not revealed
        raise HTTPException(404, "Document not found")
    return doc


@router.post("", status_code=202)
def upload(
    request: Request,
    file: UploadFile = File(...),
    visibility: Visibility = Form("tenant"),
    group_ids: list[str] = Form(default=[]),
    user: User = Depends(require_roles("admin", "editor")),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    services: Services = Depends(get_services),
):
    name = Path(file.filename or "").name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(SUPPORTED))}")
    if visibility == "restricted" and not group_ids:
        raise HTTPException(400, "Restricted documents need at least one group")
    _validate_groups(db, user.tenant_id, group_ids)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")
    if suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a valid PDF")

    count = db.scalar(select(func.count()).select_from(Document).where(Document.tenant_id == user.tenant_id))
    if count >= settings.max_docs_per_tenant:
        raise HTTPException(403, "Tenant document quota exceeded")

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Document).where(Document.tenant_id == user.tenant_id, Document.sha256 == digest))
    if existing:
        raise HTTPException(409, f"Identical document already uploaded (id={existing.id})")

    doc = Document(
        tenant_id=user.tenant_id, owner_id=user.id, filename=name, sha256=digest, size_bytes=len(data),
        visibility=visibility, path="",
    )
    db.add(doc)
    db.flush()
    dest = Path(settings.upload_dir) / user.tenant_id / doc.id / f"source{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    doc.path = str(dest)
    db.add_all(DocumentGroup(document_id=doc.id, group_id=g) for g in set(group_ids))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        shutil.rmtree(dest.parent, ignore_errors=True)
        raise HTTPException(409, "Identical document already uploaded") from None
    audit(db, user.tenant_id, user.id, "document.upload", doc.id, filename=name, visibility=visibility)

    enqueue_ingestion(settings, doc.id, lambda i: process_document(i, request.app.state.session_factory, services, settings))
    db.refresh(doc)
    return _out(db, doc)


@router.get("")
def list_documents(scope: AccessScope = Depends(scope_of), db: Session = Depends(get_db)):
    docs = db.scalars(visible_documents(scope).order_by(Document.created_at.desc()))
    return [_out(db, d) for d in docs]


@router.get("/{doc_id}")
def get_document(doc_id: str, scope: AccessScope = Depends(scope_of), db: Session = Depends(get_db)):
    return _out(db, _get_visible(db, scope, doc_id))


@router.patch("/{doc_id}/permissions")
def update_permissions(
    doc_id: str,
    body: PermissionsUpdate,
    user: User = Depends(require_roles("admin", "editor")),
    scope: AccessScope = Depends(scope_of),
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
):
    doc = _get_visible(db, scope, doc_id)
    if user.role != "admin" and doc.owner_id != user.id:
        raise HTTPException(403, "Only the owner or an admin can change permissions")
    if body.visibility == "restricted" and not body.group_ids:
        raise HTTPException(400, "Restricted documents need at least one group")
    _validate_groups(db, user.tenant_id, body.group_ids)
    doc.visibility = body.visibility
    db.execute(delete(DocumentGroup).where(DocumentGroup.document_id == doc.id))
    db.add_all(DocumentGroup(document_id=doc.id, group_id=g) for g in set(body.group_ids))
    db.commit()
    if doc.status == "ready":  # keep the vector payload in sync with the DB
        services.store.update_acl(doc.tenant_id, doc.id, doc.visibility, sorted(set(body.group_ids)))
    audit(db, user.tenant_id, user.id, "document.permissions", doc.id, visibility=body.visibility)
    return _out(db, doc)


@router.delete("/{doc_id}", status_code=204)
def delete_document(
    doc_id: str,
    user: User = Depends(require_roles("admin", "editor")),
    scope: AccessScope = Depends(scope_of),
    db: Session = Depends(get_db),
    services: Services = Depends(get_services),
):
    doc = _get_visible(db, scope, doc_id)
    if user.role != "admin" and doc.owner_id != user.id:
        raise HTTPException(403, "Only the owner or an admin can delete a document")
    services.store.delete_document(doc.tenant_id, doc.id)
    shutil.rmtree(Path(doc.path).parent, ignore_errors=True)
    db.execute(delete(DocumentGroup).where(DocumentGroup.document_id == doc.id))
    db.delete(doc)
    db.commit()
    audit(db, user.tenant_id, user.id, "document.delete", doc_id)
