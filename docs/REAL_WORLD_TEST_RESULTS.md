# Real-Language Test Results

## Production Writer Update: 2026-10-20

- Full regression suite: **135 passed**.
- Catalog rebuilt from live reception sources, including contextual commentary
	previously discarded around quotations; 100 reports remain available offline.
- The rebuild retained 45 controlled specific observations across 36 titles.
	Remaining titles have more general aspect evidence; the system does not invent
	details to make them appear richer.
- Repetitive caveats, empty sections, and unverified parental-guidance filler
	were removed from reader-facing prose. Evidence notes remain available separately.
- Neutral description no longer counts as criticism or creates a misleading
	"divided response" when the only subjective evidence is positive.
- Waitress production startup, health/readiness, rate-limit headers and 429s,
	explicit trusted-proxy settings, and safe catalog seeding are covered by tests.
- The complete seed was imported into a fresh temporary SQLite database:
	100 reports restored; a second import preserved existing data.
- Browser checks against Waitress at `http://127.0.0.1:8080` verified the cached
	Breaking Bad report, collapsed evidence notes, healthy/ready responses, and
	successful source refresh. No horizontal overflow at 320/390/768/1440 pixels.
- Optional model-assisted writing has bounded structured evidence, known evidence
	references, spoiler/unverified-detail validation, and timeout/failure fallback
	tests. **No live model call was made and model quality is not certified.**
- Docker CLI exists, but the engine is stopped; the image build/run is unverified.
	Redis-backed distributed limits and cloud deployment are also unverified.

See [deployment instructions](DEPLOYMENT.md) for the exact runtime, storage,
secrets, and operational requirements. Test success and successful retrieval
are not independent evidence of real-world semantic accuracy or perfect spoilers.

## Sectioned Critics' Take Update: 2026-10-20

- Full regression suite: **120 passed**.
- Critics' takes now have dedicated acting, story/writing, pacing, visuals,
	characters, parental-guidance status, and verdict sections.
- All 100 saved reports were upgraded to structured sections without raw review
	text or plot setup. Breaking Bad was fetched through the real analysis endpoint.
- A live Breaking Bad passage exposed a long-negation error in "never made a
	seriously damaging storytelling misstep" and sentiment bias from the title
	word "Bad". Focused regressions now cover both corrections.
- Unverified ratings are not invented. Single-passage findings are flagged as
	preliminary; unsupported aspects remain explicitly unavailable.
- The source-coverage counts below describe the original 100-film collection
	audit, before Breaking Bad replaced one entry under the 100-report limit.

## 100-Film Catalog Verification: 2026-10-20

The following is the current implementation check. Sections below it record
earlier development observations and are not current accuracy claims.

| Check | Actual result |
| --- | --- |
| Complete regression suite | 114 passed using `c:/python313/python.exe -m pytest -q` |
| Real movie reports in SQLite | 100 |
| Original source passages analyzed | 1,630; transient processing, not stored |
| Sentences screened | 3,022 |
| Sentences flagged as spoiler-risk | 1,132 withheld; correctness not independently annotated |
| Directly fetched Guardian review pages | 35 across 32 films |
| Linked reception citations | 1,733; includes websites cited by Wikipedia, not necessarily fetched |
| Minimum supported non-ending aspects per film | 2 |
| Minimum retained overall opinion sentences per film | 5 |
| Reports with a story overview | 0 |
| Inconsistent aspect evidence counts | 0 |
| Browser library count | 100 / 100 |
| Browser flows | Library filtering, cached report selection, offline-first title search, citation expansion |
| Viewport widths checked | 320, 390, 768, 1440 pixels; no horizontal overflow |

Rebuild/resume with `python build_catalog.py --limit 100 --workers 1`.
The collector checkpoints successful titles and failures in
`data/catalog_manifest.json`. Collection initially encountered transient errors;
sequential resume completed the catalog. Insufficient evidence, access-denied,
and rate-limited sources were skipped rather than bypassed or fabricated.
Raw review prose is absent from persisted evidence fields. Stored reports
contain generated prose, categorical aspect results, numeric references,
titles, and source links. Story setup is deliberately omitted for extra safety.

The bundled **26-example synthetic** evaluation returned 92.3% spoiler-label
accuracy, 87.5% spoiler recall, and 88.9% safe-aspect sentiment accuracy.
This small development set is not an independently held-out benchmark and
does not establish real-world accuracy. The catalog audit establishes that
retrieval, processing, storage, and rendering work, not that every semantic
judgment is correct. Sarcasm, implicit aspects, unfamiliar revelations, and
small or unrepresentative source selections remain limitations.

For example, Whiplash's generated report highlights performances and characters
as strengths without describing any story event. RRR's report preserves mixed
performance/visual/pacing opinions and a character-related reservation instead
of converting overall positive reception into praise for every aspect.
Inception's report leaves unsupported aspects unrated and records divided
storytelling and visual opinions. These illustrate grounded output, not
independent validation of the critics' consensus.

## Historical Checks

Tested on 2026-10-16 against the existing pipeline, without tuning it to these
examples. No pipeline code was changed during this check.

## Published Review Snippets

Source: [Cornell movie-review data / Rotten Tomatoes](https://huggingface.co/datasets/cornell-movie-review-data/rotten_tomatoes).
Fetched using the Hugging Face datasets-server JSON rows endpoint, configuration
`default`, split `test`, offsets `0` and `533`, length `20` each.
These are actual dataset snippets, not reviews invented for the application.
This deterministic convenience sample is not a representative benchmark.

Each snippet was analyzed independently. They were NOT combined into a fictional
consensus about one movie. Dataset titles and reviewer metadata were unavailable.
The dataset has overall positive/negative labels, **not** aspect or spoiler labels.
Consequently no aspect accuracy or spoiler accuracy can be inferred from it.

| Observation | Result |
| --- | --- |
| Published snippets processed | 40: 20 labeled positive, 20 labeled negative |
| Crashes | 0 |
| At least one safe explicit aspect extracted | 8 / 40 (20% observed coverage, not accuracy) |
| No safe aspect evidence | 32 / 40 |
| Snippets containing a sentence flagged risky | 2 / 40; correctness not annotated |
| Nonempty generated review field | 40 / 40; many are insufficient-evidence messages |

All retained aspect outputs in this sample:

| Dataset row | Overall dataset label | Extracted aspect and verdict |
| --- | --- | --- |
| 3 | Positive | Plot: Mostly Positive |
| 9 | Positive | Characters: Mostly Positive |
| 12 | Positive | Characters: Neutral |
| 533 | Negative | Plot: Neutral |
| 543 | Negative | Characters: Mostly Negative |
| 546 | Negative | Plot: Mostly Positive |
| 548 | Negative | Plot: Neutral |
| 551 | Negative | Pacing: Neutral |

Do not treat disagreement with an overall label as proof an aspect label is
wrong: a negative review can praise a specific aspect. Conversely, agreement
does not establish correct aspect attachment. Human aspect annotations are needed.
The small explicit taxonomy leaves many real snippets without a usable aspect.

## Authored Realistic Stress Cases

The following are original examples written for testing, **not published reviews**.
Expected labels are provisional human judgments for this check, not independent
annotations or a held-out benchmark. Context can change interpretation, especially
for slow pacing. Endings use the default privacy gate; no character names were
supplied. Each example was run separately through `analyze`.

| Input | Expected | Actual | Match |
| --- | --- | --- | --- |
| The acting is excellent but the pacing is terrible. | Acting positive; pacing negative | As expected | Yes |
| The acting is not good. | Acting negative | Negative | Yes |
| The acting is not bad. | Acting positive | Positive | Yes |
| Wonderful acting, if you enjoy watching paint dry. | Acting negative (sarcasm) | Positive | No |
| The acting isn't just good, it is outstanding. | Acting positive | Negative | No |
| The pacing is slow but never boring. | Pacing positive (provisional interpretation) | Negative | No |
| The plot has a clever twist. | Plot positive, generic opinion safe | Spoiler-Gated | No |
| Every scene looks stunning. | Cinematography positive | Not Enough Evidence | No |
| The plot reveals that Mira is the killer. | Plot gated | Spoiler-Gated | Yes |
| The plot confirms the two strangers are siblings. | Plot gated | Neutral, not gated | No |
| No spoilers: the acting is excellent. | Acting positive | Spoiler-Gated | No |
| The acting and writing are not good. | Both negative | Both negative | Yes |
| The acting is wooden and the plot is predictable. | Both negative | Both negative | Yes |
| The ending is satisfying. | Ending gated by policy | Spoiler-Gated | Yes |

**Result: 7 / 14 match these provisional expected labels.** All examples processed
without exceptions. The generated review paragraph did not copy any full input
sentence and did not contain the supplied fictional name. The response uses fixed
templates, so a missed spoiler can affect a verdict but is not quoted in the review.

## What This Means

The application is a working explainable baseline, not a reliable general-purpose
review understanding system. The 67 passing software regression tests do not
measure real-world NLP accuracy. They coexist with the semantic failures above.

Main limitations observed:

- Explicit phrase matching misses visual descriptions and other implicit aspects.
- Lexical sentiment misses sarcasm and complex negation scope.
- Aspect-free clauses after contrast markers lose their connection to an aspect.
- Generic spoiler cues overfilter safe phrases such as "no spoilers" or "clever twist".
- Unfamiliar relationship revelations can evade the spoiler rules entirely.

Recommended next steps are independently labeled development/test review sets,
broader aspect phrase coverage, and targeted improvements to negation and clause
attachment. Keep these examples as development cases once rules are changed;
do not tune on them and then claim their scores as held-out performance.

## Movie-Name Retrieval Check

After adding the movie-name workflow, live lookups were manually exercised against
Wikipedia's page search and API. **Inception (2010)**, **Dune (2021 film)**, and
**Breaking Bad** were found; all three returned critical-reception passages. Search
results let the user choose the title/year rather than silently picking the first
result. One initial request failed transiently and a retry succeeded; live network
availability is therefore a real dependency. The API's no-reception-section and
network-error cases return an error instead of making up a review.

The actual Inception article yielded 22 analyzable opinion passages and Dune
yielded 6. Inception had mixed overall safe reception and a mixed cinematography
verdict; the remaining aspects were unavailable or spoiler-gated. Dune yielded a
positive visual/cinematography verdict, with other aspects mostly unavailable or
gated. These counts are **Wikipedia source passages, not independent critics or a
representative audience sample**. They are a qualitative integration check, not
measured accuracy. A small selection of quotes and inferred summary paragraphs is
not equivalent to a full set of reader reviews.

In title mode, aspect evidence is limited to quoted reviewer opinions when the
article provides them; otherwise it is limited to the dedicated critical reception
section. We do not use plot, production, or box-office sections as a fallback.
Output is an original template-based summary and does not reproduce the review
quotes. The source link and source-basis note appear in the report.