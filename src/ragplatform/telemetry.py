"""Optional OpenTelemetry tracing. No-ops when the `otel` extra isn't installed or no endpoint is set."""
import logging
from contextlib import contextmanager

log = logging.getLogger(__name__)
_tracer = None


@contextmanager
def span(name: str, **attrs):
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name) as s:
        for k, v in attrs.items():
            s.set_attribute(k, v)
        yield


def setup_tracing(app, endpoint: str | None) -> None:
    global _tracer
    if not endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("RAG_OTLP_ENDPOINT is set but OpenTelemetry packages are missing (pip install '.[otel]')")
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "ragplatform-api"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    _tracer = trace.get_tracer("ragplatform")
