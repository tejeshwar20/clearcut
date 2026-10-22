FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    CLEARCUT_REPORT_DB=/data/clearcut.sqlite3 \
    CLEARCUT_SEED_PATH=/app/data/catalog_seed.json

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
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