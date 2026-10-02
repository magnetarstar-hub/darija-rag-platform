"""Document processing: parse -> chunk -> screen for prompt injection -> embed -> index with ACL payload."""
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .chunking import chunk_text, split_sentences
from .config import Settings
from .metrics import INGEST, INJECTION_FLAGGED
from .models import Document, DocumentGroup
from .safety import looks_like_injection
from .services import Services
from .telemetry import span

log = logging.getLogger(__name__)
SUPPORTED = {".pdf", ".txt", ".md"}


def read_pages(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        return [(i + 1, p.extract_text() or "") for i, p in enumerate(PdfReader(str(path)).pages)]
    if suffix in {".txt", ".md"}:
        return [(1, path.read_text(encoding="utf-8", errors="ignore"))]
    raise ValueError(f"Unsupported file type: {suffix}")


def process_document(
    doc_id: str, session_factory: sessionmaker, services: Services, settings: Settings, raise_on_error: bool = False
) -> bool:
    """Idempotent: re-running replaces the document's existing vectors. Returns True on success."""
    with session_factory() as db, span("ingest.document", doc_id=doc_id):
        doc = db.get(Document, doc_id)
        if doc is None:
            return False
        doc.status, doc.error = "processing", None
        db.commit()
        try:
            items: list[tuple[str, int]] = []
            flagged = 0
            for page, text in read_pages(Path(doc.path)):
                clean: list[str] = []
                for sentence in split_sentences(text):  # screen per sentence so legit neighbours are kept
                    if looks_like_injection(sentence):
                        flagged += 1
                        INJECTION_FLAGGED.inc()
                    else:
                        clean.append(sentence)
                for piece in chunk_text(" ".join(clean), settings.chunk_size, settings.chunk_overlap):
                    if looks_like_injection(piece):  # second pass: patterns spanning sentence boundaries
                        flagged += 1
                        INJECTION_FLAGGED.inc()
                        continue
                    items.append((piece, page))
            if not items:
                raise ValueError("No extractable text (scanned PDF? OCR is not supported yet)")

            group_ids = list(db.scalars(select(DocumentGroup.group_id).where(DocumentGroup.document_id == doc.id)))
            services.store.delete_document(doc.tenant_id, doc.id)
            services.store.upsert_chunks(
                tenant_id=doc.tenant_id, doc_id=doc.id, owner_id=doc.owner_id, visibility=doc.visibility,
                group_ids=group_ids, source=doc.filename, items=items,
                vectors=services.embedder.embed([t for t, _ in items]),
            )
            doc.status, doc.n_chunks, doc.flagged_chunks = "ready", len(items), flagged
            db.commit()
            INGEST.labels("ready").inc()
            return True
        except Exception as e:  # noqa: BLE001 - recorded on the document, optionally re-raised for queue retries
            log.exception("ingestion failed for %s", doc_id)
            db.rollback()
            doc = db.get(Document, doc_id)
            if doc is not None:
                doc.status, doc.error = "failed", str(e)[:500]
                db.commit()
            INGEST.labels("failed").inc()
            if raise_on_error:
                raise
            return False
