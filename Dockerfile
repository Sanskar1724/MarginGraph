# MarginGraph API image. CPU only, about 1 GB RAM at runtime.
#   docker build -t margingraph .
#   docker run -p 8000:8000 -v "$PWD/artifacts:/app/artifacts:ro" margingraph
# The model bundle is mounted, not baked in: build it with `margingraph run`.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    OPENBLAS_NUM_THREADS=1 MARGINGRAPH_ARTIFACTS=/app/artifacts

# libgomp1 is LightGBM's OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
RUN pip install . && useradd --create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "margingraph.api:app", "--host", "0.0.0.0", "--port", "8000"]
