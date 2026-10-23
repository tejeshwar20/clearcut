# ClearCut: Pasted Reviews Without Plot Reveals

A BTech-level English NLP project for movie and TV reviews. Paste a review and
generate one source-grounded, spoiler-free review. The page
has no title search, saved library, import, refresh, or export controls.
The pasted-review writer uses spaCy's English dependency parser to retain
evaluative wording while discarding surrounding plot clauses. It does not call
a paid model or require an API key. The parser and its English model are installed
by the requirements; after installation, pasted-review analysis works offline.

For deployment, run `python serve.py`, not Flask's development server. See
[production setup and Docker instructions](docs/DEPLOYMENT.md).

## Run

Python 3.11+ recommended. From this folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe serve.py
```

Open http://127.0.0.1:8080, paste an English review, and select
**Generate spoiler-free review**. Separate multiple reviews with blank lines.
The production server uses Waitress, without the Flask debugger.
To use another port: `$env:PORT = '5001'` before starting.
Dependencies, including `en_core_web_sm`, need internet to install. No network
inference is used for pasted text. The bundled sample is fictional.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe evaluate.py
```

## Legacy Catalog

The following catalog commands and source APIs are retained for compatibility and
earlier project experiments. They are not part of the paste-only website and do
not supply, save, or influence its pasted-review output.

The populated database is `data/clearcut.sqlite3`. It contains generated reviews
and citations, not original third-party review text. Rebuild or resume:

```powershell
python build_catalog.py --limit 100 --workers 1
```

Use `--refresh` to refetch the candidate titles or `--database PATH` to build a
separate database. Collection checkpoints live in `data/catalog_manifest.json`.
Candidates cover Hollywood, Indian cinema, animation, and international films.
Each admitted film needs at least two supported non-ending aspects and three
safe opinion sentences. Titles with insufficient evidence or inaccessible
sources are skipped, never filled with invented reviews. Source availability
means a future rebuild may produce a different selection or fewer than 100.

Collection audit: 100 films; 1,630 source passages; 3,022 screened sentences;
1,132 sentences flagged and withheld; 35 directly fetched Guardian review pages
across 32 films; 1,733 linked citations. Citation counts are not unique critics
or directly fetched pages. Source excerpts are processed transiently, without
persisting or redistributing raw reviews. See
[the test report](docs/REAL_WORLD_TEST_RESULTS.md) for verification and limitations.

## Legacy Source APIs

### Movie or Series Name (API Only)

The app searches Wikipedia pages whose description identifies a film or TV work.
Choose a matching title/year; ambiguous titles may have several results. Only a
critical-reception/reviews section or review paragraphs directly under Reception
are considered. Plot, cast, production,
and box-office sections are never used as fallback review content. The fetch has
a 20-second per-attempt timeout, 4 MB response limit, bounded transient-error
retry, and 1-hour in-memory article cache.
Network access can fail, Wikipedia may rate-limit requests, and some titles have
no reception section. In those cases, the app shows an error and does not invent
a review. A different title can be tried or manual review input used.

This is **not a live Rotten Tomatoes/IMDb audience-review feed**. Wikipedia
articles compile selected critical-reception passages. When quoted opinions are
available, the system analyzes those quotation spans; otherwise it analyzes
reception paragraphs. These passages are not independent reviewers, so counts,
rating weights, and MMR operate on source passages, not a representative audience
sample. A movie-specific overall tone comes from the sentiment distribution of
safe reception sentences. Accessible Guardian reviews linked by reception
citations are fetched directly, with an explicitly curated Guardian review link
also used for Inception. Other sites are cited through Wikipedia, not claimed
as directly fetched. Source metadata distinguishes both acquisition methods.
Access-denied and rate-limited pages are not bypassed. Original critic text is
not reproduced in the output.

## Pasted Input

Paste reviews separated by blank lines. The page sends only the pasted reviews
to `/api/analyze`; it does not search for or fetch a movie. Paste mode has equal
review weights. For programmatic clients, legacy CSV/JSON import supports reviewer
ratings and supplied confidence weights.
Ratings use **0 to 10**; confidence uses **0 to 1**. Convert 5-star ratings first.
Missing metadata defaults to equal weighting; confidence 0 excludes an opinion.
CSV columns: `text`, optional `rating`, optional `confidence`.
See [the example CSV](data/sample_reviews.csv).

```json
[
  {"text": "The acting is excellent but the pacing is terrible.", "rating": 8, "confidence": 0.9},
  {"text": "The ending is satisfying."}
]
```

API clients may optionally supply character names or named events to improve filtering.
Do not read a plot synopsis just to supply names. Names are matched as whole spans.
Limits: 300 reviews; 12,000 characters per review; 120,000 per collection;
2,000 sentences; 4 MB uploads. These bound the quadratic similarity calculation.

## Output

The result screen shows **one continuous spoiler-free review** and no score.
It does not show aspect bars, aspect scores, sentiment tables, sentence counts,
separate aspect headings, or repetitive spoiler warnings. No search, catalog,
source disclosure, or import controls are shown.

Both pasted reviews and saved titles have a reader-facing `reader_review` paragraph.
The manual API's `review` is the same paragraph. A supplied `title` is optional;
an explicitly italicized Markdown title can also be recognized. Qualified performer
names may be retained when the input explicitly ties them to an evaluated performance.
This includes possessive credits, "performance by/from" credits, and qualified
"played ... by" credits. Supported relationship warmth, emotional tone, rural
setting, genre, and social commentary can also inform the paragraph without copying
the surrounding plot events or revealing when a genre shift occurs. Genre and tone
alone are not treated as praise.

The pasted-review writer acts as a spoiler-free review editor. Sentences without
spoilers are kept exactly as written, and a review with no spoilers is returned
unchanged. Spoiler sentences (twists, reveals, deaths, betrayals, outcomes, the
final act or climax) are rephrased rather than deleted: the plot detail is replaced
with a vague reference to the moment ("the ending", "the final act", "the big
surprise") while the reviewer's own reaction or adjectives are kept, e.g.
"I couldn't believe the detective was the killer all along." becomes
"I couldn't believe the big surprise." Spoiler-only clauses inside an otherwise
safe sentence are cut, and paragraph breaks are preserved. Nothing new is added.
This local editor is rule-based; an unusual twist phrased without recognizable
cues can still slip through.

Optional model editor: set `CLEARCUT_WRITER=openai` and `OPENAI_API_KEY` (and
optionally `CLEARCUT_MODEL`). The review is then sent with the spoiler-free editor
instructions in `source_writer.EDITOR_PROMPT`. The model's rewrite is used only if it
passes the output check and reuses no names or events found only in spoiler
sentences; otherwise the local result is returned. This makes paid API calls.
The older catalog writer is separate and still uses controlled templates.

All reader-facing output passes a final spoiler/copy check, including saved reports
and optional model output. The browser accepts only the versioned, checked
`reader_review` field; it never falls back to a legacy `review` or provider section.
Known disclosure cues and copied runs of ten source words outside internally vetted
opinion phrases block the candidate,
and replace it with a safe unavailable message. Unsafe legacy
review fields are removed as well. This is defense in depth, not a guarantee that
every possible implicit spoiler can be recognized. Stylistic and genre observations
can survive discarded plot passages without retaining the events themselves.

The app does not rate reviews. Earlier versions showed an estimated `overall_score`;
it was removed, and the API now strips `overall_score` and `score_basis` from every
response, including old cached reports.

For legacy API clients, cached reports gain the reader-facing paragraph without a live
source request. Legacy `review_sections`, aspect distributions, and selection metadata
remain in report JSON for compatibility and inspection, but are not rendered as the
review interface. Original critical-review passages and the article lead are not
returned. Spoiler screening is heuristic and cannot guarantee detection of every
implicit or unfamiliar reveal. `overview` remains empty in title mode.

Pasted review text is held in memory for processing, not saved or added to the catalog.
For legacy API clients, movie
reception text is fetched on demand and may remain temporarily in the existing
in-memory fetch cache, but is not persisted to disk. ClearCut saves the
resulting critical take, aspect scores, source
citation, and title in
`data/clearcut.sqlite3`; the saved-report list holds the 100 most recently
analyzed movies and remains available offline. Saved reports do not contain
original critical-review passages; the selected movie title and source citations
are retained. Set `CLEARCUT_REPORT_DB` to choose another local
database path. The database is ignored by Git.
Anyone inspecting their own browser/network can still see input or fetched
source material. This is a local teaching demo, not a hardened public hosting
service.

## Course Connection

Based on the [CSL772 Autumn 2014 course](https://www.cse.iitd.ac.in/~mausam/courses/csl772/autumn2014/):

| Course topic | Project implementation |
| --- | --- |
| Tokenization / regular languages | NLTK Punkt sentence splitting and regex word boundaries |
| Information extraction | spaCy dependency parsing for pasted opinions; aspect taxonomy for legacy reports |
| Sentiment mining | VADER plus a small film lexicon and negation rules in local aspect contexts |
| Named entities | User-provided name dictionary, density features, weak capitalization fallback |
| Document similarity | scikit-learn TF-IDF and cosine similarity |
| Document summarization | Source-grounded opinion composition; legacy MMR evidence selection |
| Evaluation | Precision, recall, F1, accuracy, and regression tests |

VADER, MMR, and the specific heuristics are implementation choices, not claims
that they were explicitly taught in that course. Dictionary matching is **not**
a trained NER model. See [the project explanation](docs/PROJECT_EXPLANATION.md)
for formulas, thresholds, architecture, limitations, and viva questions.

## Evaluation Honesty

Passing software tests does not prove perfect language understanding or spoiler
detection. `evaluate.py` prints metrics on a tiny, synthetic example set that
includes known difficult cases. It is not a held-out research benchmark.
For your submission, independently annotate real, permitted English review
sentences and run `python evaluate.py --data your_labels.json`. Use the bundled
JSON schema: `text`, boolean `spoiler`, optional `entities`; for safe sentences,
also `aspect` and `sentiment` (positive/negative/neutral). One target aspect per
evaluation example. Keep threshold tuning and test data separate. Report spoiler
recall, safe-sentence coverage, aspect extraction performance, and sentiment F1.
The current evaluator measures spoiler classification and target-aspect sentiment,
not a full extraction benchmark or contextual coreference accuracy.

**No finite test suite can guarantee all inputs work correctly.** Sarcasm,
implicit aspects, unfamiliar plot facts, complex scope, and non-English text
remain limitations. Conservative filtering sacrifices coverage. The strongest
output protection is architectural: plot clauses are not deliberately copied into
the review, and retained opinion phrases pass an additional output check. These
heuristics cannot certify arbitrary text as completely spoiler-free.