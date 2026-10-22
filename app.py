"""Local Flask interface. Source reviews stay in memory; safe reports are saved locally."""

import csv
import io
import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from pipeline import MAX_REVIEWS, analyze_reader_review, analyze_reception, validate_reviews
from movie_source import SourceError, fetch_movie, search_movies
from movie_store import MAX_SAVED_MOVIES, MovieReportStore
from editorial_writer import write_editorial

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get("CLEARCUT_RATE_STORAGE", "memory://")
app.config["RATELIMIT_HEADERS_ENABLED"] = True
app.config["MOVIE_REPORT_DB"] = os.environ.get(
    "CLEARCUT_REPORT_DB",
    os.path.join(app.root_path, "data", "clearcut.sqlite3"),
)
limiter = Limiter(get_remote_address, app=app, default_limits=["240 per minute"])


@limiter.request_filter
def bypass_test_limits():
    return app.testing


def movie_report_store():
    return MovieReportStore(app.config["MOVIE_REPORT_DB"])

DEMO = [
    {"text": "The acting is excellent but the pacing is terrible. The cinematography is beautiful.", "rating": 8},
    {"text": "The performances are wonderful. The dialogue is clever and the plot is engaging.", "rating": 9},
    {"text": "The pacing is great. The characters are interesting. The ending is satisfying.", "rating": 7},
    {"text": "The writing is weak. The camera work is gorgeous. The plot reveals that Mira is the killer.", "rating": 5},
    {"text": "The acting is excellent but the pacing is terrible. The cinematography is beautiful.", "rating": 8},
    {"text": "The characters are dull. The script is excellent. The finale is disappointing.", "rating": 6},
]


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
@limiter.exempt
def health():
    return jsonify(status="ok")


@app.get("/readyz")
@limiter.exempt
def readiness():
    writer = os.environ.get("CLEARCUT_WRITER", "local")
    if writer not in {"local", "openai"} or (writer == "openai" and not os.environ.get("OPENAI_API_KEY")):
        return jsonify(status="not_ready", reason="Editorial provider configuration is incomplete."), 503
    try:
        count = len(movie_report_store().list_reports())
    except (sqlite3.Error, OSError):
        return jsonify(status="not_ready", reason="Catalog database is unavailable."), 503
    return jsonify(status="ready", saved_movies=count, writer=writer)


@app.get("/api/demo")
def demo():
    return jsonify({"reviews": DEMO})


@app.post("/api/analyze")
@limiter.limit("20 per minute")
def analyze_reviews():
    if not request.is_json:
        return jsonify(error="Send a JSON request."), 415
    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify(error="The request must be a JSON object."), 400
    try:
        return jsonify(analyze_reader_review(payload.get("reviews"), payload.get("entities"), payload.get("gate_ending", True), payload.get("title", "")))
    except ValueError as error:
        return jsonify(error=str(error)), 400


@app.get("/api/movies/search")
@limiter.limit("60 per minute")
def movie_search():
    try:
        query = request.args.get("q", "").strip()
        if not 2 <= len(query) <= 120:
            raise ValueError("Enter a movie or series name between 2 and 120 characters.")
        local = [dict(movie, saved=True) for movie in movie_report_store().list_reports() if query.casefold() in movie["title"].casefold()]
        if local:
            return jsonify(movies=local, origin="saved library")
        return jsonify(movies=search_movies(query), origin="Wikipedia")
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except SourceError as error:
        return jsonify(error=str(error)), 502


@app.get("/api/movies/saved")
def saved_movie_reports():
    return jsonify(
        movies=movie_report_store().list_reports(),
        limit=MAX_SAVED_MOVIES,
    )


@app.get("/api/movies/saved/<int:page_id>")
def saved_movie_report(page_id):
    report = movie_report_store().get_report(page_id)
    if report is None:
        return jsonify(error="No saved report exists for this title."), 404
    return jsonify(report)


@app.post("/api/movies/analyze")
@limiter.limit("10 per minute")
def movie_analysis():
    if not request.is_json:
        return jsonify(error="Send a JSON request."), 415
    payload = request.get_json()
    if not isinstance(payload, dict):
        return jsonify(error="The request must be a JSON object."), 400
    try:
        page_id = payload.get("id")
        if isinstance(page_id, bool) or not isinstance(page_id, int) or not 1 <= page_id <= 1000000000:
            raise ValueError("Choose a valid title from the search results.")
        refresh = payload.get("refresh", False)
        if not isinstance(refresh, bool):
            raise ValueError("refresh must be true or false.")
        saved = movie_report_store().get_report(page_id)
        if saved is not None and not refresh:
            return jsonify(saved)
        movie = fetch_movie(page_id)
        result = analyze_reception(movie["reviews"], title=movie["title"])
        result["movie"] = {"id": page_id, "title": movie["title"]}
        result["source"] = movie["source"]
        result["evidence_unit"] = "source passages"
        result["saved"] = True
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        write_editorial(result)
        movie_report_store().save_report(page_id, movie["title"], result)
        return jsonify(result)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except SourceError as error:
        return jsonify(error=str(error)), 502


@app.post("/api/import")
@limiter.limit("20 per minute")
def import_reviews():
    file = request.files.get("file")
    if file is None:
        return jsonify(error="Choose a CSV or JSON file."), 400
    try:
        contents = file.read().decode("utf-8-sig")
        if file.filename and file.filename.lower().endswith(".csv"):
            rows = csv.DictReader(io.StringIO(contents))
            if not rows.fieldnames or "text" not in rows.fieldnames:
                raise ValueError("CSV must have a text column; rating and confidence are optional.")
            reviews = []
            for row in rows:
                if len(reviews) >= MAX_REVIEWS:
                    raise ValueError(f"Import at most {MAX_REVIEWS} reviews.")
                entry = {"text": row["text"]}
                for key in ("rating", "confidence"):
                    if row.get(key, "").strip():
                        entry[key] = float(row[key])
                reviews.append(entry)
        elif file.filename and file.filename.lower().endswith(".json"):
            reviews = json.loads(contents)
            if isinstance(reviews, dict):
                reviews = reviews.get("reviews")
        else:
            raise ValueError("Only CSV and JSON files are supported.")
        return jsonify(reviews=validate_reviews(reviews))
    except (ValueError, UnicodeError, csv.Error, AttributeError) as error:
        return jsonify(error=f"Import failed: {error}"), 400


@app.errorhandler(BadRequest)
def bad_request(error):
    return jsonify(error="Invalid request or malformed JSON."), 400


@app.errorhandler(RequestEntityTooLarge)
def too_large(error):
    return jsonify(error="Request too large. Maximum upload size is 4 MB."), 413


@app.errorhandler(429)
def rate_limited(error):
    return jsonify(error="Too many requests. Please retry after the indicated delay."), 429


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)