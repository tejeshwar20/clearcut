# Project Explanation and Viva Guide

## One-Minute Explanation

"My project takes several English movie reviews and produces separate opinions
about acting, pacing, visuals, writing, plot, characters, and ending. I first split
reviews into sentences. I mark sentences risky using spoiler cues and name
density. Then I match aspect phrases and apply lexicon-based sentiment to their
local context. Risky opinions do not vote. I deduplicate opinions using TF-IDF
similarity, combine the remaining votes, and use MMR to select diverse evidence
references. Finally, I render fixed verdict templates rather than generating
or quoting plot text. It is explainable but not a perfect spoiler detector."

## Data Flow

```text
Paste / CSV / JSON
    -> validate and normalize Unicode
    -> tokenize sentences
    -> sentence spoiler features + limited contextual propagation
    -> match aspect spans
    -> reject risky mentions (ending gated by default)
    -> assign local aspect sentiment
    -> TF-IDF similarity / remove near duplicates
    -> weighted aspect votes + MMR representative references
    -> fixed verdict labels / safe JSON export
```

In title-search mode, the retrieval input is restricted to a Wikipedia critical-
reception/reviews section. We analyze attributed quotation spans where available,
otherwise the reception paragraph. A source paragraph is not assumed to be one
reviewer or a representative sample; its provenance and limitations are shown.
No fallback extracts plot-summary text. No reception section means no generated
movie review. A brief sentiment overview of safe reception sentences supplies
overall tone; the aspect details still require matching explicit aspect phrases.

## 1. Sentence Segmentation

NLTK's PunktSentenceTokenizer provides a lightweight sentence boundary algorithm.
This instance uses default parameters: no downloaded English training model.
It therefore has weaker handling of abbreviations than trained Punkt. Unicode
normalization maps compatibility forms and curly apostrophes to matchable text.
This is not a multilingual system or full Unicode-obfuscation defense.

## 2. Spoiler Features

The classifier is an interpretable rule system, not a learned probability.
A sentence is risky if any of these applies:

- A cue matches: death, betrayal, identity revelation, a twist, marriage, etc.
- A supplied character/event name matches and name occurrences / word count >= 0.08.
- At least three title-cased words occur and title-case density >= 0.15.
- The preceding sentence was risky and the current sentence contains a pronoun
  or demonstrative such as he, she, their, this, or it. This can propagate through
  multiple sentences. It is a conservative context rule, **not coreference resolution**.

Names are optional. Capitalization is only a weak fallback, with false positives
and false negatives. "A great twist" is deliberately overfiltered. "The keys
belong to her brother all along" may evade the cues. A risky sentence loses all
its aspect mentions, even a safe clause, prioritizing precision of released
evidence over coverage. Ending mentions are additionally gated by default.

## 3. Aspect Extraction

Each aspect has a small synonym dictionary. Case-insensitive, whole-word/phrase
regex matches produce spans. Longer phrases are placed first in each pattern.
Example: "camera work" -> cinematography; "screenplay" -> writing.
Repeated mentions of one aspect within a sentence become one averaged observation.

This is explicit aspect extraction. "It drags" maps to pacing, but implicit
opinions without a known phrase can be missed. "Story" and "writing" remain
separate aspects according to the predefined taxonomy. Dictionary coverage should
be evaluated and extended with development data, not silently tuned on test data.

## 4. Local Aspect Sentiment

VADER is a published, rule-based sentiment analyzer with a polarity lexicon,
negation, degree modifiers, and punctuation conventions. We use its lexicon to
find sentiment words and its compound score on local contexts. We do not train it.

A small explicit `FILM_LEXICON` supplements general VADER vocabulary with terms
such as wooden, rushed, predictable, gripping, and immersive. These manually
assigned scores are inspectable heuristics, not learned parameters. "Slow burn"
is masked with a same-length neutral placeholder before sentiment scoring so
that a style description is not automatically counted as a negative opinion.

Contrast markers and comma/semicolon boundaries split clauses. "And" splits
only if each part has both an aspect and a sentiment word. Within a clause,
each sentiment word attaches to the closest aspect span by character distance.
Its context includes up to three preceding words, bounded by the preceding
sentiment word. Shared single adjectives can apply to multiple aspects.
Average scores when an aspect has several sentiment words or repeated spans.

Compound >= 0.05 means positive; <= -0.05 means negative; otherwise neutral.
These conventional VADER thresholds are not calibrated confidence scores.
This local adaptation may lose some sentence-level punctuation/contrast effects.
It is less capable than dependency parsing at long-range sentiment attachment.

Example: "Excellent acting but terrible pacing" -> acting positive, pacing negative.
Sarcasm such as "Wonderful acting, if you enjoy watching paint dry" can fail.

## 5. Weighted Aggregation

For supplied confidence c and a 0-10 reviewer rating r:

```text
rating_weight = 0.75 + 0.5 * abs(r - 5) / 5   (or 1 if rating absent)
observation_weight = c * rating_weight        (c defaults to 1)
class_share = sum(weights in class) / sum(all retained weights)
```

The rating gives a small weight to strongly expressed overall opinions, whether
high or low. It never decides an aspect's polarity. This is a transparent design
heuristic, **not evidence that extreme reviewers are more reliable**. Use equal
weights when you cannot justify metadata weighting. Confidence is supplied by the
reviewer/dataset, not inferred or calibrated by this model.

A class share >= 0.65 yields Mostly Positive, Mostly Negative, or Neutral.
Otherwise the verdict is Mixed. No retained mentions + filtered mentions gives
Spoiler-Gated. No retained or filtered mentions gives Not Enough Evidence.
Zero-confidence mentions do not vote. A single opinion can yield Mostly Positive;
the displayed support count is essential, not a confidence guarantee.

## 6. Similarity, Deduplication, and MMR

scikit-learn converts safe sentence text into word unigram/bigram TF-IDF vectors.
Cosine similarity >= 0.88 removes later duplicate observations **with the same
sentiment class**, per aspect. First occurrence wins; this avoids repeating votes
but makes input order relevant. Vocabulary/IDF are fitted only to the current
aspect's evidence. Similarity thresholds are heuristics, not semantic equivalence.

MMR selects at most three representatives from the retained unique observations:

```text
relevance(candidate) = 0.5 + 0.5 * abs(sentiment_score)
MMR(candidate) = 0.7 * relevance(candidate)
               - 0.3 * max cosine_similarity(candidate, selected)
```

For the first selection, the redundancy penalty is zero. Greedy selection
balances strong opinions against repetition. Standard MMR usually uses query
relevance; here we explicitly use sentiment strength as a simple proxy.
Deduplication affects aggregation; MMR only selects representative references.
TF-IDF uses the full safe sentence, so unrelated clauses can influence similarity.
Lexical similarity cannot detect all paraphrases. Pairwise similarity uses O(n^2)
space/time per aspect; collection limits keep this teaching demo bounded.

## 7. Output Protection

The `write_review` function converts aggregated verdicts into a readable review
paragraph using fixed templates. It groups positive, negative, mixed, and neutral
aspects, explains withheld opinions, and flags single-opinion support. It does
not infer new facts or recommendations. This is template-based natural language
generation, not an LLM. Both the dashboard and JSON export include the paragraph.

The response builder copies only predefined aspect labels, predefined sentiment
labels, verdicts, counts, proportions, and numeric review references. It never
copies input text. Thus even a missed spoiler cannot become a revealed plot quote
in the report, although it can still affect a sentiment verdict. The input editor
and local import endpoint are not a spoiler-safe boundary: they necessarily hold
original reviews. The generated report is the protected boundary.

## Tests and Evaluation

`python -m pytest -q` covers the pipeline and Flask API, malformed input,
negation, contrasting aspects, coordinated/shared adjectives, gating, duplicate
opinions, confidence/rating handling, Unicode apostrophes, import formats,
resource limits, and seeded randomized input. Browser tests additionally check
desktop/mobile layout and the user flow. These are software regression checks.

`python evaluate.py` measures spoiler precision/recall/F1 and target-aspect
sentiment accuracy/F1 against synthetic examples. Some are intentionally hard.
Do not present these metrics as generalization accuracy. For real evaluation,
have two people independently label permitted review sentences, agree on spoiler
definitions, resolve disagreements, separate development and test collections by
title, and report both safe coverage and spoiler recall. Record false positives
and false negatives. Avoid presenting a test set used to tune rules as held out.

## Viva Questions

**Why not an LLM?** A lexicon and rules are inexpensive, reproducible, offline,
easy to inspect, and appropriate to this course. They have clear limitations.

**Is this ABSA?** Yes: it extracts explicit aspects and assigns sentiment locally
to them. It is a rule-based ABSA baseline, not state-of-the-art ABSA.

**Why gate the ending?** Even opinions about an ending can reveal expectations.
The toggle permits generic ending sentiment, but cue filtering still applies.

**Why no original evidence quotes?** A classifier can miss implicit spoilers.
Templates prevent plot text from leaking into the final report independently of
classifier recall. Review references provide limited traceability without quotes.

**Why not use star ratings as sentiment?** A review can love acting and dislike
pacing. Overall ratings cannot supply aspect labels.

**What would you improve?** Independently labeled evaluation first; then broader
taxonomy, trained sentence boundaries, a supervised spoiler classifier using
Naive Bayes or logistic regression, and syntactic sentiment attachment. None is
claimed to be implemented. Do not add a trained model without sufficient data.

## References

- [CSL772 course and readings](https://www.cse.iitd.ac.in/~mausam/courses/csl772/autumn2014/).
- Hutto & Gilbert (2014), VADER: A Parsimonious Rule-based Model for Sentiment
  Analysis of Social Media Text, ICWSM. [Implementation](https://github.com/cjhutto/vaderSentiment).
- Carbonell & Goldstein (1998), The Use of MMR, Diversity-Based Reranking for
  Reordering Documents and Producing Summaries, SIGIR.
- [scikit-learn text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction).

This is a learning scaffold. Understand and modify the code, perform your own
evaluation, and disclose tool assistance according to your institution's rules.