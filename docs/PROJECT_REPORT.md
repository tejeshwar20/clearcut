# ClearCut: A Rule-Based Natural Language Processing System for Spoiler-Free Review Rewriting

**Project Report**

| | |
| --- | --- |
| **Project title** | ClearCut: spoiler-free rewriting of movie and television reviews |
| **Course / subject** | Natural Language Processing |
| **Student** | Tejeshwar *(add roll number, programme and institution)* |
| **Submitted to** | *(add professor's name and department)* |
| **Date** | 23 October 2026 |
| **Source code** | https://github.com/tejeshwar20/clearcut (branch `main`) |
| **Technology** | Python 3.13, Flask, spaCy 3.8, VADER, Waitress, Docker |

---

## Abstract

Online movie and television reviews frequently reveal plot twists, character deaths and endings. A reader who wants only the reviewer's opinion has no easy way to avoid these spoilers. This project presents **ClearCut**, a web application that takes a pasted English review and returns a spoiler-free version of the *same* review. The design goal is minimal intervention: only sentences that disclose plot are rewritten, and every other sentence is returned exactly as the reviewer wrote it.

The system is built as a rule-based natural language processing pipeline. It uses spaCy's dependency parser to decide how much of a sentence to remove, curated pattern sets to detect plot disclosures, and a rewriting stage that keeps the reviewer's own reaction while replacing the revealed fact with a neutral phrase. A final safety check re-scans the output and withholds it if any disclosure remains. The system runs entirely on the local machine, needs no external service or API key, and responds in about 20 ms for a short review and about 130 ms for a 300-word review.

On a developer-written test set of 25 spoiler sentences, 20 harmless sentences and 48 mixed reviews, the final system removed all 25 spoilers, left all 20 harmless sentences unchanged, and preserved all 48 harmless sentences that surrounded a spoiler. A suite of 212 automated tests passes. These figures come from developer-written cases, not an independent benchmark. The report states this limitation openly and describes how real-world accuracy should be measured.

**Keywords:** spoiler detection, text rewriting, dependency parsing, rule-based NLP, spaCy, text safety, web application.

---

## Table of contents

1. Introduction
2. Problem statement and objectives
3. Requirements
4. Background and related work
5. System design
6. Implementation
7. Testing and evaluation
8. Results
9. Discussion: what went wrong and what was learned
10. Limitations
11. Ethical, privacy and safety considerations
12. Deployment
13. Conclusion and future work
14. References
15. Appendix A: repository structure
16. Appendix B: worked examples
17. Appendix C: how to run and test

---

## 1. Introduction

A spoiler is information about a story that lessens a reader's enjoyment of discovering it for themselves. Reviews are one of the most common places to meet spoilers: a reviewer explaining why a film works often has to refer to what happens in it.

Existing approaches to this problem mostly *hide* or *warn*. Many sites let users tag a review with a spoiler label, and browser extensions can blur text that matches a list of keywords. Neither gives the reader a usable review. A hidden paragraph also hides the reviewer's opinion, which is the part the reader wanted.

This project takes a different approach: **rewrite the spoiler and keep the opinion.** If a reviewer writes

> *Great visuals. It was all a simulation the whole time, which blew my mind.*

the reader should get

> *Great visuals. The big surprise blew my mind.*

The opinion and the reviewer's reaction survive; the revealed fact does not.

### 1.1 Scope

- Input: a single English-language movie or television review, pasted as text.
- Output: the same review in which spoiler sentences are rewritten and all other sentences are unchanged.
- Processing runs locally. No review text is sent to any outside service in the default configuration.

---

## 2. Problem statement and objectives

### 2.1 Problem statement

Given a free-text review, produce a version that (a) discloses no plot information, (b) preserves every sentence that does not disclose plot, exactly as written, and (c) keeps the reviewer's reaction wherever this can be done safely.

### 2.2 Objectives

| # | Objective | Measure of success |
| --- | --- | --- |
| O1 | Detect sentences that reveal plot events, identities, deaths, twists or endings | No tested spoiler term appears in the output |
| O2 | Leave harmless sentences untouched | Harmless sentences come back word for word |
| O3 | Rewrite instead of delete, keeping the reviewer's reaction | Reaction wording appears in the rewritten sentence |
| O4 | Avoid repetitive filler | The same replacement line never appears twice in one review |
| O5 | Never show unsafe output | A final check blocks output that still contains disclosures |
| O6 | Work without paid services or network inference | Pipeline runs offline after installation |
| O7 | Respond quickly | Under 200 ms for a typical review |
| O8 | Be deployable and testable | Docker image, health endpoint, automated tests |

---

## 3. Requirements

### 3.1 Functional requirements

| ID | Requirement |
| --- | --- |
| F1 | The user pastes review text into a single text box and presses one button. |
| F2 | The system returns one spoiler-free review as one or more paragraphs. |
| F3 | Paragraph breaks in the input are preserved in the output. |
| F4 | A review with no spoilers is returned unchanged. |
| F5 | If the output cannot be verified as safe, the user is told that a checked review is unavailable and no review text is shown. |
| F6 | Invalid or oversized input is rejected with an explanatory message. |

### 3.2 Non-functional requirements

| ID | Requirement |
| --- | --- |
| N1 | Privacy: review text is not stored by the pasted-review path. |
| N2 | Reliability: health and readiness endpoints for monitoring. |
| N3 | Security: request size limits, per-IP rate limits, content-security-policy headers. |
| N4 | Maintainability: automated tests covering each failure found in real use. |
| N5 | Portability: runs on Windows and Linux; runs in a container. |

---

## 4. Background and related work

### 4.1 Spoiler detection in the literature

Research on spoiler detection generally treats the task as **classification**: label a review or a sentence as "contains spoiler" or "does not". Published approaches include supervised sentence classifiers trained on labelled review corpora, and models that combine review text with plot synopses or reviewer information. These methods need labelled training data and decide only *whether* a spoiler is present. They do not rewrite the text.

### 4.2 Rule-based and parser-based text processing

Rule-based systems use hand-written patterns and linguistic structure. They are transparent, need no training data and give predictable output, but they cover only the patterns their authors anticipate. Dependency parsing exposes the grammatical structure of a sentence (which words modify which). That structure makes it possible to remove a single clause, such as a relative clause, while keeping the main clause grammatical.

### 4.3 Why a rule-based design was chosen here

| Consideration | Rule-based choice |
| --- | --- |
| No labelled spoiler data was available | Rules need none |
| "Keep other sentences exactly" is a hard requirement | Rules only touch sentences where a pattern fires; a learned model can alter text unpredictably |
| Explainability for a course project | Every decision traces to a named pattern |
| Offline, low-cost deployment | Small footprint, fast |
| Cost | A hosted language model would need a paid key |

The trade-off is lower coverage than a trained model could reach; this is discussed in sections 9 and 10.

### 4.4 Tools used

| Tool | Role in the project |
| --- | --- |
| **spaCy 3.8** with `en_core_web_sm` 3.8.0 | Sentence splitting, part-of-speech tags, dependency parse, lemmas |
| **VADER** 3.3.2 | Sentiment polarity of short phrases, used to recognise evaluative words when deciding what reviewer wording can be kept |
| **Regular expressions** | Cue sets for plot events, reveals, outcomes and character fates |
| **Flask 3.1 / Waitress** | Web interface and production server |
| **Flask-Limiter** | Per-IP rate limiting |
| **pytest** | Automated tests |
| **Docker / Render** | Packaging and hosting |

---

## 5. System design

### 5.1 Overview

```text
 Pasted review
      |
      v
 [1] Validate and normalise
      |   length limits, Unicode normalisation, markdown / link clean-up
      v
 [2] Parse (spaCy)
      |   sentences, parts of speech, dependency tree, lemmas
      v
 [3] Detect spoiler cues in each sentence
      |   EVENTS, REVEALS, HIDDEN_REVEALS, OUTCOMES, CHARACTER_FATES
      |   minus exemptions (GENRE_CUES, craft vocabulary)
      v
 +----+--------------------------------------------+
 | no cue                       | cue found        |
 v                              v                  |
 keep sentence unchanged     [4] Decide scope       |
                                 cue in a subordinate clause -> remove that clause
                                 cue in main clause -> rewrite whole sentence
                                                   |
                                                   v
                              [5] Rewrite
                                  keep the reviewer's reaction, point it at a
                                  neutral phrase; otherwise use a varied
                                  neutral line
      +--------------------------------------------+
      v
 [6] Assemble paragraphs, de-duplicate filler, merge consecutive spoilers
      v
 [7] Final safety check
      |   re-scan output for disclosures and long copied runs of source text
      v
 Spoiler-free review  (or "checked review unavailable")
```

### 5.2 Design principles

1. **Do no harm to harmless text.** A sentence with no cue is never modified.
2. **Smallest possible edit.** Remove a clause before rewriting a sentence; rewrite a sentence before dropping it.
3. **Keep the reviewer's voice.** The reaction ("blew my mind", "gives me chills") is kept; the revealed fact is replaced.
4. **Fail closed.** If the final check finds a disclosure, show nothing rather than a risky result.
5. **Explainable.** Each decision comes from a named pattern or a parse relation.

### 5.3 Module structure

| Module | Responsibility |
| --- | --- |
| `serve.py` | Production entry point (Waitress), configuration from environment variables |
| `app.py` | Flask application, routes, rate limiting, security headers |
| `pipeline.py` | Validation, shared cue sets, output safety check |
| `source_writer.py` | Parsing, spoiler detection, clause removal, rewriting, assembly |
| `static/app.js`, `templates/index.html`, `static/style.css` | One-page user interface |
| `editorial_writer.py` | Optional hosted-model writer (disabled by default; its output passes the same safety check) |
| `movie_source.py`, `movie_store.py`, `build_catalog.py` | Earlier title-search and saved-report experiments, retained but not used by the page |

---

## 6. Implementation

### 6.1 Input validation and normalisation

The text is Unicode-normalised, curly apostrophes are mapped to plain ones, markdown links are reduced to their label, URLs are removed, and length limits are enforced. Limits exist to bound memory and processing time.

### 6.2 Sentence analysis

spaCy splits the text into sentences and assigns each token a part of speech, a lemma and a dependency relation to its head. The dependency tree is used in the next two stages.

### 6.3 Spoiler cue sets

Detection uses several compiled pattern sets. Each has a distinct job.

| Pattern set | What it detects | Example match |
| --- | --- | --- |
| `EVENTS` | Deaths, betrayals, reveals, marriages, arrests, escapes | "the hero dies", "betrays" |
| `REVEALS` | Twist and ending language; a match withholds the **whole sentence** | "turns out", "the climax", "final act" |
| `HIDDEN_REVEALS` | Identity and family reveals, "it was all a dream", "all along", "the whole time", "wakes up in", explicit `Spoiler:` markers | "Vader is Luke's father", "it was all a simulation" |
| `OUTCOMES` | Results of plot threads | "stabs", "drowns", "inherits", "vanishes" |
| `CHARACTER_FATES` | What happens to a character, handled per clause | "doesn't survive", "loses his arm", "faked her own disappearance" |
| `GENRE_CUES` | **Exemptions**: genre labels that contain cue words | "a gripping revenge thriller" |

Two kinds of exemption keep harmless text safe:

- Genre labels such as "revenge thriller" or "crime drama" are not spoilers even though "revenge" and "crime" are cue words elsewhere.
- Craft vocabulary such as "dream sequences" or "shattering performance" is excluded from the event patterns.

### 6.4 Deciding how much to change

For each sentence, the system gathers every cue span and then uses the dependency tree:

- If **no cue** is found, the original sentence is returned as written.
- If a cue lies inside a **subordinate unit** (a relative, adverbial or coordinated clause), only that clause is removed, together with any dangling conjunctions or prepositions. The rest of the sentence is kept.
- If the cue is in the **main clause**, or the match is of the severe kind (`REVEALS`, `HIDDEN_REVEALS`), the whole sentence is rewritten.

A sentence whose subject or main verb would be removed cannot be repaired by deletion, so it is rewritten instead.

### 6.5 Rewriting

Rewriting is attempted in this order:

1. **First-person reaction.** "I couldn't believe the detective was the killer all along" becomes "I couldn't believe the big surprise."
2. **Reaction clause.** For sentences such as "…, which blew my mind", the reaction clause is kept and its subject is replaced by a neutral phrase: "The big surprise blew my mind."
3. **Appraisal of the story moment.** If the reviewer evaluated the ending or climax ("the cold, emotionally crushing climax"), the evaluation is kept: "The story builds to a cold, emotionally crushing climax."
4. **Neutral replacement line.** If no reviewer opinion can be kept, a line from a pool is used. The pool is chosen by the kind of spoiler (ending, climax, twist, character fate, other plot).

Two safeguards apply during rewriting:

- **Craft praise stays on the craft.** In "The visual effects are stunning, but I hated that the hero dies", the praise remains attached to the visual effects and is never moved onto the plot.
- **Factual words are never reused as opinion words.** A predicate such as "dead" is not allowed to become "The big surprise is dead".

The neutral-line pool, with example lines:

| Kind | Example line |
| --- | --- |
| Ending | "The ending is best experienced without knowing what's coming." |
| Climax | "The climax is best experienced fresh." |
| Twist | "There's a surprise here that's best left unspoiled." |
| Character fate | "Where the characters end up is best seen for yourself." |
| Other plot | "Key plot details are left out here to keep the experience fresh." |

### 6.6 Assembly

Sentences are joined back into paragraphs, preserving the reviewer's paragraph breaks. Three rules govern the replacement lines:

- A line is never used twice in the same review.
- Consecutive spoiler sentences are merged into a single replacement line.
- Opinion sentences are never merged or reordered.

### 6.7 Final safety check

The assembled text is checked once more. The check:

- searches for disclosure words from the event, outcome and reveal sets;
- compares runs of ten consecutive words against the original review, to catch long verbatim copies of text that should have been removed;
- if anything is found, replaces the output with "A checked spoiler-free review is unavailable for this report" and removes the review fields from the response.

This design **fails closed**. Its cost is that one bad rewrite can withhold an entire result; section 9.3 describes a real case.

### 6.8 Web interface and API

The page has one text box, one button and one result area. The front end rejects any response that is not marked as checked. The main endpoint is:

| Endpoint | Purpose |
| --- | --- |
| `POST /api/analyze` | Takes the review text, returns the spoiler-free review |
| `GET /healthz`, `GET /readyz` | Liveness and readiness probes |

The API returns no rating or score. Any earlier score fields are removed from responses, including any found in old cached reports.

### 6.9 Security and operations

| Control | Setting |
| --- | --- |
| Request body limit | 4 MB |
| Rate limit | 240 requests per minute per IP address |
| Response headers | `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` |
| Server | Waitress, no debugger, 8 worker threads by default |
| Container | Non-root user, health check, `/data` volume |
| Secrets | Optional model key is read from environment only; never stored in code |

---

## 7. Testing and evaluation

### 7.1 Automated test suite

The suite contains **212 tests, all passing**. It is organised by what each file protects.

| Test file | Tests | Protects |
| --- | ---: | --- |
| `test_pipeline.py` | 88 | Core pipeline behaviour, real reviews, output safety check |
| `test_app.py` | 40 | HTTP endpoints, response contract, rejection of unchecked payloads |
| `test_movie_source.py` | 31 | Legacy source retrieval |
| `test_spoiler_detection.py` | 26 | Hidden identities, character fates, kept reactions, varied filler |
| `test_spoiler_cases.py` | 19 | Nine full spoiler-heavy reviews and related cases |
| `test_editorial_writer.py` | 7 | Optional model writer and its guard |
| **Total** | **212** | |

Test reviews include well-known plots (*The Sixth Sense*, *Fight Club*, *Drishyam*, *Avengers: Endgame*, *Gone Girl*, *Shutter Island*, *Parasite*, *Kantara*), and reviews of *Jailer* and *Irumudi* that previously caused failures.

### 7.2 Measurement experiment

A dedicated script (`artifacts/measure.py`) runs fixed test sets through the live pipeline and reports four measures. The test sets are written by the developer; they are not independent data.

| Set | Size | Purpose |
| --- | ---: | --- |
| Spoiler sentences | 25 | Each preceded by a harmless sentence; each has terms that must not appear in the output |
| Harmless sentences | 20 | Must come back word for word and not be blocked |
| Mixed reviews | 48 | A harmless sentence, then a spoiler, then another harmless sentence; the harmless ones must survive |
| Timing runs | 25 short, 15 long | Latency of the whole pipeline |

The spoiler set covers: identity and family reveals; "all along" and "the whole time" twists; dream, simulation and imagination twists; death and survival; character injuries and fates; betrayal; faked events and framing; explicit `Spoiler:` markers; and endings stated with "in the end".

### 7.3 Earlier evaluation script

`evaluate.py` runs the earlier aspect-based component on 26 synthetic examples. Its data file is labelled in the project as **synthetic sanity-check data, not a held-out benchmark**.

---

## 8. Results

### 8.1 Spoiler removal, preservation and speed

| Measure | Result |
| --- | --- |
| Spoiler sentences tested | 25 |
| Spoilers that leaked into the output | **0 of 25** |
| Reviews where the whole output was blocked | 0 |
| Opening harmless sentence lost | 0 of 25 |
| Harmless sentences tested | 20 |
| Harmless sentences changed or blocked | **0 of 20** |
| Mixed reviews tested | 48 |
| Reviews in which the surrounding harmless sentences stayed intact | **48 of 48** |
| Latency, short review (about two sentences), median / 95th percentile | 20 ms / 26 ms |
| Latency, long review (297 words), median / maximum | 127 ms / 170 ms |
| Automated tests passing | 212 of 212 |

A second, separate probe of 16 tricky review sentences (`artifacts/probe_spoilers.py`) also showed 0 leaks.

### 8.2 The measurement found a real gap

The first run of the measurement set found **one leak out of 25**: "Amy faked her own disappearance to frame Nick for murder." The system kept "faked her own disappearance to frame Nick". This is the value of testing against a wider set. The pattern set was extended to cover faked or staged events and framing, a test was added, and the set was re-run with 0 leaks. It also shows that the earlier 0-leak figure from the 16-case probe overstated how complete the rules were.

### 8.3 Before and after

| Behaviour | Early version | Final version |
| --- | --- | --- |
| Harmless sentence "Great visuals." | Rewritten to "The visuals are Great." and preceded by a filler sentence | Kept exactly |
| Filler for spoilers | Same two lines repeated ("The story takes a significant turn.") | Chosen by spoiler kind; never repeated; consecutive spoilers merged |
| "…, which blew my mind" | Reaction dropped | "The big surprise blew my mind." |
| Hidden identity ("X is Luke's father") | Passed through | Detected and rewritten |
| Dream / simulation / "all along" twists | Passed through | Detected and rewritten |

### 8.4 Worked example

Input:

> The cast is superb and the songs are catchy. In the end the hero dies saving his village. The cinematography is gorgeous.

Output:

> The cast is superb and the songs are catchy. The ending is best experienced without knowing what's coming. The cinematography is gorgeous.

The first and third sentences are identical to the input. Only the sentence that discloses the hero's death was rewritten. More examples are in Appendix B.

---

## 9. Discussion: what went wrong and what was learned

The project went through several design changes. Each taught something about this kind of system.

### 9.1 A scoring feature was built and then removed

An early version also showed an estimated score out of 10 for each review, computed from stated ratings ("8/10", "4 out of 5 stars") and the sentiment of the text. It was removed at the request of the project owner. The score was an estimate from wording, not a verified critic rating, and could be misleading on sarcasm or unusual phrasing. The feature, its module and its tests were taken out of the page, the API, the code and the documentation, and the API now strips any score field.

### 9.2 A semantic layer was tried and reverted

To catch spoilers that the rules miss, a semantic layer was added. It used a small sentence-embedding model to compare each sentence with example plot sentences. In a test of 12 hard cases it detected spoilers the rules missed, but in use it **changed sentences that were not spoilers**. That violated the core requirement, that harmless text stay exactly as written. It also raised memory use from about 238 MB to about 398 MB, which is risky on a 512 MB free host. It was removed. The decision shows a general lesson: a detector that improves recall at the cost of changing harmless text can be worse than one with lower recall that never does.

### 9.3 A review was blocked entirely (the *Devara* case)

A user pasted a full plot summary of *Devara: Part 1* and received only "A checked spoiler-free review is unavailable". Investigation found two causes:

1. The rewriter produced "The big surprise is dead." The safety check correctly saw the word "dead" and blocked everything.
2. A broad outcome pattern treated the harmless setup phrase "a moral transformation and turns against the smuggling rings, vowing to…" as a plot outcome.

Both were fixed: factual predicates are no longer reused as opinion words, and the outcome pattern was narrowed. The exact review is now a regression test. The setup and rival description pass through unchanged, and the death and identity reveals are replaced. **Lesson:** a strict fail-closed check is correct, but a failure in it should be fixed by improving the rewriter, not by loosening the check.

### 9.4 Repetitive filler

Early output repeated one or two generic lines such as "The story takes a significant turn." A pool of lines chosen by spoiler kind, with no repeats and with consecutive spoilers merged, replaced them.

### 9.5 General lessons

| Lesson | Evidence |
| --- | --- |
| Test against real failures, and keep each as a regression test | Devara, Jailer, Irumudi cases |
| Measure on a wider set than the one used to build the rules | The 16-case probe passed, then the 25-case set found a leak |
| Stay faithful to the stated requirement | The semantic layer improved recall but broke "other sentences stay the same" |
| Fail closed, and keep failures rare by fixing causes | Devara case |

---

## 10. Limitations

1. **Rule coverage is incomplete.** A spoiler phrased in a way no pattern expects can pass through unchanged. The system gives no guarantee of a spoiler-free result.
2. **Results come from developer-written tests.** The 25, 20 and 48 case sets were written by the developer who wrote the rules. They are not an independent benchmark, and real-world accuracy is **unknown**. No claim about accuracy on real reviews is made.
3. **Over-removal is possible.** A harmless sentence containing a cue word may be changed. Genre and craft exemptions reduce this but cannot remove it.
4. **Replacement lines are generic by design.** They protect the reader but add no information.
5. **The fail-closed check can withhold a whole result** because of a single bad rewrite.
6. **English only.** No language detection is performed.
7. **Parser dependence.** The small spaCy model can mis-parse long, unusual or badly punctuated sentences, which can affect which clause is removed.
8. **No coreference resolution.** If a sentence refers to a hidden fact through a pronoun ("this changes everything"), nothing links it to the earlier sentence.
9. **Free-host constraints.** The free Render plan has 512 MB memory, sleeps after about 15 minutes idle (the first request then takes about 30–60 seconds) and has a temporary disk.
10. **Legacy code.** Earlier title-search and saved-report code remains in the repository but is not used by the page.

---

## 11. Ethical, privacy and safety considerations

- **Privacy.** The pasted-review path does not store review text. Processing is local; no third-party service is called in the default configuration.
- **Optional hosted model.** If an operator enables it, review-derived text is sent to the model provider. The key must be supplied through environment settings only. This option is off by default.
- **Honesty about guarantees.** The interface says "spoiler-free", but the system cannot prove it. Users should not treat the result as a guarantee.
- **Faithfulness.** The system rewrites only spoiler sentences and never adds opinions the reviewer did not express. The replacement lines are neutral statements about the viewing experience.
- **Copyright.** The system transforms text supplied by the user and does not scrape or republish third-party review text.
- **Abuse.** Size limits, rate limits and security headers limit misuse of the public endpoint.

---

## 12. Deployment

| Item | Detail |
| --- | --- |
| Run locally | `.\.venv\Scripts\python.exe serve.py`, then open http://127.0.0.1:8080 |
| Container | `Dockerfile` based on `python:3.13-slim`, non-root user, health check, `/data` volume |
| Hosting | `render.yaml` defines a Docker web service on Render's **free plan**, health check `/healthz`, auto-deploy on every push to `main` |
| Source control | https://github.com/tejeshwar20/clearcut (12 commits) |
| Environment | `PORT`, `HOST`, `CLEARCUT_THREADS`, `CLEARCUT_WRITER` (`local` by default), `CLEARCUT_RATE_STORAGE`, `CLEARCUT_TRUST_PROXY`, `CLEARCUT_PROXY_IP` |

**Deployment status.** The configuration is committed and the application runs locally. A public Render service must be created from the owner's Render account; this report does not claim a live public URL. *(If a public URL exists when you submit, add it here.)*

---

## 13. Conclusion and future work

### 13.1 Conclusion

ClearCut shows that a transparent, rule-based NLP pipeline can rewrite review spoilers while leaving every harmless sentence exactly as written. It meets its design goals on the test sets used: no spoilers leaked in 25 cases, no harmless sentence was changed in 20 cases, 48 of 48 mixed reviews kept their harmless sentences, and the system responds in tens of milliseconds. The final design was shaped by decisions to *remove* features that conflicted with the core requirement: a score that was only an estimate, and a semantic layer that altered harmless text.

The main weakness is untested generalisation. Rules written by one developer will miss phrasings that the developer did not imagine, and the reported figures come from that same developer's tests.

### 13.2 Future work

| Priority | Work | Why |
| --- | --- | --- |
| 1 | Build an **independent evaluation set** of 100 or more real reviews, labelled by at least two people for spoiler sentences | Measures real precision, recall and over-removal; shows inter-annotator agreement |
| 2 | Show which sentences were changed (for example a subtle highlight) | Transparency for the reader |
| 3 | Add a **language check** that politely refuses non-English input | Avoids silent failure |
| 4 | Keep more of the reviewer's own words around a spoiler when it is safe | More specific, less generic rewrites |
| 5 | Compare against a trained sentence classifier as a recall-only **warning** (not a rewriter) | Gains recall without altering harmless text |
| 6 | Add pronoun-link handling for follow-up sentences such as "this changes everything" | Closes limitation 8 |
| 7 | Remove or archive the legacy catalog code | Smaller, clearer project |

---

## 14. References

1. spaCy documentation: *Linguistic features, dependency parsing and rule-based matching*. https://spacy.io
2. Hutto, C. J. and Gilbert, E. (2014). *VADER: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text.* Proceedings of the 8th International AAAI Conference on Weblogs and Social Media.
3. Jurafsky, D. and Martin, J. H. *Speech and Language Processing* (3rd ed. draft), chapters on dependency parsing and text classification.
4. Pallets Projects: Flask documentation. https://flask.palletsprojects.com
5. Waitress documentation. https://docs.pylonsproject.org/projects/waitress
6. Render documentation: *Blueprints (render.yaml) and Docker deploys*. https://render.com/docs
7. Project repository and commit history. https://github.com/tejeshwar20/clearcut

*Note for the author: add any further published sources on spoiler detection that you consulted in your course; the list above covers the tools and methods actually used in this project.*

---

## Appendix A: repository structure

```text
nlp_project/
  app.py                  Flask routes, rate limits, security headers
  serve.py                Waitress entry point
  pipeline.py             Validation, shared cue sets, output safety check
  source_writer.py        Spoiler detection, clause removal, rewriting
  editorial_writer.py     Optional hosted-model writer (off by default)
  movie_source.py         Legacy: title search
  movie_store.py          Legacy: saved reports
  build_catalog.py        Legacy: catalog builder
  evaluate.py             Evaluation script (synthetic data)
  templates/index.html    Page
  static/app.js, style.css  Front end
  tests/                  212 automated tests
  artifacts/              measure.py, probe_spoilers.py, check_live.py
  data/                   Legacy catalog, evaluation examples
  docs/                   This report, deployment guide, explanation notes
  Dockerfile, render.yaml Packaging and hosting
  requirements.txt        Dependencies
```

Approximate size: application code about 2,150 lines of Python plus about 165 lines of front end; tests about 1,010 lines.

## Appendix B: worked examples

All outputs below were produced by the final system.

| # | Input | Output |
| --- | --- | --- |
| 1 | The acting is superb. Darth Vader is Luke's father, and that scene still gives me chills. The pacing is tight. | The acting is superb. The big surprise still gives me chills. The pacing is tight. |
| 2 | Great visuals. It was all a simulation the whole time, which blew my mind. | Great visuals. The big surprise blew my mind. |
| 3 | Fun ride. Turns out the mentor was the villain, which I didn't see coming. | Fun ride. I didn't see the big surprise coming. |
| 4 | Beautifully shot. The dog doesn't survive, so bring tissues. | Beautifully shot. The story takes an emotional turn, so bring tissues. |
| 5 | The cast is superb and the songs are catchy. In the end the hero dies saving his village. The cinematography is gorgeous. | The cast is superb and the songs are catchy. The ending is best experienced without knowing what's coming. The cinematography is gorgeous. |
| 6 | The visual effects are stunning, but I hated that the main character dies at the end. | The visual effects are stunning. |
| 7 | A tense, gripping war drama with strong performances. | *(unchanged)* |
| 8 | I'd watch it again tomorrow. The dream sequences are gorgeous. | *(unchanged)* |

**Case study: the *Devara* review.** The pasted text contained a setup section and sections headed "The Major Twist" and "The Climax & Ending". The final output keeps the setup and the description of the rival word for word, and replaces the twist and ending with a neutral line:

> Devara: Part 1 (2024) The Setup: Set against the backdrop of coastal lands in the 1980s and 90s, Devara (Jr. NTR) is a fearless man living in a village whose people rely on smuggling via the sea to make a living. When Devara realizes that their illegal trade is bringing blood, destruction, and a bad omen to their lives, he undergoes a moral transformation and turns against the smuggling rings, vowing to protect the sea rather than exploit it. This puts him at direct odds with his fierce rival, Bhaira (Saif Ali Khan), who wants to continue the lucrative criminal enterprise. There's a surprise here that's best left unspoiled.

## Appendix C: how to run and test

```powershell
# one-time setup
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# run the web app, then open http://127.0.0.1:8080
.\.venv\Scripts\python.exe serve.py

# run the 212 automated tests
.\.venv\Scripts\python.exe -m pytest -q

# run the measurement experiment (section 7.2 and 8.1)
.\.venv\Scripts\python.exe artifacts\measure.py
```
