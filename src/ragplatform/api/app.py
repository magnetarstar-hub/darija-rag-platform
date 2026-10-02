import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from .. import __version__
from ..config import Settings
from ..db import Base, make_engine, make_session_factory
from ..metrics import REQUEST_SECONDS, REQUESTS
from ..ratelimit import SlidingWindowLimiter
from ..services import Services, build_services
from ..telemetry import setup_tracing
from . import routes_admin, routes_auth, routes_documents, routes_query


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or Settings()
    if settings.app_env == "prod" and settings.jwt_secret == "change-me":
        raise RuntimeError("Refusing to start in prod with the default RAG_JWT_SECRET")

    app = FastAPI(title="Darija RAG Platform", version=__version__)
    engine = make_engine(settings.database_url)
    if settings.auto_create_tables:
        Base.metadata.create_all(engine)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.services = services or build_services(settings)
    app.state.limiter = SlidingWindowLimiter()

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        REQUEST_SECONDS.labels(route).observe(time.perf_counter() - t0)
        return response

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/ready", tags=["ops"])
    def ready(response: Response):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            app.state.services.store.ping()
        except Exception as e:  # noqa: BLE001
            response.status_code = 503
            return {"status": "unavailable", "error": type(e).__name__}
        return {"status": "ready"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    for r in (routes_auth.router, routes_admin.router, routes_documents.router, routes_query.router):
        app.include_router(r)
    setup_tracing(app, settings.otlp_endpoint)
    return app


def app_factory() -> FastAPI:  # uvicorn --factory ragplatform.api.app:app_factory
    return create_app()
