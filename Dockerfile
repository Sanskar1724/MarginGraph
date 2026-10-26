# MarginGraph image: production API (default), batch job, and the research demo API.
#   docker build -t margingraph .
#   docker run -p 8000:8000 -e MARGINGRAPH_ADMIN_KEY=... -v mgdata:/data margingraph     # production API, docs/API.md
#   docker run margingraph margingraph batch                                               # nightly retrain
#   docker run -p 8000:8000 -v "$PWD/artifacts:/app/artifacts:ro" margingraph \
#       uvicorn margingraph.api:app --host 0.0.0.0 --port 8000                            # research demo, POST /recommend
# CPU only. The API needs about 0.5 GB RAM per loaded store; training a 4,700-item store peaks at about 1.7 GB.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    OPENBLAS_NUM_THREADS=1 \
    DATABASE_URL=sqlite:////data/margingraph.db \
    MARGINGRAPH_ARTIFACTS=/data/artifacts \
    MARGINGRAPH_CONFIG=/app/configs/default.yaml

# libgomp1 is LightGBM's OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
COPY scripts ./scripts
RUN pip install ".[service]"

RUN useradd -m -u 1000 mg && mkdir -p /data /app/artifacts && chown mg /data
USER mg
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=2)"

# PORT is set by Render / Hugging Face Spaces / Fly; default 8000
CMD ["sh", "-c", "margingraph api --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1}"]
