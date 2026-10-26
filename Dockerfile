# MarginGraph API + batch job. ~1 GB image; runs in 1-2 GB RAM per store.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    OPENBLAS_NUM_THREADS=1 \
    DATABASE_URL=sqlite:////data/margingraph.db \
    MARGINGRAPH_ARTIFACTS=/data/artifacts \
    MARGINGRAPH_CONFIG=/app/configs/default.yaml

# libgomp: LightGBM's OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts
RUN pip install ".[service]"

RUN useradd -m -u 1000 mg && mkdir -p /data && chown mg /data
USER mg
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=2)"

# PORT is set by Render / Hugging Face Spaces / Fly; default 8000
CMD ["sh", "-c", "margingraph api --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1}"]
