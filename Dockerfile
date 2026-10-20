# Fosha as ONE web service: the FastAPI app serves both the API (/api/v1/...) and
# the built React app (/ and /dashboard) on a single port.
#
#   docker build -t fosha .
#   docker run -p 8000:8000 -e GROQ_API_KEY=... fosha        → http://localhost:8000
#
# Default (SEARCH=keyword): light image, keyword search over the curated places;
# the real model still understands requests and writes replies.
# Full vector search: docker build --build-arg SEARCH=vector -t fosha .
# (installs torch/sentence-transformers/chromadb and builds the index at build time;
# a much larger image).

# ---------- 1) build the web app ----------
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- 2) the Python service ----------
FROM python:3.13-slim
ARG SEARCH=keyword
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    REHLA_SEARCH=${SEARCH}
WORKDIR /app

COPY requirements-deploy.txt pyproject.toml uv.lock ./
RUN pip install --no-cache-dir -r requirements-deploy.txt \
 && if [ "$SEARCH" = "vector" ]; then \
      pip install --no-cache-dir uv \
      && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/requirements-full.txt \
      && pip install --no-cache-dir -r /tmp/requirements-full.txt; \
    fi

COPY agents ./agents
COPY api ./api
COPY rag ./rag
COPY data/raw_attractions.json ./data/raw_attractions.json
COPY --from=web /web/dist ./frontend/dist

RUN if [ "$SEARCH" = "vector" ]; then python -m rag.ingest; fi \
 && useradd --create-home fosha && chown -R fosha /app
USER fosha

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", 8000)}/api/v1/health', timeout=4)"
# Hosting platforms pass the port in $PORT; keys come from environment variables, never the image.
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT}"]
