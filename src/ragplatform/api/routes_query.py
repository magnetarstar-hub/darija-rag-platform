import hashlib
import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..acl import AccessScope, allowed_doc_ids
from ..audit import audit
from ..config import Settings
from ..metrics import ACL_BLOCKED
from ..models import User
from ..services import Services
from .deps import current_user, get_db, get_services, get_settings, scope_of

router = APIRouter(tags=["query"])
log = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    document_ids: list[str] | None = Field(default=None, max_length=50)


@router.post("/ask")
def ask(
    body: AskRequest,
    request: Request,
    user: User = Depends(current_user),
    scope: AccessScope = Depends(scope_of),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    services: Services = Depends(get_services),
):
    request.app.state.limiter.check(f"ask:{user.id}", settings.ask_rate_limit_per_min)

    hits = services.rag.retrieve(body.question, scope, body.document_ids)

    # Defense in depth: re-authorize every retrieved chunk's document against the database before the
    # LLM ever sees it. Normally a no-op; if the vector payload ever drifts from the DB, this catches it.
    allowed = allowed_doc_ids(db, scope, {h.doc_id for h in hits})
    safe_hits = [h for h in hits if h.doc_id in allowed]
    if len(safe_hits) != len(hits):
        ACL_BLOCKED.inc(len(hits) - len(safe_hits))
        log.error("ACL guard removed %d chunks for user %s", len(hits) - len(safe_hits), user.id)

    result = services.rag.respond(body.question, safe_hits)
    audit(
        db, user.tenant_id, user.id, "ask", None,
        question_sha256=hashlib.sha256(body.question.encode()).hexdigest()[:16],  # no raw question stored
        language=result["language"], confidence=result["confidence"], abstained=result["abstained"],
        document_ids=sorted({s["document_id"] for s in result["sources"]}),
    )
    return result
