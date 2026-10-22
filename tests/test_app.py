import io
import json

import pytest

from app import app


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    original_database = app.config["MOVIE_REPORT_DB"]
    app.config["MOVIE_REPORT_DB"] = str(tmp_path / "clearcut.sqlite3")
    try:
        yield app.test_client()
    finally:
        app.config["MOVIE_REPORT_DB"] = original_database


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"ClearCut" in response.data
    assert "no-store" in response.headers["Cache-Control"]


def test_api(client):
    result = client.post("/api/analyze", json={"reviews": ["The acting is excellent. The plot reveals the killer."]})
    assert result.status_code == 200
    assert "acting is excellent" in result.json["review"].lower()
    assert result.json["review"] == result.json["reader_review"]
    assert 5 < result.json["overall_score"] <= 10
    assert b"killer" not in result.data


def test_pasted_review_endpoint_preserves_qualified_opinion_and_title(client):
    text = "Driven by Ada Stone's legendary performance, the story reveals the killer. The show has meticulous pacing and devastating tension."
    result = client.post("/api/analyze", json={"title": "A Different Series", "reviews": [text]})
    assert result.status_code == 200
    assert result.json["reader_title"] == "A Different Series"
    assert "Ada Stone" in result.json["review"]
    assert "legendary" in result.json["review"]
    assert "career-defining" not in result.json["review"]
    assert "killer" not in result.json["review"]
    assert 5 < result.json["overall_score"] <= 10


def test_reader_endpoint_rejects_invalid_entities_before_extracting_names(client):
    text = "Driven by Ada Stone's legendary performance, the series is compelling."
    result = client.post("/api/analyze", json={"reviews": [text], "entities": [1]})
    assert result.status_code == 400


def test_home_has_one_overall_score_without_aspect_breakdown(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="overall-score"' in html
    assert 'id="aspects"' not in html
    assert 'class="legend"' not in html
    assert 'id="stats"' not in html


def test_home_is_paste_only(client):
    from bs4 import BeautifulSoup

    page = BeautifulSoup(client.get("/").data, "html.parser")
    assert page.select_one("form#review-form textarea#reviews") is not None
    assert len(page.select("textarea")) == 1
    assert len(page.select("button")) == 1
    assert page.select_one("#analyze") is not None
    assert not page.select('input, select, details')
    for removed in ("movie-search", "saved-movies", "import-file", "refresh", "export", "sources"):
        assert page.find(id=removed) is None


@pytest.mark.parametrize("payload", [{}, [], {"reviews": []}, {"reviews": ["acting"], "gate_ending": "false"}, {"reviews": ["acting"], "entities": "Mira"}])
def test_bad_payload(client, payload):
    assert client.post("/api/analyze", json=payload).status_code == 400


def test_malformed_json(client):
    assert client.post("/api/analyze", data="{", content_type="application/json").status_code == 400


def test_wrong_content_type(client):
    assert client.post("/api/analyze", data="reviews").status_code == 415


@pytest.mark.parametrize("name,content", [("reviews.csv", b'text,rating,confidence\n"The acting is excellent.",8,0.9\n'), ("reviews.json", b'["The acting is excellent."]')])
def test_import(client, name, content):
    response = client.post("/api/import", data={"file": (io.BytesIO(content), name)})
    assert response.status_code == 200
    assert len(response.json["reviews"]) == 1


@pytest.mark.parametrize("name,content", [("reviews.csv", b"review\nhello"), ("reviews.json", b"{"), ("reviews.csv", b"text,rating\nacting,nope"), ("reviews.txt", b"acting"), ("reviews.json", b"\xff")])
def test_bad_import(client, name, content):
    assert client.post("/api/import", data={"file": (io.BytesIO(content), name)}).status_code == 400


def test_sample_analysis(client):
    demo = client.get("/api/demo").json
    result = client.post("/api/analyze", json=demo)
    assert result.status_code == 200
    assert result.json["stats"]["duplicates_removed"] > 0
    assert "Mira" not in json.dumps(result.json)


def test_movie_search_contract(client, monkeypatch):
    import app

    monkeypatch.setattr(app, "search_movies", lambda query: [{"id": 123, "title": query, "year": "2010"}])
    result = client.get("/api/movies/search?q=Inception")
    assert result.status_code == 200
    assert result.json["movies"] == [{"id": 123, "title": "Inception", "year": "2010"}]


def test_movie_analysis_includes_citation_and_aspect_scores(client, monkeypatch):
    import app

    monkeypatch.setattr(app, "fetch_movie", lambda page_id: {"title": "Example (2020 film)", "overview": "A science-fiction film follows a skilled thief who uses dream-sharing to carry out impossible heists.", "reviews": [{"text": "The performances are excellent, the visuals are breathtaking, and the plot is inventive. The ending is mysterious."}], "source": {"name": "Critical reception", "url": "https://en.wikipedia.org/?curid=123", "basis": "Critical reception passages.", "license": "Wikipedia text; quotations remain attributed."}})
    result = client.post("/api/movies/analyze", json={"id": 123})
    assert result.status_code == 200
    assert result.json["movie"]["title"] == "Example (2020 film)"
    assert result.json["source"]["url"].endswith("123")
    assert len(result.json["aspects"]) == 7
    assert "performances emerge as a strength" in result.json["review"]
    assert "visually" in result.json["review"].lower()
    assert "ending is deliberately left out" in result.json["review"]
    assert result.json["evidence_unit"] == "source passages"
    assert result.json["saved"] is True
    assert result.json["overview"] == ""


def test_movie_report_is_saved_and_reloaded_without_source_text(client, monkeypatch):
    import app as web

    original_text = "The plot reveals that Mira is the killer."
    monkeypatch.setattr(web, "fetch_movie", lambda page_id: {
        "title": "Example",
        "reviews": [{"text": "The acting is excellent. " + original_text}],
        "source": {"name": "Critical reception", "url": "https://en.wikipedia.org/?curid=321", "basis": "Reception.", "license": "Wikipedia text."},
    })
    first = client.post("/api/movies/analyze", json={"id": 321})
    assert first.status_code == 200
    assert first.json["saved"] is True
    assert "Mira" not in first.get_data(as_text=True)
    assert original_text not in first.get_data(as_text=True)

    monkeypatch.setattr(web, "fetch_movie", lambda page_id: pytest.fail("saved report should be returned"))
    saved = client.get("/api/movies/saved/321")
    assert saved.status_code == 200
    assert saved.json == first.json
    assert client.get("/api/movies/saved").json["movies"][0]["title"] == "Example"


def test_old_saved_reports_get_new_critics_take_sections(client):
    from movie_store import MovieReportStore
    from pipeline import analyze_reception

    report = analyze_reception(["The acting is excellent but the pacing is terrible."])
    report.pop("review_sections")
    report["review"] = "Legacy unstructured summary"
    MovieReportStore(app.config["MOVIE_REPORT_DB"]).save_report(432, "Example", report)
    response = client.get("/api/movies/saved/432")
    assert response.status_code == 200
    headings = [item["heading"] for item in response.json["review_sections"]]
    assert "Acting" in headings
    assert "Story and Writing" not in headings
    assert "Pacing" in headings
    assert "Verdict" in headings
    assert "Legacy unstructured summary" not in response.json["review"]


def test_saved_report_cannot_return_poisoned_review_fields(client):
    from movie_store import MovieReportStore
    from pipeline import analyze_reception

    report = analyze_reception(["The acting is excellent."])
    spoiler = "The finale reveals that Mira is the killer. She murders Jon in the final showdown."
    report["review"] = spoiler
    report["reader_review"] = spoiler
    report["review_sections"] = [{"heading": "Verdict", "text": spoiler}]
    MovieReportStore(app.config["MOVIE_REPORT_DB"]).save_report(902, "Example", report)
    response = client.get("/api/movies/saved/902")
    assert response.status_code == 200
    assert "Mira" not in response.get_data(as_text=True)
    assert "murders" not in response.get_data(as_text=True)
    assert response.json["reader_output"]["checked"] is True


@pytest.mark.parametrize("structured", [False, True])
def test_unchecked_cache_is_never_promoted_from_raw_text(client, structured):
    from movie_store import MovieReportStore
    from pipeline import analyze_reception

    original = "A courier quietly forwards a location to an old acquaintance before the council meeting begins."
    report = analyze_reception(["The acting is excellent."]) if structured else {}
    report.pop("reader_output", None)
    report["review"] = original
    report["reader_review"] = original
    report["review_sections"] = [{"heading": "Verdict", "text": original}]
    report["overall_score"] = 9.9
    MovieReportStore(app.config["MOVIE_REPORT_DB"]).save_report(903, "Example", report)
    response = client.get("/api/movies/saved/903")
    assert response.status_code == 200
    assert original not in response.get_data(as_text=True)
    assert response.json["reader_output"]["checked"] is True
    if not structured:
        assert response.json["overall_score"] is None
        assert response.json["reader_output"]["blocked"] is True


def test_movie_story_overview_drops_spoiler_sentences(client, monkeypatch):
    import app as web

    monkeypatch.setattr(web, "fetch_movie", lambda page_id: {
        "title": "Example",
        "overview": "A science-fiction film follows a skilled thief who uses dream-sharing to carry out heists. He discovers the secret identity of the killer.",
        "reviews": [{"text": "The acting is excellent."}],
        "source": {"name": "Critical reception", "url": "https://en.wikipedia.org/?curid=654", "basis": "Reception.", "license": "Wikipedia text."},
    })
    result = client.post("/api/movies/analyze", json={"id": 654})
    assert result.status_code == 200
    assert result.json["overview"] == ""
    assert "killer" not in result.get_data(as_text=True)


def test_saved_search_and_analysis_work_without_external_sources(client, monkeypatch):
    import app as web

    monkeypatch.setattr(web, "fetch_movie", lambda page_id: {"title": "Example Film", "reviews": [{"text": "The acting is excellent."}], "source": {"name": "Test", "url": "https://example.com"}})
    first = client.post("/api/movies/analyze", json={"id": 123})
    monkeypatch.setattr(web, "fetch_movie", lambda page_id: pytest.fail("must not fetch cached movie"))
    monkeypatch.setattr(web, "search_movies", lambda query: pytest.fail("must search local database first"))
    results = client.get("/api/movies/search?q=example").json
    assert results["origin"] == "saved library"
    assert results["movies"][0]["saved"] is True
    assert client.post("/api/movies/analyze", json={"id": 123}).json == first.json


@pytest.mark.parametrize("page_id", [True, None, 0, "123", -1])
def test_movie_analysis_validates_id_before_cache_lookup(client, page_id):
    assert client.post("/api/movies/analyze", json={"id": page_id}).status_code == 400


def test_oversized_request(client):
    assert client.post("/api/analyze", data=b"x" * (4 * 1024 * 1024 + 1), content_type="application/json").status_code == 413


def test_production_health_and_readiness(client, monkeypatch):
    monkeypatch.setenv("CLEARCUT_WRITER", "local")
    assert client.get("/healthz").json == {"status": "ok"}
    assert client.get("/readyz").json["status"] == "ready"
    monkeypatch.setenv("CLEARCUT_WRITER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert client.get("/readyz").status_code == 503


def test_production_requests_are_rate_limited(client, monkeypatch):
    import app as web

    monkeypatch.setitem(app.config, "TESTING", False)
    web.limiter.reset()
    for index in range(10):
        assert client.post("/api/movies/analyze", json=[], environ_base={"REMOTE_ADDR": "203.0.113.8"}).status_code == 400
    response = client.post("/api/movies/analyze", json=[], environ_base={"REMOTE_ADDR": "203.0.113.8"})
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    web.limiter.reset()


def test_deployment_seed_restores_reports_without_overwriting_existing(tmp_path):
    from build_catalog import export_catalog
    from movie_store import MovieReportStore
    from pipeline import analyze_reception
    from serve import bootstrap_catalog

    source = MovieReportStore(tmp_path / "source.sqlite3")
    report = analyze_reception(["The acting is nuanced and the writing is sharp."])
    source.save_report(123, "Example", report)
    seed = tmp_path / "seed.json"
    export_catalog(source.database_path, seed)
    target = MovieReportStore(tmp_path / "target.sqlite3")
    assert bootstrap_catalog(target, seed) == 1
    assert target.get_report(123)["review"] == report["review"]
    assert bootstrap_catalog(target, seed) == 0


def test_proxy_headers_require_an_explicit_trusted_address(monkeypatch):
    from serve import proxy_settings

    monkeypatch.setenv("CLEARCUT_TRUST_PROXY", "0")
    assert proxy_settings() == {}
    monkeypatch.setenv("CLEARCUT_TRUST_PROXY", "1")
    monkeypatch.delenv("CLEARCUT_PROXY_IP", raising=False)
    with pytest.raises(ValueError):
        proxy_settings()
    monkeypatch.setenv("CLEARCUT_PROXY_IP", "127.0.0.1")
    assert proxy_settings()["trusted_proxy"] == "127.0.0.1"