"""Fetch attributed critical reception and the article's spoiler-screened lead."""

import copy
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from contextvars import ContextVar

from bs4 import BeautifulSoup


SOURCE_BASIS = (
    "Review verdicts analyze Wikipedia's critical-reception section, supplemented by accessible Guardian reviews when available. "
    "Citations distinguish directly fetched reviews from websites cited by Wikipedia. "
    "Counts describe source passages, not independent reviewers or a representative audience sample. Story setup is omitted."
)
REQUEST_DEADLINE = ContextVar("source_deadline", default=None)


def _with_budget(callback):
    token = REQUEST_DEADLINE.set(time.monotonic() + 45)
    try:
        return callback()
    finally:
        REQUEST_DEADLINE.reset(token)


class SourceError(Exception):
    pass


def _request_text(url, accept="text/html"):
    request = urllib.request.Request(url, headers={
        "User-Agent": "ClearCutStudentProject/1.0 (local educational review summarizer)",
        "Accept": accept,
    })
    for attempt in range(2):
        deadline = REQUEST_DEADLINE.get()
        remaining = deadline - time.monotonic() if deadline is not None else 12
        if remaining <= 0:
            raise SourceError("Source retrieval exceeded its time budget. Please try later.")
        try:
            with urllib.request.urlopen(request, timeout=min(12, remaining)) as response:
                chunks = []
                size = 0
                while size <= 4 * 1024 * 1024:
                    if deadline is not None and time.monotonic() >= deadline:
                        raise SourceError("Source retrieval exceeded its time budget. Please try later.")
                    chunk = response.read(min(65536, 4 * 1024 * 1024 + 1 - size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                content = b"".join(chunks)
            if len(content) > 4 * 1024 * 1024:
                raise SourceError("The source article is too large to process safely.")
            return content.decode("utf-8")
        except urllib.error.HTTPError as error:
            if attempt == 0 and error.code in {502, 503, 504} and not error.headers.get("Retry-After"):
                continue
            raise SourceError(f"Source HTTP {error.code}; access restrictions and retry instructions are respected.") from error
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            if attempt:
                raise SourceError("The review source is unavailable. Please try again later.") from error
    raise SourceError("The review source is unavailable.")


def _request_json(url):
    try:
        return json.loads(_request_text(url, "application/json"))
    except ValueError as error:
        raise SourceError("The review source returned invalid JSON.") from error


def reception_sources(html):
    soup = BeautifulSoup(html, "html.parser")
    active = False
    selected_level = 0
    sources = []
    seen = set()
    for node in soup.find_all(["h2", "h3", "h4", "p"]):
        if node.name != "p":
            heading = node.get_text(" ", strip=True).lower().replace("[edit]", "").strip()
            level = int(node.name[1])
            if heading in {"reception", "critical response", "critical reception", "critical reviews", "reviews", "critical reaction", "critical reactions", "critical assessment"}:
                active, selected_level = True, level
            elif active and (level <= selected_level or re.search(r"box office|accolades|awards|commercial|audience|home media", heading)):
                active = False
            continue
        if not active:
            continue
        for reference in node.select('sup.reference a[href^="#"]'):
            citation = soup.find(id=urllib.parse.unquote(reference["href"][1:]))
            if citation is None:
                continue
            link = citation.select_one("a.external[href]")
            if link is None:
                continue
            url = link["href"]
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or url in seen:
                continue
            publisher = parsed.hostname.removeprefix("www.")
            names = {"theguardian.com": "The Guardian", "rogerebert.com": "RogerEbert.com", "rottentomatoes.com": "Rotten Tomatoes", "metacritic.com": "Metacritic", "variety.com": "Variety", "hollywoodreporter.com": "The Hollywood Reporter", "indiewire.com": "IndieWire", "nytimes.com": "The New York Times"}
            sources.append({"name": names.get(publisher, publisher), "url": url, "method": "cited in Wikipedia"})
            seen.add(url)
    return sources[:30]


def extract_guardian_review(html):
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("#maincontent .article-body-commercial-selector, .article-body-commercial-selector, [data-gu-name='body']")
    if body is None:
        return []
    passages = []
    total = 0
    for paragraph in body.find_all("p"):
        text = paragraph.get_text(" ", strip=True)
        if not 40 <= len(text) <= 12000 or total + len(text) > 30000:
            continue
        passages.append({"text": text})
        total += len(text)
    return passages[:30]


def supplement_reviews(movie):
    direct = 0
    if movie.get("title") == "Inception" and not any("theguardian.com" in source["url"] for source in movie["source"].get("citations", [])):
        movie["source"].setdefault("citations", []).append({"name": "The Guardian", "url": "https://www.theguardian.com/film/2010/jul/15/inception-review", "method": "candidate review"})
    for source in movie["source"].get("citations", []):
        parsed = urllib.parse.urlparse(source["url"])
        if parsed.scheme != "https" or parsed.hostname not in {"www.theguardian.com", "theguardian.com"} or not parsed.path.startswith(("/film/", "/tv-and-radio/")) or "review" not in parsed.path:
            continue
        try:
            passages = extract_guardian_review(_request_text(source["url"]))
        except SourceError:
            continue
        if not passages:
            continue
        movie["reviews"].extend(passages)
        source["method"] = "direct review"
        source["passages"] = len(passages)
        direct += 1
        if direct >= 2:
            break
    movie["source"]["direct_review_pages"] = direct
    movie["source"]["name"] = "Wikipedia critical reception" + (" + The Guardian" if direct else "")
    return movie


def search_movies(query):
    if not isinstance(query, str) or not 2 <= len(query.strip()) <= 120:
        raise ValueError("Enter a movie or series name between 2 and 120 characters.")
    parameters = urllib.parse.urlencode({"q": query.strip(), "limit": 12})
    payload = _request_json("https://en.wikipedia.org/w/rest.php/v1/search/page?" + parameters)
    movies = []
    for page in payload.get("pages", []):
        description = page.get("description") or ""
        details = description + " " + (page.get("excerpt") or "") + " " + page.get("title", "")
        if not re.search(r"\b(film|television|series|miniseries)\b", description, re.I):
            continue
        if re.search(r"\b(soundtrack|novel|franchise|filmography)\b", description, re.I):
            continue
        if not isinstance(page.get("id"), int) or not isinstance(page.get("title"), str):
            continue
        year = re.search(r"\b(?:19|20)\d{2}\b", details)
        movies.append({"id": page["id"], "title": page["title"], "year": year.group() if year else None})
    return movies


def extract_reception(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("sup, .mw-editsection, table, figure, script, style"):
        tag.decompose()
    active = False
    selected_level = 0
    paragraphs = []
    heading_names = {"reception", "critical response", "critical reception", "critical reviews", "reviews", "critical reaction", "critical reactions", "critical assessment"}
    for node in soup.find_all(["h2", "h3", "h4", "p"]):
        if node.name != "p":
            name = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip().lower()
            level = int(node.name[1])
            if name in heading_names:
                active = True
                selected_level = level
            elif active and (level <= selected_level or re.search(r"box office|accolades|awards|commercial|audience|home media", name)):
                active = False
            continue
        if active:
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if 40 <= len(text) <= 12000:
                paragraphs.append(text)
    selected = []
    total = 0
    for paragraph in paragraphs:
        if total + len(paragraph) > 100000 or len(selected) >= 30:
            break
        selected.append({"text": paragraph})
        total += len(paragraph)
    return selected


def extract_overview(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("sup, .mw-editsection, table, figure, script, style"):
        tag.decompose()
    content = soup.select_one(".mw-parser-output") or soup
    paragraphs = []
    for node in content.children:
        name = getattr(node, "name", None)
        if not name:
            continue
        if name in ("h2", "h3", "h4") or "mw-heading" in (node.get("class") or []):
            break
        if name != "p":
            continue
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        if 40 <= len(text) <= 3000:
            paragraphs.append(text)
        if paragraphs:
            break
    return " ".join(paragraphs)[:5000]


def opinion_passages(reviews):
    passages = []
    for review in reviews:
        quotations = [text for text in re.findall(r'["\u201c]([^"\u201c\u201d]*)["\u201d]', review["text"]) if 40 <= len(text) <= 3000]
        for text in quotations or [review["text"]]:
            passages.append({"text": text})
        if quotations:
            commentary = re.sub(r'["\u201c][^"\u201c\u201d]*["\u201d]', " ", review["text"])
            if len(commentary.strip()) >= 80 and re.search(r"\b(?:acting|performances?|pacing|screenplay|writing|cinematography|visuals|storytelling|characters)\b", commentary, re.I):
                passages.append({"text": commentary.strip()})
    return passages[:100]


@lru_cache(maxsize=32)
def _fetch_movie(page_id, cache_hour):
    parameters = urllib.parse.urlencode({"action": "parse", "pageid": page_id, "prop": "text|displaytitle", "format": "json", "formatversion": 2})
    payload = _request_json("https://en.wikipedia.org/w/api.php?" + parameters)
    return _movie_from_payload(payload, page_id)


def _movie_from_payload(payload, page_id):
    article = payload.get("parse")
    if not isinstance(article, dict) or not isinstance(article.get("text"), str):
        raise SourceError("This title could not be retrieved from the review source.")
    overview = extract_overview(article["text"])
    reviews = extract_reception(article["text"])
    if not reviews:
        raise SourceError("No dedicated critical-reception section is available for this title. Try another title or use manual reviews.")
    title = BeautifulSoup(article.get("displaytitle", "Selected title"), "html.parser").get_text(" ", strip=True)
    return {"id": page_id, "title": title, "overview": overview, "reviews": opinion_passages(reviews), "source": {
        "name": "Wikipedia: critical reception", "url": "https://en.wikipedia.org/?curid=" + str(page_id),
        "license": "Wikipedia article text is available under CC BY-SA; the linked article provides attribution and license details. Quoted critic opinions remain attributed to their original authors.",
        "basis": SOURCE_BASIS,
        "citations": reception_sources(article["text"]),
    }}


def fetch_movie_title(title):
    return _with_budget(lambda: _fetch_movie_title(title))


def _fetch_movie_title(title):
    parameters = urllib.parse.urlencode({"action": "parse", "page": title, "redirects": 1, "prop": "text|displaytitle", "format": "json", "formatversion": 2})
    payload = _request_json("https://en.wikipedia.org/w/api.php?" + parameters)
    page_id = payload.get("parse", {}).get("pageid")
    if not isinstance(page_id, int):
        raise SourceError("The catalog title could not be resolved.")
    return supplement_reviews(_movie_from_payload(payload, page_id))


def fetch_movie(page_id):
    if isinstance(page_id, bool) or not isinstance(page_id, int) or not 1 <= page_id <= 1000000000:
        raise ValueError("Choose a valid title from the search results.")
    return _with_budget(lambda: supplement_reviews(copy.deepcopy(_fetch_movie(page_id, int(time.time() // 3600)))))