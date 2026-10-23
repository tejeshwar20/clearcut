"""Production entry point: python serve.py (Waitress, Windows or Linux)."""

import json
import logging
import os
from ipaddress import ip_address
from pathlib import Path

from waitress import serve

from app import app, movie_report_store
from movie_store import MAX_SAVED_MOVIES


def bootstrap_catalog(store, seed_path):
    if store.list_reports() or not Path(seed_path).exists():
        return 0
    payload = json.loads(Path(seed_path).read_text(encoding="utf-8"))
    records = payload.get("reports")
    if payload.get("schema_version") != 1 or not isinstance(records, list) or len(records) > MAX_SAVED_MOVIES:
        raise ValueError("Invalid catalog seed.")
    seen = set()
    for record in records:
        page_id = record.get("id")
        report = record.get("report")
        if isinstance(page_id, bool) or not isinstance(page_id, int) or page_id <= 0 or page_id in seen or not isinstance(record.get("title"), str) or not isinstance(report, dict):
            raise ValueError("Invalid catalog record.")
        if report.get("overview") or "reviews" in report or not isinstance(report.get("review"), str) or not isinstance(report.get("aspects"), list):
            raise ValueError("Catalog seeds must contain generated reports, not original reviews.")
        seen.add(page_id)
    for record in records:
        store.save_report(record["id"], record["title"], record["report"])
    return len(records)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if os.environ.get("CLEARCUT_WRITER", "local") not in {"local", "openai"}:
        raise ValueError("CLEARCUT_WRITER must be local or openai.")
    if os.environ.get("CLEARCUT_WRITER") == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("Configure OPENAI_API_KEY through your deployment's secret settings.")
    proxy = proxy_settings()
    seed = os.environ.get("CLEARCUT_SEED_PATH", str(Path(__file__).parent / "data" / "catalog_seed.json"))
    restored = bootstrap_catalog(movie_report_store(), seed)
    logging.getLogger(__name__).info("Catalog startup: restored %d reports", restored)
    import semantic

    logging.getLogger(__name__).info("Semantic spoiler check: %s", "on" if semantic.available() else "off (rules only)")
    port = int(os.environ.get("PORT", "8080"))
    threads = int(os.environ.get("CLEARCUT_THREADS", "8"))
    if not 1 <= port <= 65535 or not 2 <= threads <= 32:
        raise ValueError("Choose a valid PORT and 2-32 CLEARCUT_THREADS.")
    serve(app, host=os.environ.get("HOST", "0.0.0.0"), port=port, threads=threads, connection_limit=100, channel_timeout=90, max_request_body_size=4 * 1024 * 1024, expose_tracebacks=False, **proxy)


def proxy_settings():
    if os.environ.get("CLEARCUT_TRUST_PROXY") != "1":
        return {}
    address = os.environ.get("CLEARCUT_PROXY_IP", "")
    ip_address(address)
    return {"trusted_proxy": address, "trusted_proxy_count": 1, "trusted_proxy_headers": {"x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"}}


if __name__ == "__main__":
    main()