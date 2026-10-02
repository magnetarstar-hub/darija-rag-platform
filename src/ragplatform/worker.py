"""Queue job entrypoint. Run workers with: rq worker -u $RAG_REDIS_URL ingest"""
from functools import lru_cache

from .config import Settings
from .db import make_engine, make_session_factory
from .ingestion import process_document
from .services import Services, build_services


@lru_cache(maxsize=1)
def _runtime() -> tuple[Settings, Services, object]:
    settings = Settings()
    return settings, build_services(settings), make_session_factory(make_engine(settings.database_url))


def run_job(doc_id: str) -> None:
    settings, services, session_factory = _runtime()
    process_document(doc_id, session_factory, services, settings, raise_on_error=True)  # raise => RQ retry
