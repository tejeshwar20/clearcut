import pytest

import movie_source


def test_extracts_only_critical_response():
    html = '<h2>Plot</h2><p>Mira is the killer and the hidden sibling in the final scene.</p><h2>Reception</h2><h3>Box office</h3><p>The film grossed a large amount of money around the world.</p><h3>Critical response</h3><p>The acting is excellent but the pacing is slow, according to reviewers.<sup>[1]</sup></p><h3>Accolades</h3><p>The film received a very large number of awards and nominations.</p>'
    reviews = movie_source.extract_reception(html)
    assert len(reviews) == 1
    assert "acting" in reviews[0]["text"]
    assert "killer" not in str(reviews)
    assert "grossed" not in str(reviews)
    assert "[1]" not in str(reviews)


def test_missing_reception_returns_no_reviews():
    assert movie_source.extract_reception('<h2>Plot</h2><p>A very detailed plot description that must not be analyzed.</p>') == []


def test_source_deadline_stops_requests_before_contacting_upstream(monkeypatch):
    token = movie_source.REQUEST_DEADLINE.set(0)
    monkeypatch.setattr(movie_source.urllib.request, "urlopen", lambda *args, **kwargs: pytest.fail("expired requests must not contact sources"))
    try:
        with pytest.raises(movie_source.SourceError, match="time budget"):
            movie_source._request_text("https://en.wikipedia.org/")
    finally:
        movie_source.REQUEST_DEADLINE.reset(token)


def test_reception_heading_supports_reviews_but_excludes_box_office():
    html = '<h2>Reception</h2><p>The acting is excellent and the writing is consistently compelling.</p><h3>Box office</h3><p>The film grossed a very large amount of money around the world.</p><h3>Awards</h3><p>The film won many awards and accolades throughout the following year.</p>'
    passages = movie_source.extract_reception(html)
    assert len(passages) == 1
    assert "acting" in passages[0]["text"]


def test_extracts_article_lead_but_not_plot_section():
    html = '<p>A science-fiction film follows a skilled thief who uses dream-sharing to carry out impossible heists .</p><h2>Plot</h2><p>He discovers the secret identity of the killer.</p><h2>Reception</h2><p>The acting and visuals are excellent.</p>'
    assert movie_source.extract_overview(html) == "A science-fiction film follows a skilled thief who uses dream-sharing to carry out impossible heists."


def test_opinion_quotation_removes_critic_attribution():
    passages = movie_source.opinion_passages([{"text": 'Alice Smith of New York Weekly said "The acting is excellent but the pacing feels rather slow."'}])
    assert passages == [{"text": "The acting is excellent but the pacing feels rather slow."}]


def test_unquoted_opinion_preserved():
    passages = [{"text": "Reviewers praised the acting and the beautiful photography."}]
    assert movie_source.opinion_passages(passages) == passages


def test_short_quotations_do_not_corrupt_long_quotation_boundaries():
    passages = movie_source.opinion_passages([{"text": 'An average grade of "A". A critic called it "The acting is excellent and the pacing is consistently compelling."'}])
    assert passages == [{"text": "The acting is excellent and the pacing is consistently compelling."}]


def test_reception_citations_exclude_plot_sources():
    html = '<h2>Plot</h2><p>Plot<sup class="reference"><a href="#plot">1</a></sup></p><h2>Critical reception</h2><p>Reception<sup class="reference"><a href="#review">2</a></sup></p><li id="plot"><a class="external" href="https://example.com/plot">plot</a></li><li id="review"><cite><a class="external" href="https://www.theguardian.com/film/example-review">review</a><i>The Guardian</i></cite></li>'
    sources = movie_source.reception_sources(html)
    assert len(sources) == 1
    assert sources[0]["name"] == "The Guardian"
    assert sources[0]["method"] == "cited in Wikipedia"


def test_guardian_extraction_excludes_navigation():
    html = '<p>Navigation and unrelated headlines must not become review evidence.</p><div class="article-body-commercial-selector"><p>The performances are excellent, although the pacing occasionally drags.</p></div>'
    assert movie_source.extract_guardian_review(html) == [{"text": "The performances are excellent, although the pacing occasionally drags."}]


def test_supplement_uses_only_allowlisted_review_pages(monkeypatch):
    calls = []

    def fetch(url):
        calls.append(url)
        return '<div class="article-body-commercial-selector"><p>The acting is excellent and the cinematography is beautiful throughout.</p></div>'

    monkeypatch.setattr(movie_source, "_request_text", fetch)
    movie = {"reviews": [], "source": {"citations": [
        {"url": "http://localhost/film/review"},
        {"url": "https://www.theguardian.com/film/2020/example-review", "name": "The Guardian"},
    ]}}
    result = movie_source.supplement_reviews(movie)
    assert len(calls) == 1
    assert result["source"]["direct_review_pages"] == 1
    assert result["reviews"]


def test_search_filters_non_movies(monkeypatch):
    monkeypatch.setattr(movie_source, "_request_json", lambda url: {"pages": [
        {"id": 1, "title": "Dune (film)", "description": "Film directed by Denis Villeneuve", "excerpt": "2021 science fiction film"},
        {"id": 2, "title": "Dune", "description": "1965 novel by Frank Herbert"},
    ]})
    assert movie_source.search_movies("Dune") == [{"id": 1, "title": "Dune (film)", "year": "2021"}]


@pytest.mark.parametrize("query", [None, "", "a", "x" * 121])
def test_invalid_query(query):
    with pytest.raises(ValueError):
        movie_source.search_movies(query)


@pytest.mark.parametrize("page_id", [None, True, "123", -1, 0, 1000000001])
def test_invalid_page_id(page_id):
    with pytest.raises(ValueError):
        movie_source.fetch_movie(page_id)


def test_missing_source_data(monkeypatch):
    movie_source._fetch_movie.cache_clear()
    monkeypatch.setattr(movie_source, "_request_json", lambda url: {"error": {"code": "missingtitle"}})
    with pytest.raises(movie_source.SourceError):
        movie_source.fetch_movie(123)


def test_no_plot_fallback(monkeypatch):
    movie_source._fetch_movie.cache_clear()
    monkeypatch.setattr(movie_source, "_request_json", lambda url: {"parse": {"text": '<h2>Plot</h2><p>A detailed plot that should never be used as review evidence.</p>'}})
    with pytest.raises(movie_source.SourceError, match="critical-reception"):
        movie_source.fetch_movie(123)


def test_movie_search_api(monkeypatch):
    import app as web

    monkeypatch.setattr(web, "search_movies", lambda query: [{"id": 12, "title": "Example", "year": "2020"}])
    response = web.app.test_client().get("/api/movies/search?q=Example")
    assert response.status_code == 200
    assert response.json["movies"][0]["id"] == 12


def test_movie_analysis_api(monkeypatch, tmp_path):
    import app as web

    monkeypatch.setitem(web.app.config, "MOVIE_REPORT_DB", str(tmp_path / "movie-analysis.sqlite3"))
    monkeypatch.setattr(web, "fetch_movie", lambda page_id: {"title": "Example", "reviews": [{"text": "The acting is excellent but the pacing is terrible. The plot reveals that Mira is the killer."}], "source": {"name": "Test source", "url": "https://en.wikipedia.org/?curid=12"}})
    response = web.app.test_client().post("/api/movies/analyze", json={"id": 12})
    assert response.status_code == 200
    assert response.json["movie"]["title"] == "Example"
    assert "performances emerge as a strength" in response.json["review"]
    assert "pacing is a sticking point" in response.json["review"]
    assert "Mira" not in str(response.json)
    assert "killer" not in str(response.json)


def test_movie_network_failure(monkeypatch, tmp_path):
    import app as web

    monkeypatch.setitem(web.app.config, "MOVIE_REPORT_DB", str(tmp_path / "movie-network-failure.sqlite3"))

    def unavailable(page_id):
        raise movie_source.SourceError("Source temporarily unavailable.")

    monkeypatch.setattr(web, "fetch_movie", unavailable)
    response = web.app.test_client().post("/api/movies/analyze", json={"id": 12})
    assert response.status_code == 502
    assert "review" not in response.json


def test_editorial_review_does_not_invent_aspects():
    from pipeline import analyze_reception

    result = analyze_reception(["A remarkable and wonderful achievement."])
    assert result["overall"]["tone"] == "positive"
    assert "performances" not in result["review"]
    assert all(item["safe_mentions"] == 0 for item in result["aspects"])


def test_editorial_review_insufficient_safe_evidence():
    from pipeline import analyze_reception

    result = analyze_reception(["The plot reveals that Mira is the killer."])
    assert result["overall"]["tone"] == "insufficient"
    assert "not enough spoiler-safe" in result["review"]
    assert "Mira" not in result["review"]


def test_catalog_builds_real_reports_and_resumes(monkeypatch, tmp_path):
    import build_catalog
    from movie_store import MovieReportStore

    def fetch(title):
        return {"id": int(title), "title": "Film " + title, "reviews": [
            {"text": "The acting is excellent. The visuals are beautiful. The pacing is terrible. The plot reveals that Mira is the killer."}
        ], "source": {"name": "Test", "url": "https://example.com", "citations": []}}

    monkeypatch.setattr(build_catalog, "fetch_movie_title", fetch)
    database = tmp_path / "catalog.sqlite3"
    manifest = build_catalog.build_catalog(database, limit=3, titles=["1", "2", "3"])
    assert len(manifest["entries"]) == 3
    store = MovieReportStore(database)
    assert len(store.list_reports()) == 3
    report = store.get_report(1)
    assert "Mira" not in str(report)
    assert "killer" not in str(report)
    assert report["overview"] == ""
    assert "strong performances" in report["review"]
    monkeypatch.setattr(build_catalog, "fetch_movie_title", lambda title: pytest.fail("must resume without fetching"))
    assert len(build_catalog.build_catalog(database, limit=3, titles=["1", "2", "3"])["entries"]) == 3


def test_catalog_rejects_insufficient_evidence(monkeypatch):
    import build_catalog

    monkeypatch.setattr(build_catalog, "fetch_movie_title", lambda title: {"reviews": [{"text": "The acting is excellent."}]})
    with pytest.raises(movie_source.SourceError, match="Too little"):
        build_catalog.prepare_report("Example")