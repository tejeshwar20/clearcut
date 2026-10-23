"""Semantic plot-event detector: a safety net for spoilers the keyword rules do not know.

Each sentence is embedded with a small sentence-transformer (all-MiniLM-L6-v2 via ONNX, ~90 MB,
no GPU/API key) and compared with example plot-event sentences and example opinion sentences.
A sentence whose meaning is clearly closer to plot events than to opinions is reported as a likely spoiler.

If fastembed or the model is unavailable, or CLEARCUT_SEMANTIC=0, every function degrades to
"no semantic signal" and the rule-based pipeline runs unchanged.
"""

import logging
import os
import threading

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 3
# Calibrated on the regression reviews: opinion sentences score <= -0.03, plot sentences the
# keyword rules miss score +0.02 .. +0.27. Sentences that carry the reviewer's opinion need a
# much stronger plot signal before they are withheld.
PLAIN_THRESHOLD = float(os.environ.get("CLEARCUT_SEMANTIC_THRESHOLD", "0.0"))
OPINION_THRESHOLD = float(os.environ.get("CLEARCUT_SEMANTIC_OPINION_THRESHOLD", "0.12"))

# Sentences that state what happens in a story: deaths, reveals, twists, outcomes, endings.
PLOT_EXAMPLES = [
    "The main character dies at the end.",
    "It turns out the friend was the killer all along.",
    "She discovers her father is the villain.",
    "The hero sacrifices himself to save the city.",
    "They get married in the final scene.",
    "The detective is revealed to be the murderer.",
    "He was a ghost the whole time.",
    "The family escapes but the mother is left behind.",
    "The king is betrayed by his own son.",
    "The ship sinks and only two people survive.",
    "In the end he goes to prison for the crime.",
    "The twins swap identities to fool the police.",
    "The dog is killed by the neighbour.",
    "She wins the competition but loses her best friend.",
    "The whole story was a dream inside a coma.",
    "The mentor is secretly working for the enemy.",
    "The boy finally confronts his abusive stepfather and leaves home.",
    "The rebels storm the palace and the queen is overthrown.",
    "His wife leaves him and takes the children to another city.",
    "The scientist's experiment goes wrong and wipes out the town.",
    "The two friends fall out and never speak again.",
    "The girl turns out to have been adopted.",
    "The soldier comes home blind after the war.",
    "The hostage negotiator is the one who planned the kidnapping.",
    "The robot shuts itself down to protect the humans.",
    "She burns the letters and leaves the village forever.",
    "The old man's will leaves everything to the housekeeper.",
    "The brothers inherit the farm and sell it to the developers.",
    "The cult leader is arrested and the followers disperse.",
    "The bride runs away from the wedding with the best man.",
    "The heist fails and the whole crew is caught.",
    "The patient was never sick; the doctor was poisoning her.",
    "The killer escapes and is never caught.",
    "The baby is switched at birth with another child.",
    "The town was underwater all along.",
    "The pilot crashes the plane on purpose.",
    "The general is assassinated during the parade.",
    "The kids find their missing father living under a new name.",
    "Only the youngest sister survives the fire.",
    "The ghost is the girl's late mother protecting her.",
]

# Set-up sentences: who the characters are and what the story starts with. These are allowed.
PREMISE_EXAMPLES = [
    "A retired cop is pulled back for one last case.",
    "Two sisters return to their childhood home after their mother's funeral.",
    "A young farmer takes a vow at his daughter's request.",
    "The story follows a struggling family that cons its way into jobs with a rich household.",
    "A marshal arrives at an island hospital to investigate a missing patient.",
    "A cable operator protects his family when a police officer's son goes missing.",
    "After an alien attack wipes out half of life, the surviving heroes regroup.",
    "A rebellious villager clashes with a forest officer over land rights.",
    "An insomniac office worker meets a charismatic soap salesman.",
    "A child psychologist tries to help a frightened boy who claims he sees ghosts.",
    "When his wife disappears on their anniversary, suspicion falls on the husband.",
    "A group of climbers attempts a dangerous winter ascent.",
    "Set in 1920s Paris, the film follows a jazz singer trying to make it big.",
    "A widowed father raises his daughter alone in a small town.",
    "A rookie detective is partnered with a burned-out veteran.",
    "Five astronauts are sent to investigate a signal from a distant planet.",
    "A chef opens a restaurant in the city and faces a fierce rival.",
    "The film follows a boy and his dog on a road trip across the country.",
    "A thief is hired to steal a priceless manuscript from a library.",
    "An orphan is sent to a strict boarding school run by a cold headmistress.",
]

# Sentences that judge the film without saying what happens in it.
OPINION_EXAMPLES = [
    "The cinematography is gorgeous.",
    "The acting is superb and the score is haunting.",
    "The pacing drags in the middle.",
    "The dialogue feels clunky and forced.",
    "I loved every minute of it.",
    "The visual effects are stunning.",
    "It is a tense and gripping thriller.",
    "The script is clever and funny.",
    "The ending felt rushed and unearned.",
    "The performances are uniformly strong.",
    "A beautifully shot, slow-burn drama.",
    "The soundtrack is lovely and the sets are lavish.",
    "I would recommend it to anyone who likes mysteries.",
    "The twist is clever but predictable.",
    "The chemistry between the leads is electric.",
    "The editing is sharp and the tone is consistent.",
    "A moving, heartfelt story about grief and family.",
    "The villain is magnetic and wonderfully hammy.",
    "The hero is a charming, flawed everyman.",
    "It is a war film about loss, brutal and impeccably shot.",
    "The world building is rich and immersive.",
    "The comedy lands and the cast is hilarious.",
    "The first act is slow but the payoff is worth it.",
    "The production design and costumes are immaculate.",
    "It is too long and the subplots go nowhere.",
    "The direction is confident and the camera work is fluid.",
    "The lead gives a career-best performance.",
    "The film explores themes of guilt and forgiveness.",
    "It is a faithful adaptation that fans will enjoy.",
    "The sound design delivers genuine scares.",
    "Go in blind; I will not spoil anything.",
    "The story is about a family surviving a harsh winter.",
    "The murder mystery setup is clever and fun.",
    "This horror film scared me to death.",
    "The action choreography is breathtaking.",
    "The CGI looks cheap and the plot is predictable.",
    "The relationship between the sisters feels authentic.",
    "A must-watch for fans of the genre.",
    "The final act is a bit rushed.",
    "The emotional beats land hard.",
]

_lock = threading.Lock()
_state = {"loaded": False, "model": None, "plot": None, "premise": None, "opinion": None}
logger = logging.getLogger(__name__)


def enabled():
    return os.environ.get("CLEARCUT_SEMANTIC", "1") != "0"


def _normalize(vectors):
    import numpy as np

    vectors = np.asarray(vectors, dtype="float32")
    return vectors / np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9, None)


def _load():
    if _state["loaded"]:
        return _state["model"]
    with _lock:
        if _state["loaded"]:
            return _state["model"]
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(MODEL_NAME, cache_dir=os.environ.get("CLEARCUT_MODEL_CACHE") or None)
            _state["plot"] = _normalize(list(model.embed(PLOT_EXAMPLES)))
            _state["premise"] = _normalize(list(model.embed(PREMISE_EXAMPLES)))
            _state["opinion"] = _normalize(list(model.embed(OPINION_EXAMPLES)))
            _state["model"] = model
            logger.info("Semantic spoiler model loaded: %s", MODEL_NAME)
        except Exception as error:  # missing package, no network on first download, etc.
            logger.warning("Semantic spoiler model unavailable, using rules only: %s", error)
            _state["model"] = None
        _state["loaded"] = True
    return _state["model"]


def available():
    return enabled() and _load() is not None


def plot_margins(sentences):
    """Return, per sentence, closeness to plot outcomes minus the closer of premise or opinion.

    Positive means the sentence reads like something that happens later in the story rather than
    a set-up or a judgement. Returns None for every sentence when the model is not available.
    """
    sentences = list(sentences)
    if not sentences or not enabled():
        return [None] * len(sentences)
    model = _load()
    if model is None:
        return [None] * len(sentences)
    import numpy as np

    vectors = _normalize(list(model.embed(sentences)))
    def closeness(examples):
        return np.sort(vectors @ examples.T, axis=1)[:, -TOP_K:].mean(axis=1)

    plot = closeness(_state["plot"])
    other = np.maximum(closeness(_state["premise"]), closeness(_state["opinion"]))
    return [float(value) for value in plot - other]


def is_plot_event(margin, opinionated):
    if margin is None:
        return False
    return margin > (OPINION_THRESHOLD if opinionated else PLAIN_THRESHOLD)
