# ClearCut — Project Report

**Spoiler-free movie and series review rewriting with an estimated score**
Report date: 23 October 2026 · Repository: https://github.com/tejeshwar20/clearcut · Branch `main`, latest commit `c3479d9`

---

## 1. Summary

ClearCut is a Flask web application. A user pastes a movie or TV review, and the app returns:

1. **A spoiler-free version of the same review.** Sentences that give away plot are rephrased into vague, non-revealing wording. Every other sentence is kept word for word.
2. **One estimated score out of 10**, with a one-line explanation of how it was produced.

All text processing runs locally with a rule-based NLP pipeline (spaCy dependency parsing, VADER sentiment, regular-expression cue lists). No API key, paid model or network call is needed to analyse a pasted review. The app is published on GitHub and set up for one-click deployment on Render's free tier.

| Item | Status |
| --- | --- |
| Working app (paste → spoiler-free review + score) | Done, running locally on port 8080 |
| Automated tests | 222 collected, 222 passing |
| Source code | Pushed to GitHub (11 commits) |
| Deployment configuration | `Dockerfile` and `render.yaml` committed (free plan, health check `/healthz`) |
| Live public deployment | Not confirmed. Needs the Render Blueprint to be applied from the user's account |
| Independent benchmark | None. Evaluation uses a small synthetic set (see section 7) |

---

## 2. Problem and goal

Reviews often contain plot reveals. Readers who want an opinion without being spoiled have no simple tool for it. The goal was to take an existing review and rewrite **only the spoiler sentences**, so the reviewer's voice, opinions and wording are otherwise untouched.

Design rules that came out of the project:

- Non-spoiler sentences must stay **exactly as written**.
- A spoiler sentence is **rephrased**, not deleted, and keeps the reviewer's own reaction where possible (for example "…, which blew my mind." becomes "The big surprise blew my mind.").
- Rewrites must **not repeat the same filler line** within a review.
- If the final safety check finds a plot detail in the output, the output is **blocked** rather than shown.

---

## 3. How it works

```text
Pasted review
   │
   ▼
Validate and normalise text (length limits, Unicode, markdown clean-up)
   │
   ▼
spaCy parses each sentence (dependency tree)
   │
   ├── No spoiler cue found ───────────────► keep the sentence unchanged
   │
   └── Spoiler cue found
          ├── Cue only affects one clause ─► remove that clause, keep the rest
          └── Whole sentence is a reveal ──► rephrase (keep reviewer's reaction)
                                              or use a varied neutral line
   │
   ▼
Final safety check (blocks output if death/twist/identity words remain)
   │
   ▼
Score = stated rating (if any) + sentence-level sentiment
   │
   ▼
JSON → web page: review text + "Overall score x / 10"
```

### 3.1 Spoiler detection (`source_writer.py`, `pipeline.py`)

Detection is rule-based, built from several cue sets:

| Rule set | Catches | Example |
| --- | --- | --- |
| `EVENTS` | deaths, betrayals, reveals, marriages, arrests | "the hero dies" |
| `REVEALS` | twist or ending language (always withholds the whole sentence) | "it turns out…", "the final act…" |
| `HIDDEN_REVEALS` | identity and family reveals, "it was all a dream", "all along", "the whole time", "wakes up in…", `Spoiler:` markers | "Vader is Luke's father" |
| `OUTCOMES` | what happens at the end of a plot thread | "stabs", "drowns", "inherits" |
| `CHARACTER_FATES` | fates of characters, handled at clause level | "doesn't survive", "loses his arm" |
| `GENRE_CUES` | **exemptions** so "revenge thriller" is not treated as a spoiler | "a gripping revenge thriller" |

The dependency parse decides **how much** to remove. If a cue sits in a subordinate clause, only that clause is deleted. If the cue is in the main clause, the sentence is rephrased as a whole.

### 3.2 Rewriting (`source_writer.py`)

- **Reaction kept:** a first-person reaction or demonstrative clause is kept and pointed at a neutral phrase ("the big surprise", "the ending").
- **Craft praise stays on the craft:** "The visual effects are stunning, but I hated that the hero dies" keeps the first half intact and does not move "stunning" onto the plot.
- **No repetitive filler:** when no opinion can be kept, a line is chosen from a pool matching the kind of spoiler (ending, climax, twist, character fate, plot), never reused in the same review, with consecutive spoilers merged into one line.
- **Factual words are never reused:** an outcome such as "dead" is never turned into an opinion adjective.

### 3.3 Safety check (`pipeline.enforce_reader_output`)

Before anything is returned, the result is scanned again for disclosure words and for long copied runs of the source text. If anything is found, the user sees "A checked spoiler-free review is unavailable" and no score. This check is deliberately strict, so a single wrong rewrite can block a whole result (this caused the Devara failure described in section 6).

### 3.4 Scoring (`scoring.py`)

The score is an **estimate of tone**, not a critic rating.

- **Stated ratings are used first.** "8/10", "4 out of 5", "3.5 stars" and "★★★☆☆" are read and normalised to 0–10. When present, a stated rating counts for 80% of the score and the text tone for 20%.
- **Text sentiment per sentence** (VADER plus a review-specific vocabulary): praise words such as *gripping*, *masterful*, *legendary*, and criticism such as *bland*, *tedious*, *underwhelming*.
- **Mood words are neutral:** *dark*, *violent*, *brutal*, *revenge* describe a film, not the reviewer's verdict.
- **Common phrases** are handled explicitly ("worth a watch", "nothing special", "waste of time", "not perfect").
- **Contrast words** ("but", "however"): the part after the contrast carries more weight.
- Consistent praise or criticism keeps its strength; reviews that swing between both are pulled toward the middle.

Results on ten sample reviews (before → after tuning): rave 7.2 → 8.4, "good" 7.2 → 7.8, mixed 5.4 → 5.3, "meh" 5.2 → 4.7, bad 2.7 → 1.9, awful 1.4 → 0.9, "8/10" 7.0 → 8.1, "2 out of 5 stars" 8.0 → 4.8.

---

## 4. Architecture and code

| Layer | Files | Role |
| --- | --- | --- |
| Web server | `serve.py` | Waitress production server, `PORT`/`HOST`/threads settings, optional proxy trust |
| API | `app.py` | Flask routes, rate limiting (240/min per IP), security headers |
| Spoiler rewrite | `source_writer.py` (673 lines) | Parsing, cue rules, clause removal, rephrasing, assembly |
| Shared NLP | `pipeline.py` (639 lines) | Validation, event cues, aspect analysis, output safety check |
| Scoring | `scoring.py` (139 lines) | Rating extraction and sentiment calibration |
| Front end | `templates/index.html`, `static/app.js`, `static/style.css` | One textarea, one button, one result block with score |
| Optional model writer | `editorial_writer.py` | OpenAI rewrite, only when `CLEARCUT_WRITER=openai` and a key is set; still passes the same safety check |
| Legacy catalog | `movie_source.py`, `movie_store.py`, `build_catalog.py`, `data/` | Earlier title-search and saved-report experiments, retained but not part of the paste-only page |
| Deployment | `Dockerfile`, `render.yaml` | Container build and Render blueprint |

**API surface:** `POST /api/analyze` is the main endpoint. `GET /healthz` and `/readyz` are health checks. The movie search, saved-report and import endpoints are legacy.

**Libraries:** Flask, Waitress, Flask-Limiter, spaCy 3.8 with `en_core_web_sm`, vaderSentiment 3.3.2, NLTK, scikit-learn, BeautifulSoup, OpenAI SDK (optional), pytest.

**Size:** about 2,000 lines of application Python and about 1,050 lines of tests.

---

## 5. Testing

`222 passed` on the full suite.

| Test file | Focus |
| --- | --- |
| `test_pipeline.py` | Core pipeline, real reviews (Jailer, Irumudi, Breaking Bad), safety guard |
| `test_spoiler_cases.py` | Nine full spoiler-heavy reviews (Sixth Sense, Fight Club, Parasite, Gone Girl and others) |
| `test_spoiler_detection.py` | Hidden-identity and fate patterns, kept reactions, varied fillers, the Devara regression |
| `test_scoring.py` | Rating parsing, score ordering, dark-subject neutrality, contrast handling |
| `test_app.py` | HTTP endpoints, response contract, caching and rejection of unchecked payloads |
| `test_movie_source.py`, `test_editorial_writer.py` | Legacy source and optional model writer |

A separate probe script, `artifacts/probe_spoilers.py`, runs 16 tricky spoiler reviews and reports leaks: **0 of 16** at the last run.

---

## 6. Project history and lessons

| Phase | What happened |
| --- | --- |
| Foundation | Aspect-based review analysis with fixed templates, saved catalog of 100 titles, production server and Docker setup |
| Reader rewrite | Switched to a paste-only page that returns one review and one score |
| Source-grounded writer | Spoiler clauses removed with spaCy parsing, other wording kept |
| Deployment (Oct 2026) | Git repository, GitHub, Render blueprint; free plan chosen |
| Scoring upgrade (`5f1a246`) | Stated ratings, calibrated scale, review vocabulary, contrast handling |
| Stronger spoilers (`d5efdb4`) | Hidden identities, dream/simulation twists, character fates, reaction-preserving rewrites |
| **Reverted:** semantic layer and 50-case rule expansion (`9045075`, `abf64fb`) | Added sentence-embedding detection. Users found it changed sentences that were not spoilers, so it was removed (`5706cf3`). The rule set was returned to `d5efdb4` |
| Filler wording (`5b27f20`) | Replaced repeated "The story takes a significant turn" with varied, non-repeating lines |
| Devara fix (`c3479d9`) | See below |

**Devara case.** A full plot summary was blocked entirely. Two causes: (1) the rewrite produced "The big surprise is dead", which the safety check correctly flagged, and (2) a rule treated the setup phrase "transformation … vowing to" as a plot outcome. Both were fixed, and the exact review is now a regression test. The setup and rival description pass through unchanged; only the reveals are replaced.

**Lessons**

- Adding detection power raised false positives on harmless sentences. The user's priority, "only change spoilers", mattered more than catching every spoiler.
- A strict final safety check is good for safety but can hide an entire result because of one bad rewrite. Fixing the rewrite is better than loosening the check.
- Rule-based systems need a regression test for every real failure.

---

## 7. Evaluation and accuracy

| Measure | Result | Notes |
| --- | --- | --- |
| Unit and integration tests | 222 / 222 pass | Includes the real reviews that failed in use |
| Spoiler probe (own cases) | 0 / 16 leaks | Cases written by the developer, not independent |
| `evaluate.py` spoiler classification | Accuracy 0.92 (F1 0.94 safe, 0.88 risky) | 26 synthetic examples |
| `evaluate.py` aspect sentiment | Accuracy 0.889 | 18 examples |

The project docs state that the bundled evaluation data is a **sanity check, not a held-out benchmark**. No evaluation against independently collected spoiler-labelled reviews has been done, so real-world accuracy is unknown.

---

## 8. Limitations and risks

1. **Spoiler detection is rule-based and cannot be complete.** A spoiler phrased in a way no rule anticipates can pass through unchanged. Nothing guarantees a spoiler-free result.
2. **Over-removal is possible** when a harmless sentence contains a cue word. The strict output check can also withhold a whole result.
3. **Rewritten lines are generic by design.** "The ending is best experienced without knowing what's coming" is safe, but it adds no information.
4. **The score is an estimate from wording.** Sarcasm, unusual phrasing and non-English text can mislead it, and it is not a verified critic score.
5. **English only.**
6. **Memory:** spaCy needs a few hundred MB. Render's free plan has 512 MB and sleeps after about 15 minutes idle, so the first request after sleep takes 30–60 seconds.
7. **Legacy catalog code is still in the repository** (search, saved reports, import) and is not used by the page. The SQLite database on a free host is wiped on each restart.
8. **Documentation lag:** `docs/PROJECT_EXPLANATION.md` still describes the older aspect-template pipeline, not the current rewrite approach.
9. **Rate limits are per IP.** Behind a proxy, all users can appear as one address unless proxy trust is configured (`CLEARCUT_TRUST_PROXY`, `CLEARCUT_PROXY_IP`).

---

## 9. Deployment status

- GitHub repository is live with all commits.
- `render.yaml` defines a Docker web service on the **free** plan with `/healthz` as the health check and auto-deploy on every push to `main`.
- The Render service must be created by the owner (New → Blueprint → select the repo → Apply). After that, each `git push` redeploys automatically.
- Locally: `.\.venv\Scripts\python.exe serve.py`, then open http://127.0.0.1:8080.

---

## 10. Recommended next steps

1. **Collect 50–100 real reviews** with known spoilers and measure leaks and over-removal properly.
2. **Show which sentences were changed**, for example a subtle highlight, so users can see exactly what was rephrased.
3. **Improve rewrite specificity** by keeping more of the reviewer's wording around the spoiler when it is safe.
4. **Update `docs/PROJECT_EXPLANATION.md`** to describe the current pipeline for viva and submission.
5. **Remove or archive the legacy catalog code** to shrink the project and avoid confusion.
6. **Confirm the Render deployment** and test the public URL with a few real reviews.
7. **Consider a language check** that politely refuses non-English input.
