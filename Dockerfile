FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models
WORKDIR /app

# CPU-only torch keeps the image far smaller than the default CUDA build
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src
COPY migrations ./migrations
RUN pip install ".[otel]"

RUN useradd -r -u 10001 app && mkdir -p /app/data /models && chown -R app /app /models
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn ragplatform.api.app:app_factory --factory --host 0.0.0.0 --port 8000"]
