"""Access rules. The SAME rule is implemented three times, deliberately (defense in depth):
  1. SQL     (visible_documents)        -> what the document API lists/serves
  2. Qdrant  (vectorstore.build_filter) -> what retrieval can even see
  3. Python  (AccessScope.allows)       -> used in tests and as a post-retrieval guard
Rule: same tenant AND (admin OR visibility == 'tenant' OR owner OR shares a group with the document).
"""
from dataclasses import dataclass

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from .models import Document, DocumentGroup, User, UserGroup


@dataclass(frozen=True)
class AccessScope:
    tenant_id: str
    user_id: str
    group_ids: frozenset[str]
    is_admin: bool

    def allows(self, payload: dict) -> bool:
        if payload.get("tenant_id") != self.tenant_id:
            return False
        if self.is_admin or payload.get("visibility") == "tenant" or payload.get("owner_id") == self.user_id:
            return True
        return bool(self.group_ids & set(payload.get("group_ids", [])))


def user_scope(db: Session, user: User) -> AccessScope:
    groups = frozenset(db.scalars(select(UserGroup.group_id).where(UserGroup.user_id == user.id)))
    return AccessScope(user.tenant_id, user.id, groups, user.role == "admin")


def visible_documents(scope: AccessScope) -> Select:
    q = select(Document).where(Document.tenant_id == scope.tenant_id)
    if scope.is_admin:
        return q
    conds = [Document.visibility == "tenant", Document.owner_id == scope.user_id]
    if scope.group_ids:
        conds.append(
            Document.id.in_(select(DocumentGroup.document_id).where(DocumentGroup.group_id.in_(scope.group_ids)))
        )
    return q.where(or_(*conds))


def allowed_doc_ids(db: Session, scope: AccessScope, doc_ids: set[str]) -> set[str]:
    if not doc_ids:
        return set()
    rows = db.scalars(visible_documents(scope).where(Document.id.in_(doc_ids)))
    return {d.id for d in rows}
