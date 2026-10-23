"""Review score estimation (0-10) from spoiler-safe text plus any rating the reviewer stated."""

import math
import re

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Explicit ratings: "8/10", "8.5 / 10", "4 out of 5", "3.5 stars", "4/5 stars", "★★★★☆".
_FRACTION = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d)?)\s*(?:/|out\s+of)\s*(10|5|4|100)(?!\.?\d)(?:\s*stars?)?", re.I)
_STARS = re.compile(r"(?<![\d.])(\d(?:\.5)?)\s*(?:-|\s)?stars?\b", re.I)
_STAR_GLYPHS = re.compile(r"([★]+)([☆]*)")

# Multi-word reviewer idioms VADER misreads. Matched phrases are scored here and
# removed before the rest of the sentence goes to VADER.
PHRASES = {
    r"\bnot\s+(?:entirely\s+)?perfect\b": -0.1,
    r"\bnot\s+(?:a\s+)?(?:bad|terrible|awful)\b": 0.3,
    r"\bnot\s+(?:great|good|very\s+good)\b": -0.45,
    r"\bnothing\s+special\b": -0.35,
    r"\bworth\s+(?:a\s+)?(?:watch|watching|seeing|your\s+time|the\s+wait|it)\b": 0.55,
    r"\bnot\s+worth\b": -0.6,
    r"\bmust[-\s](?:see|watch)\b": 0.8,
    r"\bwaste\s+of\s+(?:time|money|talent)\b": -0.85,
    r"\bwalked\s+out\b": -0.6,
    r"\b(?:best|finest)\s+(?:film|movie|show|series)s?\b": 0.8,
    r"\b(?:worst|weakest)\s+(?:film|movie|show|series)s?\b": -0.85,
    r"\bfell\s+flat\b": -0.6,
    r"\bmissed\s+(?:the\s+)?mark\b": -0.55,
    r"\bover-?hyped\b": -0.45,
    r"\bhighly\s+recommend(?:ed)?\b": 0.75,
    r"\bwouldn't\s+recommend\b|\bwould\s+not\s+recommend\b|\bcan't\s+recommend\b": -0.65,
    r"\bstays?\s+with\s+you\b": 0.5,
    r"\bon\s+the\s+edge\s+of\s+(?:my|your)\s+seat\b": 0.6,
}

# Mood/genre/plot words describe the film, not the reviewer's verdict.
NEUTRAL_WORDS = {
    "dark", "darker", "tense", "grim", "gritty", "violent", "violence", "brutal", "sad", "tragic",
    "tragedy", "scary", "creepy", "bleak", "dread", "disturbing", "death", "die", "dies", "died",
    "kill", "kills", "killed", "killer", "murder", "murders", "crime", "war", "fear", "horror",
    "villain", "villains", "evil", "revenge", "grief", "cry", "tears", "thriller", "drama",
    "comedy", "funny", "serious", "intense", "shocking", "twist", "twists",
    "bloody", "unhinged", "war", "wage", "smuggler", "criminal", "crushing", "cold", "brutally",
    "vigilante", "battle", "fight", "fights", "attack", "destroy", "threat", "danger", "dangerous",
    "torture", "corrupt", "weapon", "gun", "guns", "prison", "warden", "retired", "mild-mannered",
}
# Words reviewers use as praise that VADER's default lexicon misses.
PRAISE = {
    "masterpiece": 3.2, "flawless": 3.0, "electric": 2.0, "swagger": 1.5, "jaw-dropping": 2.5,
    "gripping": 2.2, "riveting": 2.4, "masterful": 2.8, "masterfully": 2.6, "stunning": 2.6,
    "breathtaking": 2.8, "mesmerizing": 2.5, "mesmerising": 2.5, "compelling": 2.0, "engrossing": 2.0,
    "immersive": 1.8, "nuanced": 1.6, "layered": 1.2, "assured": 1.4, "slick": 1.2, "stylish": 1.6,
    "subverts": 0.8, "earned": 1.0, "terrific": 2.6, "superb": 2.8, "phenomenal": 2.9,
    "legendary": 2.4, "iconic": 2.0, "meticulous": 1.8, "devastating": 0.8, "harrowing": 0.6,
    "gut-wrenching": 0.8, "heartbreaking": 0.6, "unforgettable": 2.4, "spellbinding": 2.6,
}
CRITICISM = {
    "forgettable": -1.6, "mediocre": -1.8, "bland": -1.6, "lifeless": -2.2, "wooden": -1.5,
    "incoherent": -2.0, "bloated": -1.6, "tedious": -1.9, "predictable": -1.2, "derivative": -1.3,
    "overlong": -1.3, "uneven": -1.0, "contrived": -1.5, "cliched": -1.3, "clichéd": -1.3,
    "messy": -1.4, "underwhelming": -1.8, "disappointing": -2.0, "pointless": -1.9, "drags": -1.2,
}
CONTRAST = re.compile(r"\b(?:but|however|though|although|yet|still|nevertheless)\b", re.I)


def build_analyzer(base_lexicon=None):
    analyzer = SentimentIntensityAnalyzer()
    if base_lexicon:
        analyzer.lexicon.update(base_lexicon)
    for word in NEUTRAL_WORDS:
        analyzer.lexicon[word] = 0.0
    analyzer.lexicon.update(PRAISE)
    analyzer.lexicon.update(CRITICISM)
    return analyzer


def stated_rating(text):
    """Return the reviewer's own rating normalised to 0-10, if they gave one."""
    values = []
    for match in _FRACTION.finditer(text):
        value, scale = float(match.group(1)), float(match.group(2))
        if 0 <= value <= scale:
            values.append(10 * value / scale)
    if not values:
        for match in _STARS.finditer(text):
            value = float(match.group(1))
            if 0 <= value <= 5:
                values.append(2 * value)
    if not values:
        for match in _STAR_GLYPHS.finditer(text):
            full, empty = len(match.group(1)), len(match.group(2))
            if full + empty == 5 or (not empty and full <= 5):
                values.append(2 * full)
    return sum(values) / len(values) if values else None


def sentence_score(analyzer, sentence):
    """Signed opinion strength for one sentence, or None when it carries no opinion."""
    sentence = re.sub(_FRACTION, " ", sentence)
    parts = []
    # After a contrast word the reviewer's real verdict usually follows: weight it more.
    pieces = CONTRAST.split(sentence)
    for index, piece in enumerate(pieces):
        weight = 1.0 if len(pieces) == 1 else (0.6 if index < len(pieces) - 1 else 1.4)
        for pattern, value in PHRASES.items():
            for _ in re.finditer(pattern, piece, re.I):
                parts.append((value, weight))
            piece = re.sub(pattern, " ", piece, flags=re.I)
        polarity = analyzer.polarity_scores(piece)
        if polarity["pos"] or polarity["neg"]:
            parts.append((polarity["compound"], weight))
    if not parts:
        return None
    total = sum(weight for _, weight in parts)
    return sum(value * weight for value, weight in parts) / total


def text_polarity(analyzer, texts):
    sentences = [part for text in texts for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]
    scores = [score for score in (sentence_score(analyzer, sentence) for sentence in sentences) if score is not None and abs(score) >= 0.05]
    if not scores:
        return None
    mean = sum(scores) / len(scores)
    # Agreement: consistent praise/criticism keeps its strength; reviews that flip between
    # praise and criticism are pulled toward the middle of the scale.
    positive = sum(1 for score in scores if score > 0)
    agreement = abs(2 * positive - len(scores)) / len(scores)
    return max(-1.0, min(1.0, mean * (0.8 + 0.2 * agreement)))


def to_ten(polarity):
    return round(min(10.0, max(0.0, 5 + 5 * polarity)), 1)


def estimate_score(analyzer, safe_texts, reviews):
    """Combine stated ratings (per review) with sentiment of the spoiler-safe text."""
    stated = []
    for review in reviews:
        if review.get("confidence", 1) == 0:
            continue
        rating = review.get("rating")
        if rating is None:
            rating = stated_rating(review.get("text", ""))
        if rating is not None:
            stated.append((rating, review.get("confidence", 1) or 1))
    polarity = text_polarity(analyzer, safe_texts)
    text_score = to_ten(polarity) if polarity is not None else None
    if stated:
        weight = sum(item[1] for item in stated)
        rating = sum(value * conf for value, conf in stated) / weight
        if text_score is None:
            return round(rating, 1), "Reviewer's stated rating."
        return round(0.8 * rating + 0.2 * text_score, 1), "Reviewer's stated rating, adjusted slightly by the tone of the review."
    if text_score is None:
        return None, "No clear opinion to score."
    return text_score, "Estimated from the sentiment of the spoiler-free review, not a verified critic rating."
