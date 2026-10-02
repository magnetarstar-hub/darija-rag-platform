from collections.abc import Callable

from .config import Settings


def enqueue_ingestion(settings: Settings, doc_id: str, run_inline: Callable[[str], object]) -> None:
    """inline: process synchronously (dev/tests). rq: push to Redis; `rq worker` processes with retries."""
    if settings.queue_mode == "inline":
        run_inline(doc_id)
        return
    from redis import Redis
    from rq import Queue, Retry

    Queue(settings.queue_name, connection=Redis.from_url(settings.redis_url)).enqueue(
        "ragplatform.worker.run_job", doc_id, retry=Retry(max=3, interval=[10, 30, 60]), job_timeout=1800
    )
