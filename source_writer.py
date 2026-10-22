"""Source-grounded opinion extraction using grammatical dependency structure."""

import logging
import os
import re
from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from pipeline import EVENTS, GENRE_CUES, SENTIMENT, TOKEN, enforce_reader_output, infer_review_title, normalize


FEATURES = {
    "acting", "performance", "cast", "portrayal", "ensemble", "chemistry",
    "pacing", "pace", "rhythm", "editing", "edit", "cinematography",
    "visual", "visuals", "photography", "lighting", "animation", "imagery",
    "writing", "script", "screenplay", "dialogue", "storytelling", "narrative",
    "plot", "story", "characterization", "characterisation", "character",
    "music", "score", "sound", "soundtrack", "design", "costume", "set",
    "direction", "filmmaking", "choreography", "action", "humour", "humor",
    "comedy", "atmosphere", "tension", "suspense", "tone", "theme", "bond",
    "relationship", "message", "commentary", "precision", "craft", "wit",
    "setting", "depth", "complexity", "scale", "scope", "ambition", "core",
}
GENRES = {
    "film", "movie", "series", "drama", "thriller", "comedy", "romance",
    "horror", "epic", "western", "documentary", "masterpiece", "achievement",
    "spectacle", "adventure", "satire", "tragedy", "study",
}
DESCRIPTIVE_VERBS = {"be", "feel", "seem", "look", "sound", "remain", "have", "offer", "deliver"}
MODIFIERS = {"det", "amod", "advmod", "neg", "compound", "cc", "conj", "punct", "npadvmod", "quantmod"}
DISCLOSURES = re.compile(
    r"\b(?:finale|climax|ending|showdown|assassinat\w*|syndicate|revenge|"
    r"retaliation|culprit|perpetrator|blood[- ]soaked|shot|"
    r"final words|voice message|real identity)\b", re.I,
)
# Twist/ending language: any sentence containing it is withheld entirely.
REVEALS = re.compile(
    r"\b(?:reveal\w*|revelation|twists?|turns? out|is actually|was actually|true nature|"
    r"real identity|betray\w*|climax\w*|finale|final act|third act|ending|culminat\w*|"
    r"unmask\w*|unravel\w*|uncover\w*|discover\w*|finds? out|learns? that|"
    r"ends? (?:with|on|in|when|as)|ended (?:with|on|in)|final moments|final shot|last shot|epilogue|post-credits?)\b", re.I,
)
OUTCOMES = re.compile(
    r"\b(?:execution|executes|execute (?:him|her|them|his|her)|executed by|dismantl\w*|destroys?|destroyed|"
    r"triumphs? over|avenge[sd]?|avenging|snipers?|shatter(?:s|ed|ing)? (?:his|her|their)|"
    r"pass(?:es|ed|ing)? away|perish\w*|drown\w*|stabs?|stabb\w*|shoots|shooting (?:him|her|them)\w*|"
    r"poison\w*|strangl\w*|behead\w*|bloodbath|massacre\w*|lobotom\w*|inherit\w*|vanish\w*|"
    r"gives? (?:his|her|their) life|bur(?:y|ies|ied) (?:the|his|her|their)|"
    r"grief|griev\w*|mourn\w*|kidnap\w*|abduct\w*|hostage|corpse|funeral|"
    r"(?:shift\w*|evolution|evolv\w*|transform\w*|devolv\w*|descent)\b[^.;]{0,60}?\b(?:into|to)|"
    r"(?:turns?|turned|turning)(?:\s+\w+){0,2}\s+into|"
    r"(?:dark|shocking|sharp|sudden|unexpected|tragic|violent|brutal)\s*,?\s*(?:\w+\s+)?turn)\b", re.I,
)
HINTS = {"initially", "ostensibly", "seemingly", "supposedly"}
CLAUSE_UNITS = {"advcl", "relcl", "conj", "parataxis", "appos", "prep", "acl", "npadvmod", "dative"}
REVIEW_SENTIMENT = SentimentIntensityAnalyzer()
REVIEW_SENTIMENT.lexicon.update(SENTIMENT.lexicon)
REVIEW_SENTIMENT.lexicon.update({
    "meticulous": 1.8, "precision": 1.6, "restrained": 1.2,
    "career-defining": 3.0, "hypnotic": 1.5, "sumptuous": 2.2,
    "heartwarming": 2.5, "mischievous": 1.0, "overbearing": -1.8,
    "jagged": -0.8, "disorienting": -1.0,
    "career-best": 3.0, "sleek": 1.5, "spectacular": 2.5, "blistering": 1.8,
    "thunderous": 1.2, "venomous": 0.8, "chilling": 1.0, "haunting": 1.5,
    "magnetic": 2.0, "clunky": -1.5, "cardboard": -1.2, "villain": 0, "villains": 0,
})


@lru_cache(maxsize=1)
def language_model():
    import spacy

    try:
        return spacy.load("en_core_web_sm", disable=["ner"])
    except OSError as error:
        raise ValueError("The English review parser is not installed. Install the project requirements before starting the app.") from error


def phrase_tokens(root):
    selected = {root.i: root}

    def collect(token):
        for child in token.children:
            if child.dep_ not in MODIFIERS or child.dep_ == "punct" and child.text not in {",", "-"}:
                continue
            if child.pos_ in {"VERB", "AUX"} and child.dep_ not in {"amod", "conj"}:
                continue
            if child.dep_ == "conj" and any(part.dep_ in {"nsubj", "dobj", "ccomp", "relcl"} for part in child.children):
                continue
            if root.pos_ in {"NOUN", "PROPN"} and child.dep_ in {"conj", "cc"} and child.head == root:
                continue
            selected[child.i] = child
            collect(child)

    collect(root)
    return sorted(selected.values(), key=lambda token: token.i)


def wording(tokens):
    text = " ".join(token.text for token in tokens)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text.strip(" ,.;:-")


def safe_phrase(tokens, allow_names=False):
    text = wording(tokens)
    if not text or len(tokens) > 24 or EVENTS.search(text) or DISCLOSURES.search(text):
        return ""
    if not allow_names and any(token.pos_ in {"PROPN", "PRON"} for token in tokens):
        return ""
    return text


def inferred_title(doc):
    for sentence in doc.sents:
        for token in sentence:
            complements = [child for child in token.head.children if child.dep_ == "attr"]
            if token.dep_ == "nsubj" and token.head.lemma_ == "be" and any(child.lemma_ in GENRES for child in complements) and token.pos_ in {"PROPN", "NOUN"} and token.lemma_.lower() not in FEATURES | {"film", "movie", "series", "show", "it"}:
                parts = [part for part in phrase_tokens(token) if part.pos_ in {"PROPN", "NOUN", "NUM"}]
                title = wording(parts)
                if 0 < len(title) <= 100 and len(parts) <= 8 and not EVENTS.search(title):
                    return title[:1].upper() + title[1:]
        break
    return ""


def cue_spans(text, entities):
    exempt = [match.span() for match in GENRE_CUES.finditer(text)]
    patterns = [(REVEALS, True), (EVENTS, False), (DISCLOSURES, False), (OUTCOMES, False)]
    patterns += [(re.compile(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", re.I), False) for entity in entities]
    spans = []
    for pattern, severe in patterns:
        for match in pattern.finditer(text):
            if any(start <= match.start() < end for start, end in exempt):
                continue
            if match[0].lower() == "shot" and re.search(r"(?:ly|well)\s+$", text[:match.start()], re.I):
                continue
            spans.append((match.start(), match.end(), severe))
    return spans


def clause_unit(token):
    while token.dep_ != "ROOT":
        if token.dep_ in CLAUSE_UNITS and not (token.dep_ == "acl" and token.left_edge.lower_ == "that"):
            return token
        token = token.head
    return None


def tidy(text):
    text = re.sub(r"\(\s*\)|\[\s*\]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    text = re.sub(r"([,;:\u2014-])(?:\s*[,;:\u2014-])+", r"\1", text)
    text = re.sub(r"[\s,;:\u2014-]+([.!?])", r"\1", text)
    text = text.strip(" ,;:\u2014-")
    if text and text[-1] not in ".!?\"'":
        text += "."
    return text[:1].upper() + text[1:]


def salvage_opening(sentence, entities):
    """Keep an evaluative opening participle ("Driven by ...,") from a withheld sentence."""
    root = sentence.root
    subjects = [child for child in root.children if child.dep_ in {"nsubj", "nsubjpass"} and child.i < root.i]
    if sentence[0].tag_ not in {"VBN", "VBG"} or not subjects:
        return ""
    subject = max(subjects, key=lambda token: token.i)
    opening = sentence.doc[sentence.start:subject.left_edge.i]
    text = opening.text.strip().rstrip(",;:\u2014- ")
    if not text or cue_spans(text, entities):
        return ""
    if REVIEW_SENTIMENT.polarity_scores(text)["compound"] == 0 and not any(token.lemma_.lower() in FEATURES for token in opening):
        return ""
    noun = subject.lemma_.lower() if subject.lemma_.lower() in {"film", "movie", "series", "show", "story", "narrative", "plot", "drama", "thriller"} else "film"
    return tidy("The " + noun + " is " + text[:1].lower() + text[1:])


def redact_sentence(sentence, entities):
    """Return the sentence without spoiler clauses, or "" when it cannot be kept."""
    removed = set()
    for start, end, severe in cue_spans(sentence.text, entities):
        span = sentence.char_span(start, end, alignment_mode="expand")
        if span is None:
            continue
        if severe:
            return ""
        for token in span:
            unit = clause_unit(token)
            if unit is None:
                return ""
            # A coordinated verb sharing the main subject is part of the same plot event.
            if unit.dep_ == "conj" and unit.head == sentence.root and unit.pos_ in {"VERB", "AUX"} and not any(child.dep_ in {"nsubj", "nsubjpass"} for child in unit.children):
                return ""
            removed.update(part.i for part in unit.subtree)
    changed = True
    while changed:
        changed = False
        for token in sentence:
            content = [child for child in token.children if not child.is_punct]
            if token.i not in removed and token.pos_ in {"VERB", "ADP"} and content and all(child.i in removed for child in content):
                unit = clause_unit(token)
                if unit is None:
                    return ""
                removed.update(part.i for part in unit.subtree)
                changed = True
            if token.i not in removed and token.dep_ in {"cc", "preconj"} and not any(
                sibling.dep_ == "conj" and sibling.i > token.i and sibling.i not in removed for sibling in token.head.children
            ):
                removed.add(token.i)
                changed = True
    root = sentence.root
    if root.i in removed or any(child.i in removed for child in root.children if child.dep_ in {"nsubj", "nsubjpass"}):
        return ""
    # A first-person reaction stripped of its cause reads incomplete; let rephrase_spoiler restore a vague cause.
    if removed and root.lemma_.lower() in REACTIONS and any(child.lower_ in {"i", "we"} for child in root.children if child.dep_ in {"nsubj", "nsubjpass"}):
        return ""
    parts = []
    for token in sentence:
        if token.i in removed or (token.lower_ in HINTS and token.dep_ == "advmod"):
            continue
        text = token.text
        if token.lemma_ == "masquerade":
            text = "unfolds" if token.tag_ == "VBZ" else "unfold"
        parts.append(text + token.whitespace_)
    text = tidy("".join(parts))
    return text if len(TOKEN.findall(text)) >= 3 else ""


FRAME_NOUNS = {
    "card", "turn", "moment", "scene", "sequence", "act", "climax", "finale", "ending",
    "conclusion", "twist", "reveal", "revelation", "surprise", "payoff", "resolution",
}
INTENSITY = {
    "brutal", "cold", "shocking", "devastating", "crushing", "gut-wrenching", "heartbreaking",
    "stunning", "haunting", "bold", "audacious", "bleak", "dark", "savage", "emotional",
    "predictable", "lazy", "contrived", "unexpected", "surprising", "satisfying", "chilling",
    "harrowing", "tragic", "poignant", "wild", "jaw-dropping", "cathartic", "rushed", "abrupt",
}
REACTIONS = {
    "believe", "expect", "stun", "shock", "surprise", "floor", "blindside", "love", "hate",
    "gasp", "cry", "predict", "guess", "anticipate", "enjoy", "adore", "dislike", "see",
}
WEAK_ADVERBS = {"most", "more", "very", "so", "too", "all"}


def moment_phrase(sentence):
    text = sentence.text.lower()
    if "climax" in text:
        return "the climax"
    if "finale" in text:
        return "the finale"
    if re.search(r"\b(?:final|third|last) act\b", text):
        return "the final act"
    if re.search(r"\bending\b|\bends? (?:with|on|in|when|as)\b|\bended (?:with|on|in)\b|\b(?:final|last) (?:scene|moments?|shot|frame)\b", text):
        return "the ending"
    if re.search(r"\b(?:twist|reveal\w*|revelation|turns? out|is actually|was actually|all along|real identity|true nature|unmask\w*|discover\w*|uncover\w*|finds? out|learns? that)\b", text):
        return "the final surprise" if re.search(r"\b(?:final|last|ultimate)\b", text) else "the big surprise"
    return "a pivotal turn in the story"


def join_words(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def appraisal_word(token):
    if not (token.lower_ in INTENSITY or REVIEW_SENTIMENT.lexicon.get(token.lower_, 0)):
        return ""
    adverbs = [child for child in token.children if child.dep_ == "advmod" and child.lower_ not in WEAK_ADVERBS and child.i < token.i]
    return " ".join(part.text for part in adverbs + [token])


def rephrase_spoiler(sentence, entities):
    """Vague, non-revealing version of a spoiler sentence keeping the reviewer's own reaction or adjectives."""
    moment = moment_phrase(sentence)
    root = sentence.root
    subjects = [child for child in root.children if child.dep_ in {"nsubj", "nsubjpass"}]
    if root.lemma_.lower() in REACTIONS and subjects and subjects[0].lower_ in {"i", "we"}:
        head = [token for token in sentence if token == root or (token.head == root and token.dep_ in {"nsubj", "nsubjpass", "aux", "auxpass", "neg"})]
        reaction = "".join(token.text_with_ws for token in head).strip()
        return tidy(reaction + (" by " if root.tag_ == "VBN" else " ") + moment), True
    predicates = [child for child in root.children if child.dep_ in {"acomp", "oprd"}]
    predicates += [conj for predicate in predicates for conj in predicate.conjuncts]
    words = [word for word in (appraisal_word(token) for token in sorted(set(predicates), key=lambda token: token.i)) if word]
    if words and root.lemma_ == "be":
        return tidy(moment + " is " + join_words(words)), True
    for token in sentence:
        if token.lemma_.lower() in {"climax", "finale", "ending", "conclusion"}:
            phrase = [part for part in phrase_tokens(token) if part.dep_ not in {"conj", "cc"}]
            described = [word for word in (appraisal_word(part) for part in phrase if part.dep_ == "amod") if word]
            text = wording(phrase)
            if described and not any(part.pos_ in {"PROPN", "PRON"} and part.dep_ != "poss" for part in phrase) and not cue_spans(re.sub(r"\b(?:climax|finale|ending)\b", "", text), entities):
                text = re.sub(r"^(?:this|that|its|his|her|their)\b", "a", text, flags=re.I)
                if not re.match(r"(?:a|an|the)\b", text, re.I):
                    text = ("an " if text[:1].lower() in "aeiou" else "a ") + text
                return tidy("The story builds to " + text), True
    words = []
    for token in sentence:
        if token.dep_ == "amod" and token.head.lemma_.lower() in FRAME_NOUNS:
            word = appraisal_word(token)
            if word and word not in words:
                words.append(word)
    if words:
        if moment.startswith("a pivotal"):
            return tidy("The story takes a " + join_words(words) + " turn"), True
        if "surprise" in moment:
            return tidy(moment + " is " + join_words(words)), True
        return tidy(moment + " takes a " + join_words(words) + " turn"), True
    neutral = {
        "the climax": "The climax brings the story's conflicts to a head",
        "the finale": "The finale brings the story's conflicts to a head",
        "the final act": "The final act takes the story in a new direction",
        "the ending": "The ending brings the story to a decisive close",
    }
    return tidy(neutral.get(moment, "The story has a surprise in store" if "surprise" in moment else "The story takes a significant turn")), False


def extract_opinions(reviews, entities):
    model = language_model()
    findings = []
    seen = set()
    titles = []
    passages = []
    current = [None]

    def retain(subject, description, text, review_index, confidence, names=()):
        text = re.sub(r"\s+", " ", text).strip().rstrip(".,;:") + "."
        if EVENTS.search(text) or DISCLOSURES.search(text) or any(re.search(r"(?<!\w)" + re.escape(entity) + r"(?!\w)", text, re.I) for entity in entities):
            return
        key = text.casefold()
        if key in seen or not 3 <= len(TOKEN.findall(text)) <= 45:
            return
        seen.add(key)
        score_text = description if description else text
        if subject == "overall":
            genre_pattern = r"\b(?:" + "|".join(sorted(GENRES - {"masterpiece", "achievement"})) + r")\b"
            score_text = re.sub(genre_pattern, "", score_text, flags=re.I)
        score = REVIEW_SENTIMENT.polarity_scores(score_text)["compound"]
        if subject in {"setting", "tone", "tension", "suspense", "core"}:
            score = 0
        findings.append({"subject": subject, "description": description, "text": text, "score": score, "weight": confidence, "review": review_index, "names": list(names), "sentence": current[0]})

    texts = [re.sub(r"[*_`]", "", clean_markup(review["text"])) for review in reviews]
    for review_index, (review, doc) in enumerate(zip(reviews, model.pipe(texts, batch_size=8)), 1):
        confidence = review.get("confidence", 1)
        if confidence == 0:
            continue
        titles.append(inferred_title(doc))
        for sentence in doc.sents:
            current[0] = (review_index, sentence.start)
            kept = redact_sentence(sentence, entities)
            rephrased = ("", False) if kept else rephrase_spoiler(sentence, entities)
            passages.append({"key": current[0], "source": sentence.text, "text": kept or salvage_opening(sentence, entities), "withheld": not kept, "rephrased": rephrased[0], "evaluative": rephrased[1]})
            for token in sentence:
                lemma = token.lemma_.lower()
                if lemma in FEATURES:
                    subject = safe_phrase(phrase_tokens(token))
                    verb = token.head
                    if token.dep_ == "nsubj" and verb.lemma_ in DESCRIPTIVE_VERBS and subject:
                        complements = [child for child in verb.children if child.dep_ in {"acomp", "attr", "dobj", "oprd"}]
                        for complement in complements:
                            description = safe_phrase(phrase_tokens(complement))
                            if not description:
                                continue
                            if not any(part.pos_ in {"ADJ", "ADV"} for part in phrase_tokens(complement)) and complement.lemma_ not in {"wit", "precision", "craft"}:
                                continue
                            negative = any(child.dep_ == "neg" for child in verb.children)
                            description = ("not " if negative else "") + description
                            connector = "has" if verb.lemma_ == "have" else "feels" if verb.lemma_ == "feel" else "is" if verb.lemma_ == "be" else verb.text.lower()
                            if token.tag_ == "NNS" and connector == "is":
                                connector = "are"
                            if token.tag_ == "NNS" and connector == "has":
                                connector = "have"
                            retain(lemma, description, subject[:1].upper() + subject[1:] + " " + connector + " " + description, review_index, confidence)
                    modifiers = [part for part in token.children if part.dep_ in {"amod", "advmod", "compound"} and (part.pos_ in {"ADJ", "ADV", "VERB"} or REVIEW_SENTIMENT.lexicon.get(part.lower_, 0) != 0)]
                    evaluated_modifiers = [part for part in modifiers if abs(REVIEW_SENTIMENT.polarity_scores(wording(phrase_tokens(part)))["compound"]) >= 0.05]
                    if evaluated_modifiers:
                        modifiers = evaluated_modifiers
                    if modifiers and subject:
                        if token.dep_ == "nsubj" and verb.lemma_ in DESCRIPTIVE_VERBS:
                            continue
                        if any(part.lemma_ in {"final", "last", "first"} for part in modifiers):
                            continue
                        negated = any(part.lower_ in {"no", "not", "never", "without"} for part in phrase_tokens(token)) or any(child.dep_ == "neg" for child in token.head.children)
                        if not negated:
                            adjective_parts = {part.i: part for modifier in modifiers for part in phrase_tokens(modifier)}
                            if adjective_parts:
                                first, last = min(adjective_parts), max(adjective_parts)
                                for part in sentence:
                                    if first < part.i < last and part.text == ",":
                                        adjective_parts[part.i] = part
                            description = safe_phrase(sorted(adjective_parts.values(), key=lambda part: part.i))
                            subject_parts = [part for part in phrase_tokens(token) if part.i not in adjective_parts and part.pos_ != "DET" and (not part.is_punct or part.text == "-")]
                            feature = safe_phrase(subject_parts)
                            if feature and description:
                                retain(lemma, description, "The " + feature + (" are " if token.tag_ == "NNS" else " is ") + description, review_index, confidence)
                    if token.dep_ == "nsubj" and token.head.lemma_ not in DESCRIPTIVE_VERBS:
                        for preposition in token.head.children:
                            if preposition.dep_ == "prep" and preposition.lemma_ in {"on", "with"}:
                                for complement in preposition.children:
                                    details = safe_phrase(phrase_tokens(complement))
                                    if details and complement.lemma_ in FEATURES | {"effect", "structure", "construction"} and any(part.pos_ == "ADJ" for part in phrase_tokens(complement)):
                                        retain(lemma, details, "The " + token.text + " " + token.head.text + " " + preposition.text + " " + details, review_index, confidence)
                if token.dep_ == "attr" and lemma in GENRES and token.head.lemma_ == "be":
                    description = safe_phrase(phrase_tokens(token))
                    if description:
                        if any(child.dep_ == "neg" for child in token.head.children):
                            description = "not " + description
                        retain("overall", description, "This is " + description, review_index, confidence)
                if lemma in {"performance", "portrayal"}:
                    description = safe_phrase([part for part in phrase_tokens(token) if part.i != token.i and part.pos_ != "DET"])
                    for owner in token.children:
                        if owner.dep_ == "poss":
                            names = [part for part in phrase_tokens(owner) if part.pos_ == "PROPN"]
                            name = safe_phrase(names, allow_names=True)
                            if name and description:
                                retain("performance", description, name + " gives a " + description + " performance", review_index, confidence, names=[name])
                    for preposition in token.children:
                        if preposition.dep_ != "prep" or preposition.lemma_ not in {"by", "from"}:
                            continue
                        for actor in preposition.children:
                            names = [part for part in phrase_tokens(actor) if part.pos_ == "PROPN"]
                            name = safe_phrase(names, allow_names=True)
                            if name and description:
                                retain("performance", description, name + " gives a " + description + " performance", review_index, confidence, names=[name])
                if token.lemma_ == "play" and token.pos_ == "VERB":
                    praise = [child for child in token.children if child.dep_ == "advmod"]
                    for preposition in token.children:
                        if preposition.dep_ not in {"agent", "prep"} or preposition.lemma_ != "by":
                            continue
                        for actor in preposition.children:
                            name = safe_phrase([part for part in phrase_tokens(actor) if part.pos_ == "PROPN"], allow_names=True)
                            appraisal = safe_phrase(praise)
                            if name and appraisal:
                                retain("performance", appraisal, name + " plays the part " + appraisal, review_index, confidence, names=[name])
                if token.lemma_ in {"brilliance", "ingenuity"}:
                    for preposition in token.children:
                        for feature in preposition.children:
                            if preposition.lemma_ == "of" and feature.lemma_ in FEATURES:
                                retain(feature.lemma_, token.text, "The " + feature.text + " shows " + token.text, review_index, confidence)
    return findings, next((title for title in titles if title), ""), passages


def clean_markup(text):
    text = re.sub(r"\[([^\]]+)\]\((?:[^()\s]|\([^()\s]*\))*\)", r"\1", normalize(text))
    return re.sub(r"https?://\S+", "", text)


def write_source_review(report, reviews, entities, title):
    findings, detected_title, passages = extract_opinions(reviews, entities)
    selected = []
    for item in findings:
        if item["subject"] == "performance" and not item["names"] and any(other["subject"] == "performance" and other["names"] for other in findings):
            continue
        if not any(item["text"].casefold() == previous["text"].casefold() for previous in selected):
            selected.append(item)
    paragraphs = []
    groups = {}
    seen = set()
    original_kept = False
    previous_rephrased = False
    for passage in passages:
        candidates = [passage["text"]] if passage["text"] else []
        original_kept |= bool(candidates)
        if passage["withheld"]:
            # Rewrite rather than delete, but avoid stacking content-free vague sentences.
            if passage["rephrased"] and (passage["evaluative"] or not (candidates or previous_rephrased)):
                candidates.append(passage["rephrased"])
            if not passage["text"]:
                candidates += [item["text"] for item in selected if item["sentence"] == passage["key"]]
        previous_rephrased = passage["withheld"]
        for text in candidates:
            if text.casefold() not in seen and sum(len(part) for part in paragraphs) + len(text) < 5500:
                seen.add(text.casefold())
                paragraphs.append(text)
                groups.setdefault(passage["key"][0], []).append(text)
    if not original_kept and not any(passage["evaluative"] for passage in passages):
        paragraphs, groups = [], {}
    cleaned = [{**review, "text": re.sub(r"\*{4,}", "***", clean_markup(review["text"]))} for review in reviews]
    title = title or infer_review_title(cleaned) or detected_title
    if title.islower():
        title = title[:1].upper() + title[1:]
    review = "\n\n".join(" ".join(group) for group in groups.values()) if paragraphs else "The text contains no independently supported, spoiler-safe opinions to turn into a review."
    subjective = [item for item in selected if abs(item["score"]) >= 0.05]
    weight = sum(item["weight"] for item in subjective)
    value = sum(item["score"] * item["weight"] for item in subjective) / weight if weight else None
    if value is None and paragraphs:
        genre_pattern = r"\b(?:" + "|".join(sorted(GENRES - {"masterpiece", "achievement"})) + r")\b"
        scores = [REVIEW_SENTIMENT.polarity_scores(re.sub(genre_pattern, "", text, flags=re.I)) for text in paragraphs]
        scores = [score["compound"] for score in scores if score["pos"] or score["neg"]]
        value = sum(scores) / len(scores) if scores else None
    report.update(
        reader_title=title, reader_review=review, review=review, review_sections=[],
        overall_score=round(5 + 5 * value, 1) if value is not None else None,
        score_basis="Sentiment-based estimate from retained opinions, not a verified critic rating.",
        writer={"provider": "local", "mode": "source_grounded", "status": "ready" if paragraphs else "insufficient_opinion"},
        opinion_evidence=[{key: item[key] for key in ("subject", "description", "text", "review")} for item in selected],
        overall={"tone": "positive" if value is not None and value > 0.2 else "negative" if value is not None and value < -0.2 else "mixed" if value is not None else "insufficient", "safe_opinion_sentences": len(selected)},
    )
    original = "\n\n".join(re.sub(r"[*_`]", "", review["text"]) for review in cleaned if review.get("confidence", 1) != 0)
    rewritten = model_rewrite(original, passages, entities)
    if rewritten:
        report.update(reader_review=rewritten, review=rewritten, writer={"provider": "openai", "mode": "spoiler_editor", "status": "ready", "model": os.environ.get("CLEARCUT_MODEL", "gpt-4.1-mini")})
        checked = enforce_reader_output(report, allow_vague_references=True)
        if not checked["reader_output"]["blocked"]:
            return checked
        report.update(overall_score=round(5 + 5 * value, 1) if value is not None else None)
    if os.environ.get("CLEARCUT_WRITER") == "openai":
        report["writer"] = {"provider": "local", "mode": "source_grounded", "status": "fallback" if paragraphs else "insufficient_opinion"}
    report.update(reader_review=review, review=review)
    return enforce_reader_output(report, reviews, approved_phrases=paragraphs)


EDITOR_PROMPT = """You are a spoiler-free review editor. Your job is to rewrite a movie/book/show review so it reads naturally and stays useful, without revealing any spoilers.

WHAT COUNTS AS A SPOILER
- Plot twists, reveals, or surprise endings
- Character deaths, betrayals, or major relationship changes
- Who wins, who survives, or how the story resolves
- Anything that happens in the final act or climax
- Specific events that would reduce the viewer's surprise

HOW TO EDIT
1. Keep every sentence that has no spoilers exactly as written.
2. When a sentence contains a spoiler, rephrase it instead of deleting it. Keep the reviewer's opinion and tone, but replace the specific plot detail with a vague, non-revealing description.
   - Spoiler: "I couldn't believe the detective was the killer all along."
   - Rewritten: "The final reveal genuinely caught me off guard."
3. Preserve the reviewer's sentiment (praise, criticism, rating) and writing style.
4. Keep the review fluent and well-structured. It should read as if the reviewer wrote it spoiler-free from the start.
5. Do not add new information, opinions, or plot details that were not in the original.
6. If the whole review is spoiler-free, return it unchanged.

OUTPUT
Return only the rewritten review. No explanations, labels, or notes."""
GENERIC_LEMMAS = {
    "film", "movie", "show", "series", "story", "plot", "act", "scene", "moment", "ending", "climax",
    "finale", "twist", "reveal", "revelation", "surprise", "turn", "character", "viewer", "audience",
    "be", "have", "do", "make", "take", "leave", "get", "go", "come", "lead", "bring", "feel", "catch",
    "guard", "way", "time", "thing", "lot", "end", "final", "half", "direction", "development",
}


def model_rewrite(original, passages, entities):
    """Optional LLM editor; returns None unless configured and the result passes the leak check."""
    if os.environ.get("CLEARCUT_WRITER") != "openai" or not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=30, max_retries=0)
        response = client.chat.completions.create(
            model=os.environ.get("CLEARCUT_MODEL", "gpt-4.1-mini"),
            messages=[{"role": "system", "content": EDITOR_PROMPT}, {"role": "user", "content": original}],
            max_completion_tokens=2000,
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as error:
        logging.getLogger(__name__).warning("Spoiler editor unavailable: %s", type(error).__name__)
        return None
    if not 20 <= len(text) <= 6000 or OUTCOMES.search(text) or any(entity.casefold() in text.casefold() for entity in entities):
        return None
    model = language_model()
    kept = {token.lemma_.lower() for passage in passages if not passage["withheld"] for token in model(passage["source"])}
    spoiler_terms = {
        token.lemma_.lower() for passage in passages if passage["withheld"] for token in model(passage["source"])
        if token.pos_ in {"NOUN", "PROPN", "VERB"} and not token.is_stop and token.lemma_.lower() not in kept | GENERIC_LEMMAS
    }
    if any(token.lemma_.lower() in spoiler_terms for token in model(text) if token.pos_ in {"NOUN", "PROPN", "VERB"}):
        return None
    return text