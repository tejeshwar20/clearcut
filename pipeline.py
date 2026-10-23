"""Explainable English aspect sentiment, spoiler filtering, and diverse selection."""

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

from nltk.tokenize import PunktSentenceTokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


ASPECTS = {
    "acting": ("acting", "performances", "performance", "cast", "actors", "actress", "actor", "portrayal", "ensemble"),
    "pacing": ("pacing", "pace", "runtime", "run time", "slow burn", "drags", "dragged"),
    "cinematography": ("cinematography", "visuals", "visually", "visual", "stunning-looking", "photography", "photographed", "camera work", "camerawork", "lighting", "shots", "imagery", "images", "animation"),
    "writing": ("writing", "script", "screenplay", "dialogue", "dialogues", "written", "scripting"),
    "plot": ("plot", "story", "storyline", "storytelling", "narrative"),
    "characters": ("characters", "character", "character development", "protagonist", "villain"),
    "ending": ("ending", "finale", "climax", "conclusion", "final act", "last scene"),
}
PATTERNS = {
    aspect: re.compile(r"\b(?:" + "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)) + r")\b", re.I)
    for aspect, terms in ASPECTS.items()
}
EVENTS = re.compile(
    r"\b(?:dies?|died|dead|death|kills?|killed|killer|murder\w*|betray\w*|"
    r"suicide|survives?|survived|reveals?|revealed|revelation|turns? out|"
    r"identity|secretly|twist|spoiler\w*|resurrect\w*|pregnant|"
    r"marri\w*|wedding|divorc\w*|escapes?|escaped|arrest\w*|"
    r"defeats?|defeated|sacrific\w*|dream(?!\s+(?:sequences?|logic|team|cast|come|role|project|like|-like))|is actually|was actually|"
    r"discovers?|learns?|finds out|unmasked|confesses?|reunites?|"
    r"captured|rescued|unravels?|becomes? the|ends up|"
    r"in the end|at the end|by the end|final scene|last scene|"
    r"true nature|real identity|only a dream|all a dream|"
    r"was the culprit|is the culprit|loses? (?:his|her|their) life)\b", re.I,
)
NEGATORS = re.compile(r"\b(?:he|she|they|his|her|their|this|that|it)\b", re.I)
GENRE_CUES = re.compile(
    r"\b(?:revenge|murder|crime|heist|kidnap\w*|vigilante|serial[- ]killer|survival|spy|war|death|escape)"
    r"[- ](?:thrillers?|dramas?|myster(?:y|ies)|sagas?|films?|movies?|stories|story|tales?|genre|comed(?:y|ies)|epics?|flicks?|procedurals?|noirs?)\b", re.I,
)
TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
SPLIT = re.compile(r"\s+(?:but|however|whereas|although|yet)\s+|[;,]+", re.I)
SENTIMENT = SentimentIntensityAnalyzer()
FILM_LEXICON = {
    "wooden": -2.0, "lifeless": -2.0, "unconvincing": -2.0,
    "underdeveloped": -1.8, "incoherent": -2.0, "predictable": -1.5,
    "rushed": -1.6, "slow": -1.2, "drags": -1.8, "dragged": -1.8,
    "overlong": -1.6, "choppy": -1.5, "cliched": -1.6,
    "gripping": 2.2, "immersive": 2.0, "compelling": 2.0,
    "nuanced": 1.6, "breathtaking": 2.8,
    "expertly": 1.8, "virtuosic": 2.5, "flawlessly": 2.5,
    "commanding": 1.8, "dragging": -1.8,
}
SENTIMENT.lexicon.update(FILM_LEXICON)
SEGMENTER = PunktSentenceTokenizer()
MAX_REVIEWS = 300
MAX_REVIEW_LENGTH = 12000
MAX_TOTAL_LENGTH = 120000
MAX_SENTENCES = 2000

EDITORIAL_TRAITS = (
    ("acting", "nuanced", r"nuanced|understated|subtle|restrained", "positive", "The performances favor nuance and restraint rather than broad gestures."),
    ("acting", "intense", r"ferocious|commanding|powerhouse|magnetic", "positive", "The acting stands out for its intensity and commanding screen presence."),
    ("acting", "emotional", r"moving|heartfelt|vulnerab\w*|emotionally convincing", "positive", "The performances bring emotional weight to the material."),
    ("acting", "wooden", r"wooden|stiff|unconvincing", "negative", "The acting can feel stiff, making the emotional moments less convincing."),
    ("pacing", "slow_burn", r"slow[- ]burn|gradual build|deliberate pace|measured pace", "neutral", "The rhythm is a deliberate slow burn, better suited to viewers who enjoy a gradual build than constant action."),
    ("pacing", "dragging", r"drags|dragging|overlong|sluggish", "negative", "The momentum suffers in places, and the length may test your patience."),
    ("pacing", "rushed", r"rushed|hurried|too fast", "negative", "The pacing can feel hurried, leaving less room for the material to breathe."),
    ("pacing", "gripping", r"gripping|brisk|propulsive|well[- ]paced", "positive", "The pacing keeps the experience moving with a strong sense of momentum."),
    ("cinematography", "striking", r"striking|breathtaking|stunning|gorgeous|beautiful", "positive", "Visually, the production stands out for its striking imagery."),
    ("cinematography", "atmospheric", r"atmospheric|immersive|evocative", "positive", "The visual style builds a strong atmosphere rather than serving as decoration alone."),
    ("writing", "sharp", r"sharp|witty|clever|expertly|flawlessly", "positive", "The writing is praised for its precision and craft."),
    ("writing", "weak", r"clumsy|cliched|clich[eé]d|contrived|weak", "negative", "The writing can feel contrived, making parts of the experience less convincing."),
    ("plot", "complex", r"intricate|layered|complex|ambitious", "neutral", "The storytelling is layered and asks for your attention rather than offering a simple, undemanding watch."),
    ("plot", "engaging", r"engaging|compelling|gripping|absorbing", "positive", "The storytelling gives you a reason to stay invested."),
    ("plot", "predictable", r"predictable|formulaic|incoherent", "negative", "The storytelling is less convincing where it feels familiar or lacks coherence."),
    ("characters", "layered", r"complex|complicated|conflicted|layered|believable", "positive", "The characters have enough complexity to invite interest beyond simple heroes and villains."),
    ("characters", "thin", r"underdeveloped|one[- ]dimensional|shallow|thinly", "negative", "Some characterization feels thin, limiting the emotional connection."),
)


def editorial_evidence(reviews):
    findings = {}
    for review in reviews:
        if review.get("confidence", 1) == 0:
            continue
        prior_risk = False
        for sentence in SEGMENTER.tokenize(review["text"]):
            risk = spoiler_risk(sentence, []) or (prior_risk and bool(NEGATORS.search(sentence)))
            prior_risk = risk
            if risk or PATTERNS["ending"].search(sentence):
                continue
            for aspect, identifier, pattern, sentiment, description in EDITORIAL_TRAITS:
                if not PATTERNS[aspect].search(sentence):
                    continue
                match = re.search(pattern, sentence, re.I)
                if match is None or re.search(r"\b(?:not|never|hardly|isn't|aren't|wasn't|no)\b", sentence[max(0, match.start() - 35):match.start()], re.I):
                    continue
                key = aspect + ":" + identifier
                item = findings.setdefault(key, {"id": key, "aspect": aspect, "description": description, "sentiment": sentiment, "passages": set()})
                item["passages"].add(sentence.casefold().strip())
    return [{**item, "passages": len(item["passages"])} for item in findings.values()]


@dataclass
class Mention:
    aspect: str
    text: str
    review: int
    score: float
    weight: float


def normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("\u2019", "'").replace("\u200b", "")


def validate_reviews(reviews: object) -> list[dict]:
    if not isinstance(reviews, list) or not reviews or len(reviews) > MAX_REVIEWS:
        raise ValueError(f"Provide between 1 and {MAX_REVIEWS} reviews.")
    cleaned = []
    for index, review in enumerate(reviews, 1):
        if isinstance(review, str):
            review = {"text": review}
        if not isinstance(review, dict) or not isinstance(review.get("text"), str):
            raise ValueError(f"Review {index} needs a text string.")
        text = normalize(review["text"]).strip()
        if not text or len(text) > MAX_REVIEW_LENGTH:
            raise ValueError(f"Review {index} must contain 1 to {MAX_REVIEW_LENGTH} characters.")
        entry = {"text": text}
        for key, minimum, maximum in (("rating", 0, 10), ("confidence", 0, 1)):
            value = review.get(key)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum or not math.isfinite(value):
                    raise ValueError(f"Review {index}: {key} must be a number from {minimum} to {maximum}.")
                entry[key] = float(value)
        cleaned.append(entry)
    if sum(len(entry["text"]) for entry in cleaned) > MAX_TOTAL_LENGTH:
        raise ValueError(f"A collection must not exceed {MAX_TOTAL_LENGTH} characters.")
    return cleaned


def spoiler_risk(sentence: str, entities: list[str]) -> bool:
    if EVENTS.search(sentence):
        return True
    tokens = TOKEN.findall(sentence)
    entity_hits = sum(len(re.findall(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", sentence, re.I)) for entity in entities)
    if entity_hits and entity_hits / max(1, len(tokens)) >= 0.08:
        return True
    names = re.findall(r"\b[A-Z][a-z]+\b", sentence)
    return len(names) >= 3 and len(names) / max(1, len(tokens)) >= 0.15


def local_score(clause: str, matches: list[tuple], target: tuple) -> float:
    clause = re.sub(r"\bslow burn\b", "slowburn ", clause, flags=re.I)
    for start, end, aspect in reversed(matches):
        clause = clause[:start] + " " * (end - start) + clause[end:]
    words = list(TOKEN.finditer(clause))
    sentiment_words = [word for word in words if word.group().lower() in SENTIMENT.lexicon]
    center = (target[0] + target[1]) / 2
    owned = []
    for word in sentiment_words:
        position = (word.start() + word.end()) / 2
        nearest = min(abs(position - (match[0] + match[1]) / 2) for match in matches)
        if abs(position - center) <= nearest + 0.01:
            owned.append(word)
    if not owned:
        if len(sentiment_words) == 1:
            return SENTIMENT.polarity_scores(clause)["compound"]
        return 0.0
    scores = []
    for word in owned:
        position = next(index for index, candidate in enumerate(words) if candidate.start() == word.start())
        start = max(0, position - 3)
        previous = [candidate for candidate in sentiment_words if candidate.end() <= word.start()]
        boundary = previous[-1].end() if previous else 0
        snippet = clause[max(words[start].start(), boundary):word.end()]
        negated_errors = re.finditer(r"\b(?:never|not)\s+(?:made|make|makes|committed|commit)\b[^.!?;]{0,100}\b(?:missteps?|mistakes?|errors?)\b", clause, re.I)
        if any(scope.start() <= word.start() < scope.end() for scope in negated_errors):
            snippet = "not " + word.group()
        scores.append(SENTIMENT.polarity_scores(snippet)["compound"])
    return sum(scores) / len(scores)


def label(score: float) -> str:
    return "positive" if score >= 0.05 else "negative" if score <= -0.05 else "neutral"


def opinion_verdict(weights):
    subjective = weights.get("positive", 0) + weights.get("negative", 0)
    if not subjective:
        return "Neutral"
    if weights.get("positive", 0) / subjective >= 0.65:
        return "Mostly Positive"
    if weights.get("negative", 0) / subjective >= 0.65:
        return "Mostly Negative"
    return "Mixed"


def select_diverse(mentions: list[Mention], limit: int = 3) -> tuple[list[Mention], list[Mention]]:
    if not mentions:
        return [], []
    vectors = TfidfVectorizer(ngram_range=(1, 2), strip_accents="unicode").fit_transform([item.text for item in mentions])
    similarities = cosine_similarity(vectors)
    unique = []
    for index in range(len(mentions)):
        if not any(similarities[index, other] >= 0.88 and label(mentions[index].score) == label(mentions[other].score) for other in unique):
            unique.append(index)
    selected = []
    remaining = list(unique)
    while remaining and len(selected) < limit:
        best = max(remaining, key=lambda index: 0.7 * (0.5 + 0.5 * abs(mentions[index].score)) - 0.3 * max((similarities[index, other] for other in selected), default=0))
        selected.append(best)
        remaining.remove(best)
    return [mentions[index] for index in unique], [mentions[index] for index in selected]


def write_review(results: list[dict]) -> str:
    groups = {}
    for item in results:
        groups.setdefault(item["verdict"], []).append(item["aspect"])

    def join_aspects(names):
        if len(names) == 1:
            return names[0]
        return ", ".join(names[:-1]) + " and " + names[-1]

    sentences = []
    for verdict, wording in (
        ("Mostly Positive", "Feedback on {aspects} is mostly positive, making these the better-received elements in the available opinions."),
        ("Mostly Negative", "Feedback on {aspects} is mostly negative, pointing to weaknesses in the viewing experience."),
        ("Mixed", "Opinions on {aspects} are divided, so these elements may work better for some viewers than others."),
        ("Neutral", "Comments on {aspects} are largely neutral, without a strong positive or negative reaction."),
    ):
        if verdict in groups:
            sentences.append(wording.format(aspects=join_aspects(groups[verdict])))
    if not sentences:
        sentences.append("There is not enough spoiler-safe opinion to write a reliable review of the viewing experience.")
    gated = list(groups.get("Spoiler-Gated", []))
    if "ending" in gated:
        sentences.append("The ending is intentionally left unreviewed to avoid spoilers.")
        gated.remove("ending")
    if gated:
        sentences.append("Spoiler-sensitive opinions about " + join_aspects(gated) + " have been withheld.")
    if any(item["safe_mentions"] == 1 for item in results):
        sentences.append("Some aspect judgments rely on just one retained opinion, so treat them as preliminary.")
    return " ".join(sentences)


def safe_overview(overview: object) -> str:
    if not isinstance(overview, str):
        return ""
    overview = normalize(overview).strip()
    if not overview:
        return ""
    selected = []
    prior_event_risk = False
    for sentence in SEGMENTER.tokenize(overview):
        risk_text = re.sub(r"\bdream[- ]sharing\b", "dreamsharing", sentence, flags=re.I)
        risk_text = re.sub(r"\bthe land of the dead\b", "the afterlife", risk_text, flags=re.I)
        event_risk = bool(EVENTS.search(risk_text))
        risk = spoiler_risk(risk_text, []) or (prior_event_risk and bool(NEGATORS.search(sentence)))
        prior_event_risk = event_risk
        if risk:
            continue
        selected.append(sentence)
        if len(selected) >= 3 or sum(map(len, selected)) >= 700:
            break
    return " ".join(selected)[:800]


def analyze_reception(reviews: object, overview: object = None, title: str = "", entities=None, gate_ending=True) -> dict:
    reviews = validate_reviews(reviews)
    reader_reviews = reviews
    reader_title = title or infer_review_title(reviews)
    if title and len(TOKEN.findall(title)) >= 2:
        title = re.sub(r"\s+\([^)]*\)$", "", normalize(title)).strip()
        pattern = re.compile(r"(?<!\w)" + re.escape(title) + r"(?!\w)", re.I)
        reviews = [dict(review, text=pattern.sub("this production", review["text"])) for review in reviews]
    result = analyze(reviews, entities, gate_ending)
    result["reader_findings"] = reader_evidence(reader_reviews, entities or [])
    result["reader_title"] = reader_title
    premise = safe_overview(overview)
    observations = Counter()
    seen = set()
    for review in reviews:
        if review.get("confidence", 1) == 0:
            continue
        prior_risk = False
        for sentence in SEGMENTER.tokenize(review["text"]):
            risk = spoiler_risk(sentence, []) or (prior_risk and bool(NEGATORS.search(sentence)))
            prior_risk = risk
            key = sentence.casefold().strip()
            if risk or PATTERNS["ending"].search(sentence) or key in seen or re.search(r"\b(?:box office|grossed|million|billion|award|awards|nominations)\b", sentence, re.I):
                continue
            seen.add(key)
            observations[label(SENTIMENT.polarity_scores(sentence)["compound"])] += 1
    total = sum(observations.values())
    tone = "insufficient"
    if total:
        subjective = observations["positive"] + observations["negative"]
        tone = next((name for name in ("positive", "negative") if subjective and observations[name] / subjective >= 0.65), "mixed" if subjective else "neutral")
    result["overview"] = premise
    result["overall"] = {"tone": tone, "safe_opinion_sentences": total}
    result["editorial_evidence"] = editorial_evidence(reviews)
    return enforce_reader_output(format_reception_review(result), reader_reviews)


def format_reception_review(result: dict) -> dict:
    tone = result["overall"]["tone"]
    openings = {
        "positive": "The overall impression is positive, with more to appreciate than to fault.",
        "negative": "This is a harder recommendation: its weaknesses leave a stronger impression than its strengths.",
        "mixed": "The appeal will depend on your taste, with worthwhile qualities alongside noticeable reservations.",
        "neutral": "The response is measured rather than enthusiastic, making this a more tentative recommendation.",
        "insufficient": "There is not enough spoiler-safe opinion to offer a dependable recommendation yet.",
    }
    phrasing = {
        "acting": ("The performances emerge as a strength.", "The performances draw more criticism than praise.", "The performances receive a divided response."),
        "cinematography": ("Visually, the production makes a strong impression.", "The visual presentation is less well received.", "The visual presentation attracts both praise and criticism."),
        "writing": ("The writing comes across as one of its strengths.", "The writing is a weaker element in the available opinions.", "The writing works for some critics but leaves others less convinced."),
        "plot": ("The storytelling is generally well received.", "The storytelling draws criticism rather than consistent enthusiasm.", "The storytelling is divisive rather than universally appealing."),
        "pacing": ("The pacing receives a favorable response.", "The pacing is a sticking point, with criticism outweighing praise.", "The rhythm is a point of disagreement and may depend on your patience for the material."),
        "characters": ("The characters draw a favorable response.", "The characters are less well received.", "Opinions about the characters are split."),
    }
    by_aspect = {item["aspect"]: item for item in result["aspects"]}
    strengths = [aspect for aspect in phrasing if by_aspect[aspect]["verdict"] == "Mostly Positive"]
    weaknesses = [aspect for aspect in phrasing if by_aspect[aspect]["verdict"] == "Mostly Negative"]
    audience = {
        "acting": "strong performances", "cinematography": "striking visuals",
        "writing": "well-received writing", "plot": "engaging storytelling",
        "pacing": "a well-judged rhythm", "characters": "well-received characters",
    }
    verdict_sentences = []
    if strengths:
        preferences = [audience[aspect] for aspect in strengths[:2]]
        verdict_sentences.append("Worth considering if you value " + " and ".join(preferences) + (" and can accept reservations about the " + " and ".join(weaknesses[:2]) if weaknesses else "") + ".")
    elif weaknesses:
        verdict_sentences.append("Approach with caution if " + " and ".join(weaknesses[:2]) + " matter most to you.")
    elif tone in {"positive", "mixed"}:
        verdict_sentences.append("The overall response alone is not enough to promise a good fit; consider the aspect findings above before deciding.")
    else:
        verdict_sentences.append("There is not enough clear aspect-specific support for a firm recommendation.")
    closing = []
    if by_aspect["ending"]["gated_mentions"]:
        closing.append("The ending is deliberately left out to preserve the experience.")
    supported = sum(item["safe_mentions"] > 0 for item in result["aspects"])
    if supported < 3:
        closing.append("The source provides limited aspect-specific evidence; unmentioned elements are left unrated rather than guessed.")
    if any(item["safe_mentions"] == 1 for item in result["aspects"]):
        closing.append("Some aspect findings rest on a single retained passage and should be treated as preliminary.")
    section_specs = (
        ("Acting", ("acting",)),
        ("Story and Writing", ("plot", "writing")),
        ("Pacing", ("pacing",)),
        ("Visuals and Cinematography", ("cinematography",)),
        ("Characters", ("characters",)),
    )
    sections = [{"heading": "Overall Impression", "text": openings[tone]}]
    for heading, aspects in section_specs:
        sentences = []
        for aspect in aspects:
            item = by_aspect[aspect]
            verdict = item["verdict"]
            descriptions = [finding["description"] for finding in result.get("editorial_evidence", []) if finding["aspect"] == aspect]
            if descriptions:
                sentences.extend(descriptions[:2])
                if verdict == "Mixed":
                    sentences.append("Not every retained opinion agrees, so this is a point on which tastes may differ.")
                continue
            if verdict in ("Mostly Positive", "Mostly Negative", "Mixed"):
                sentences.append(phrasing[aspect][("Mostly Positive", "Mostly Negative", "Mixed").index(verdict)])
        if sentences:
            sections.append({"heading": heading, "text": " ".join(sentences)})
    if by_aspect["ending"]["gated_mentions"]:
        verdict_sentences.append("The ending is deliberately left out to preserve the experience.")
    sections.append({"heading": "Verdict", "text": " ".join(verdict_sentences)})
    result["review_notes"] = closing
    result["content_guidance"] = {"verified": False, "text": "Age ratings and content advisories are not verified by these review sources."}
    result["quality"] = {"status": "supported" if supported >= 3 and result["overall"]["safe_opinion_sentences"] >= 5 else "limited", "supported_aspects": supported, "specific_observations": len(result.get("editorial_evidence", []))}
    result["review_format_version"] = 4
    result["review_sections"] = sections
    result["review"] = "\n\n".join(section["heading"] + "\n" + section["text"] for section in sections)
    result["overall"].update(strengths=strengths, reservations=weaknesses)
    return add_reader_review(result)


READER_SIGNALS = (
    ("exceptional", "overall", r"\b(?:groundbreaking masterpiece|masterpiece|exceptional television|outstanding series)\b", "", 0.94),
    ("lead", "acting", r"\b(?:career[- ]defining|legendary|outstanding|brilliant|extraordinary)\s+(?:lead\s+)?performance\b", "A commanding lead performance gives the drama a powerful emotional center.", 0.94),
    ("supporting", "supporting_acting", r"\b(?i:played\s+(?:wonderfully|brilliantly|beautifully|superbly|convincingly)\s+by)\s+(?P<performer>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", "The supporting performances add to the emotional appeal.", 0.8),
    ("emotional", "tone", r"\bemotionally\s+(?:heavy|intense|powerful|affecting|resonant)\b", "The emotional intensity gives the experience a serious, heartfelt tone.", None),
    ("commercial_drama", "genre", r"\bcommercial\s+drama\b", "commercial drama", None),
    ("neo_noir", "genre", r"\bneo[- ]noir\s+thriller\b", "neo-noir thriller", None),
    ("stylized", "style", r"\b(?:highly|boldly|distinctively)\s+styli[sz]ed\b", "The stylized approach gives the presentation a distinctive character, making the filmmaking feel as deliberate as the mystery itself.", None),
    ("intricate_plot", "plot", r"\b(?:intricate|complex)\s*,?\s*(?:high[- ]stakes\s+)?(?:plot|narrative|storytelling|domino effect)\b|\b(?:brilliance|ingenuity)\s+of\s+the\s+(?:plot|storytelling)\b", "The storytelling is intricate rather than straightforward, rewarding viewers who enjoy following connections and paying close attention.", None),
    ("plot_craft", "plot", r"\b(?:brilliance|ingenuity)\s+of\s+the\s+(?:plot|storytelling)\b", "", 0.86),
    ("suspense", "atmosphere", r"\b(?:narrative tension|sustained suspense|high[- ]stakes suspense)\b", "The tension is built into the narrative's structure, giving the experience a tightly wound, high-pressure feel.", None),
    ("thriller", "genre", r"\b(?:rural|gritty|gripping|taut|tense|suspenseful)\s+thriller\b|\bthriller[- ]driven\b", "thriller", None),
    ("rural", "setting", r"\brural\s+(?:thriller|drama|setting|backdrop)\b", "The rural backdrop gives the story a rooted, intimate atmosphere rather than an anonymous setting.", None),
    ("family", "relationships", r"\b(?:heartwarming|heartfelt|touching|moving|tender)\s+(?:father[- ]daughter|mother[- ]daughter|father[- ]son|mother[- ]son|family)\s+(?:bond|relationship)\b", "The warmth of the family relationship gives the story a personal emotional foundation.", 0.8),
    ("gripping", "overall", r"\bgripping\s+(?:(?:commercial|family|rural|psychological|neo[- ]noir|crime|mystery)\s+)?(?:drama|thriller|film|story|narrative)\b", "", 0.82),
    ("unpredictable", "writing", r"\b(?:subverts expectations|avoids predictable tropes|defies convention)\b", "A willingness to move beyond familiar commercial formulas gives the storytelling an unpredictable edge.", 0.72),
    ("social", "theme", r"\b(?:powerful|thought[- ]provoking|meaningful|effective|resonant)\s+social\s+(?:message|commentary)\b", "A socially conscious edge gives the material a purpose beyond its immediate dramatic pull.", 0.76),
    ("acting", "acting", r"\b(?:excellent|superb|wonderful|strong|magnetic|compelling)\s+(?:acting|performances?|cast)\b|\b(?:acting|performances?|cast)\s+(?:is|are|was|were)\s+(?:excellent|superb|wonderful|strong|magnetic)\b", "Strong performances bring conviction and emotional weight to the material.", 0.82),
    ("weak_acting", "acting", r"\b(?:wooden|stiff|unconvincing|terrible|awful)\s+(?:acting|performances?|cast)\b|\b(?:acting|performances?|cast)\s+(?:is|are|feels?)\s+(?:wooden|stiff|unconvincing|terrible|awful)\b", "The performances lack conviction, making the emotional stakes harder to invest in.", -0.82),
    ("precise_pacing", "pacing", r"\b(?:meticulous|precise|expert|carefully controlled|well[- ]judged)\s+pacing\b", "Meticulous pacing gives the drama room to develop while keeping its tension carefully controlled.", 0.86),
    ("slow_burn", "pacing", r"\b(?:slow[- ]burn|measured pacing|deliberate pacing)\b", "The measured, slow-burn rhythm rewards patience rather than promising constant action.", None),
    ("dragging", "pacing", r"\b(?:pacing\s+(?:is|feels?)\s+(?:terrible|slow|sluggish|awful)|(?:sluggish|dragging|uneven|rushed)\s+pacing|pacing\s+drags)\b", "The pacing is less assured, with stretches that weaken the momentum and test your patience.", -0.76),
    ("tension", "atmosphere", r"\b(?:devastating|unforgettable|unrelenting|sustained|masterful|gripping|intense)\s+tension\b", "An intense atmosphere keeps the experience gripping and emotionally charged.", 0.83),
    ("precision", "writing", r"\b(?:narrative precision|razor[- ]sharp writing|meticulous storytelling|precise storytelling|brilliant writing|sharp writing)\b", "The storytelling has a remarkable precision, balancing dramatic intensity with a clear sense of purpose.", 0.88),
    ("weak_writing", "writing", r"\b(?:weak|clumsy|contrived|cliched)\s+(?:writing|script|screenplay)\b|\b(?:writing|script|screenplay)\s+(?:is|feels?)\s+(?:weak|clumsy|contrived|cliched)\b", "The writing is less persuasive, with contrivances that undercut the drama.", -0.76),
    ("morality", "theme", r"\b(?:human (?:corruption|morality)|moral (?:compromise|complexity|ambiguity)|morality and ambition)\b", "Its exploration of morality and human complexity adds a searching psychological dimension beneath the suspense.", None),
    ("tragedy", "theme", r"\b(?:true tragedy|visual tragedy|tragic humanity|irreversible consequences)\b", "A tragic undercurrent gives each choice a sense of weight, leaving an impression that is both unsettling and emotionally resonant.", None),
)


def infer_review_title(reviews):
    text = reviews[0]["text"].strip()
    match = re.match(r"\*{1,3}([^*\n]{1,100})\*{1,3}\s+is\b", text)
    if match and not spoiler_risk(match[1], []):
        return match[1].strip()
    match = re.match(r"(?:(?:[A-Z][\w'-]*\s*){1,3}['\u2019]s\s+)?([A-Z][\w :'!?,-]{0,79}?)\s+\((?:18|19|20|21)\d{2}\)", text)
    if match and not spoiler_risk(match[1], []):
        return match[1].strip()
    return ""


def reader_evidence(reviews, entities):
    findings = {}
    seen = set()
    for review in reviews:
        weight = review.get("confidence", 1)
        key = review["text"].casefold().strip()
        if weight == 0 or key in seen:
            continue
        seen.add(key)
        for identifier, aspect, pattern, description, value in READER_SIGNALS:
            for match in re.finditer(pattern, review["text"], 0 if identifier == "supporting" else re.I):
                prefix = review["text"][max(0, match.start() - 45):match.start()]
                if re.search(r"\b(?:not|never|hardly|isn't|aren't|wasn't|no|without)\b[^.!?;]*$", prefix, re.I):
                    continue
                if identifier == "lead":
                    performer = re.search(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){1,2})['\u2019]s\s+$", prefix)
                    credited = re.match(r"\s+(?:by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", review["text"][match.end():])
                    name = performer[1] if performer else credited[1] if credited else ""
                    if name and not any(entity.casefold() in name.casefold() for entity in entities):
                        quality = match[0].split()[0].lower()
                        restrained = re.search(r"\b(?:restrained|subtle|understated)(?:\s*,\s*|\s+and\s+)$", prefix, re.I)
                        if restrained:
                            description = name + " brings restraint and conviction to the performance, giving the emotional moments weight without relying on broad gestures."
                        else:
                            description = name + "'s " + quality + " lead performance gives the drama a powerful emotional center."
                elif identifier == "supporting":
                    name = match["performer"]
                    if not any(entity.casefold() in name.casefold() for entity in entities):
                        description = name + " also earns praise, adding another strong performance to the ensemble."
                elif identifier == "family":
                    relationship = re.search(r"(?:father[- ]daughter|mother[- ]daughter|father[- ]son|mother[- ]son|family)", match[0], re.I)[0].lower()
                    description = "The warmth of the " + relationship + " relationship supplies a personal anchor, grounding the larger drama in affection and connection."
                item = findings.setdefault(identifier, {"id": identifier, "aspect": aspect, "description": description, "value": value, "weight": 0})
                item["weight"] += weight
                break
    return list(findings.values())


def add_reader_review(result):
    findings = result.get("reader_findings", [])
    by_id = {item["id"]: item for item in findings}
    title = result.get("reader_title") or result.get("movie", {}).get("title") or "This production"
    if title.islower():
        title = title[:1].upper() + title[1:]
    scored = [item for item in findings if item["value"] is not None]
    covered = {item["aspect"] for item in scored}
    for aspect in result.get("aspects", []):
        if aspect["aspect"] == "ending" or aspect["aspect"] in covered or not aspect["safe_mentions"]:
            continue
        parts = aspect["weighted_distribution"]
        subjective = parts.get("positive", 0) + parts.get("negative", 0)
        if subjective:
            scored.append({"value": 0.75 * (parts.get("positive", 0) - parts.get("negative", 0)) / subjective, "weight": 1})
    weight = sum(item["weight"] for item in scored)
    value = sum(item["value"] * item["weight"] for item in scored) / weight if weight else None
    result["overall_score"] = round(min(10, max(0, 5 + 5 * value)), 1) if value is not None else None
    result["score_basis"] = "Sentiment-based estimate from the supplied opinions, not a verified critic rating."
    contextual_opening = value is not None and value >= 0.35 and "commercial_drama" in by_id
    if "neo_noir" in by_id and value is not None and value >= 0.35:
        opening = title + " is a gripping neo-noir thriller, with a strong sense of style and an absorbing emphasis on mystery."
    elif contextual_opening:
        opening = title + (" is an emotionally weighty commercial drama" if "emotional" in by_id else " is a gripping commercial drama" if "gripping" in by_id else " is a well-received commercial drama")
        if "family" in by_id and "thriller" in by_id:
            opening += ", pairing the warmth of a family story with the intensity of a thriller."
        elif "thriller" in by_id:
            opening += ", with a tense atmosphere that adds an edge to its emotional appeal."
        else:
            opening += "."
    elif "exceptional" in by_id and value is not None and value > 0.5:
        opening = title + " is an exceptional work of screen storytelling, distinguished by its dramatic ambition and absorbing intensity."
    elif value is not None and value >= 0.35:
        opening = title + " makes a strong impression, with its best qualities giving the experience a clear sense of character and purpose."
    elif value is not None and value <= -0.35:
        opening = title + " struggles to turn its ideas into a consistently convincing viewing experience."
    elif value is not None:
        opening = title + " offers an uneven experience, with worthwhile qualities offset by noticeable limitations."
    else:
        opening = "The supplied text does not contain enough clear evaluation for a dependable review or overall score."
    sentences = [opening]
    used_aspects = set()
    combined = {"precision", "precise_pacing", "tension"} if {"precision", "precise_pacing", "tension"} <= by_id.keys() else set()
    for identifier in ("lead", "supporting", "weak_acting", "acting", "family", "emotional", "morality", "stylized", "intricate_plot", "precision", "unpredictable", "weak_writing", "precise_pacing", "dragging", "slow_burn", "tension", "suspense", "rural", "social", "tragedy"):
        item = by_id.get(identifier)
        if not item or (identifier == "acting" and "lead" in by_id):
            continue
        if identifier == "emotional" and contextual_opening:
            continue
        if identifier in combined:
            if identifier == "precision":
                sentences.append("Precise storytelling and meticulous pacing work together to build sustained tension, keeping the experience gripping while allowing its emotional stakes to register.")
                used_aspects.update({"writing", "pacing", "atmosphere"})
            continue
        sentences.append(item["description"])
        used_aspects.add(item["aspect"])
    for item in result.get("editorial_evidence", []):
        if item["aspect"] not in used_aspects:
            sentences.append(item["description"])
            used_aspects.add(item["aspect"])
    fallback = {
        "acting": ("The performances bring conviction and emotional weight to the material.", "The performances struggle to make the material convincing."),
        "writing": ("The writing gives the material a clear dramatic focus.", "The writing is a weaker link, making the drama less persuasive."),
        "plot": ("The storytelling holds your attention and gives the experience a satisfying sense of direction.", "The storytelling lacks the cohesion needed to sustain interest."),
        "pacing": ("The pacing maintains an engaging rhythm.", "Reservations about the pacing make this a less consistent watch."),
        "cinematography": ("The visual presentation adds distinction to the experience.", "The visual presentation makes less of an impression."),
        "characters": ("The characterization gives you a reason to stay emotionally invested.", "Thin characterization limits the emotional connection."),
    }
    for item in result.get("aspects", []):
        aspect = item["aspect"]
        if aspect not in fallback or aspect in used_aspects:
            continue
        if item["verdict"] in {"Mostly Positive", "Mostly Negative"}:
            sentences.append(fallback[aspect][item["verdict"] == "Mostly Negative"])
        elif item["verdict"] == "Mixed":
            sentences.append("The " + ("performances" if aspect == "acting" else aspect) + " receive a mixed response, making this part of the experience more dependent on personal taste.")
    if value is not None and len(sentences) > 2:
        if value >= 0.6:
            preferences = []
            for identifier, preference in (("morality", "moral complexity"), ("precision", "precise storytelling"), ("tension", "sustained tension"), ("lead", "performance-led drama"), ("family", "heartfelt family emotion"), ("intricate_plot", "intricate mysteries"), ("stylized", "a distinctive screen style"), ("slow_burn", "a gradual build")):
                if identifier in by_id:
                    preferences.append(preference)
            if len(preferences) >= 2:
                listing = ", ".join(preferences[:2]) + " and " + preferences[2] if len(preferences) > 2 else " and ".join(preferences)
                sentences.append("A compelling choice for viewers drawn to " + listing + ".")
        elif value <= -0.35:
            sentences.append("Those weaknesses make it difficult to recommend without significant reservations.")
    result["reader_review"] = " ".join(sentences)
    return enforce_reader_output(result)


def enforce_reader_output(report, source_reviews=(), approved_phrases=(), allow_vague_references=False):
    title = report.get("reader_title") or report.get("movie", {}).get("title") or ""
    extra_events = re.compile(r"\b(?:assassinat\w*|final showdown|blood[- ]soaked|final words|culprit|perpetrator|revenge|retaliation|syndicate)\b", re.I)

    def unsafe(text):
        if not isinstance(text, str):
            return True
        screened = normalize(text)
        if title and screened.casefold().startswith(title.casefold()):
            screened = screened[len(title):]
        screened = re.sub(r"\bspoiler[- ](?:safe|free)\b", "", screened, flags=re.I)
        screened = GENRE_CUES.sub("", screened)
        if allow_vague_references:
            # "The final reveal surprised me" names no event; "reveals that X ..." still fails.
            screened = re.sub(r"\b(?:the|a|an|its|this|that)\s+(?:[\w-]+\s+){0,2}(?:twists?|reveal|revelation)\b(?!\s+(?:that|of|is|was)\b)", "", screened, flags=re.I)
        return bool(EVENTS.search(screened) or extra_events.search(screened))

    text = report.get("reader_review", "")
    blocked = not isinstance(text, str) or not 20 <= len(text) <= 6000 or unsafe(text)
    if not blocked and source_reviews:
        tokens = [word.casefold() for word in TOKEN.findall(text)]
        output_spans = {tuple(tokens[index:index + 10]) for index in range(len(tokens) - 9)}
        approved_words = [word.casefold() for word in TOKEN.findall(" ".join(approved_phrases))]
        output_spans.difference_update(tuple(approved_words[index:index + 10]) for index in range(len(approved_words) - 9))
        for review in source_reviews:
            original = review.get("text", "") if isinstance(review, dict) else review
            source_tokens = [word.casefold() for word in TOKEN.findall(normalize(original))]
            if any(tuple(source_tokens[index:index + 10]) in output_spans for index in range(len(source_tokens) - 9)):
                blocked = True
                break
    if blocked:
        text = "A checked spoiler-free review is unavailable for this report. Refresh the source or submit a different set of opinions."
        report["reader_review"] = text
        report["overall_score"] = None
    sections = report.get("review_sections", [])
    legacy_unsafe = unsafe(report.get("review", "")) or not isinstance(sections, list) or any(not isinstance(section, dict) or unsafe(section.get("text")) for section in sections)
    if blocked or legacy_unsafe:
        report["review"] = text
        report["review_sections"] = []
    if report.get("overview") and unsafe(report["overview"]):
        report["overview"] = ""
    report["reader_output"] = {"version": 1, "checked": True, "blocked": blocked}
    return report


def analyze_reader_review(reviews, entities=None, gate_ending=True, title=""):
    from source_writer import write_source_review

    if not isinstance(title, str) or len(title) > 120:
        raise ValueError("Title must be a string of at most 120 characters.")
    reviews = validate_reviews(reviews)
    report = analyze(reviews, entities=entities, gate_ending=gate_ending)
    return write_source_review(report, reviews, entities or [], title.strip())


def analyze(reviews: object, entities: object = None, gate_ending: bool = True) -> dict:
    reviews = validate_reviews(reviews)
    if entities is None:
        entities = []
    if not isinstance(entities, list) or len(entities) > 100 or any(not isinstance(entity, str) or not entity.strip() or len(entity) > 100 for entity in entities):
        raise ValueError("Entities must be a list of up to 100 nonempty names, each at most 100 characters.")
    if not isinstance(gate_ending, bool):
        raise ValueError("gate_ending must be true or false.")
    entities = [normalize(entity).strip() for entity in entities]
    buckets = {aspect: [] for aspect in ASPECTS}
    gated = Counter()
    total_sentences = 0
    risky_sentences = 0
    for review_index, review in enumerate(reviews, 1):
        prior_risk = False
        for sentence in SEGMENTER.tokenize(review["text"]):
            total_sentences += 1
            if total_sentences > MAX_SENTENCES:
                raise ValueError(f"A collection must not exceed {MAX_SENTENCES} sentences.")
            risk = spoiler_risk(sentence, entities) or (prior_risk and bool(NEGATORS.search(sentence)))
            prior_risk = risk
            risky_sentences += int(risk)
            sentence_aspects = [aspect for aspect, pattern in PATTERNS.items() if pattern.search(sentence)]
            for aspect in sentence_aspects:
                if risk or (gate_ending and aspect == "ending"):
                    gated[aspect] += 1
            if risk:
                continue
            per_sentence = {}
            clauses = []
            for part in SPLIT.split(sentence):
                sides = re.split(r"\s+and\s+", part, flags=re.I)
                has_aspects = [any(pattern.search(side) for pattern in PATTERNS.values()) for side in sides]
                if len(sides) > 1 and all(has_aspects) and all(any(word.lower() in SENTIMENT.lexicon for word in TOKEN.findall(side)) for side in sides):
                    clauses.extend(sides)
                else:
                    clauses.append(part)
            for clause in clauses:
                matches = sorted((match.start(), match.end(), aspect) for aspect, pattern in PATTERNS.items() for match in pattern.finditer(clause))
                for target in matches:
                    aspect = target[2]
                    if gate_ending and aspect == "ending":
                        continue
                    per_sentence.setdefault(aspect, []).append(local_score(clause, matches, target))
            for aspect, scores in per_sentence.items():
                confidence = review.get("confidence", 1.0)
                rating_weight = 0.75 + 0.5 * abs(review["rating"] - 5) / 5 if "rating" in review else 1.0
                weight = confidence * rating_weight
                if weight > 0:
                    buckets[aspect].append(Mention(aspect, sentence, review_index, sum(scores) / len(scores), weight))
    results = []
    duplicate_count = 0
    for aspect in ASPECTS:
        unique, representatives = select_diverse(buckets[aspect])
        duplicate_count += len(buckets[aspect]) - len(unique)
        counts = Counter(label(mention.score) for mention in unique)
        weights = Counter()
        for mention in unique:
            weights[label(mention.score)] += mention.weight
        total_weight = sum(weights.values())
        if not unique:
            verdict = "Spoiler-Gated" if gated[aspect] else "Not Enough Evidence"
        else:
            verdict = opinion_verdict(weights)
        results.append({
            "aspect": aspect, "verdict": verdict, "safe_mentions": len(unique),
            "gated_mentions": gated[aspect],
            "distribution": {sentiment: counts[sentiment] for sentiment in ("positive", "neutral", "negative")},
            "weighted_distribution": {sentiment: round(weights[sentiment] / total_weight, 4) if total_weight else 0 for sentiment in ("positive", "neutral", "negative")},
            "evidence": [{"review": mention.review, "sentiment": label(mention.score)} for mention in representatives],
        })
    return {"review": write_review(results), "aspects": results, "stats": {"reviews": len(reviews), "sentences": total_sentences, "risky_sentences": risky_sentences, "duplicates_removed": duplicate_count},
            "notice": "English-only heuristic analysis. Spoiler detection and sentiment can be wrong. No review quotations or plot details are returned. Ratings are weak weights, not sentiment labels; confidence is user-supplied, not a calibrated probability."}