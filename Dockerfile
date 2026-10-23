FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    CLEARCUT_REPORT_DB=/data/clearcut.sqlite3 \
    CLEARCUT_SEED_PATH=/app/data/catalog_seed.json \
    CLEARCUT_MODEL_CACHE=/opt/models \
    HF_HUB_DISABLE_SYMLINKS_WARNING=1

WORKDIR /app
COPY requirements.txt ./
# The semantic spoiler model (~90 MB) is downloaded at build time so startup needs no network.
RUN pip install --no-cache-dir -r requirements.txt \
    && python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/opt/models')" \
    && chmod -R a+rX /opt/models \
    && groupadd --gid 10001 clearcut \
    && useradd --uid 10001 --gid clearcut --no-create-home clearcut \
    && mkdir -p /data \
    && chown clearcut:clearcut /data
COPY --chown=clearcut:clearcut . .
USER clearcut
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/healthz',timeout=3)"
CMD ["python", "serve.py"]