"""Semantic plot-event safety net (rules miss these phrasings)."""

import pytest

import semantic
from pipeline import analyze_reader_review

pytestmark = pytest.mark.skipif(not semantic.available(), reason="semantic model not installed")

OPEN = "The cinematography is gorgeous and the lead performance is superb. "


@pytest.mark.parametrize("spoiler, forbidden", [
    ("The hero's journey concludes six feet under.", ["six feet under"]),
    ("By the credits, the lighthouse keeper is the only one left breathing.", ["lighthouse keeper"]),
    ("Her brother was pulling the strings from day one.", ["pulling the strings"]),
    ("The boy grows up to become the very monster he feared.", ["monster he feared"]),
    ("Both lovers end up in separate graves.", ["graves"]),
    ("The bank job goes wrong and the gang turns on each other.", ["turns on each other"]),
    ("The old man never wakes from his surgery.", ["surgery"]),
    ("The quiet neighbour was the arsonist.", ["arsonist"]),
    ("Jonah takes the fall for his father's crimes and goes to jail.", ["jail"]),
    ("The mother walks out on the family for good.", ["walks out"]),
])
def test_semantic_layer_catches_unlisted_spoilers(spoiler, forbidden):
    report = analyze_reader_review([OPEN + spoiler])
    review = report["review"].lower()
    assert "gorgeous" in review
    for term in forbidden:
        assert term not in review
    assert report["spoiler_detection"]["semantic"] is True


@pytest.mark.parametrize("text", [
    "A moving, heartfelt story about grief and family, anchored by a superb lead.",
    "The villain is magnetic and wonderfully hammy, and the score is thunderous.",
    "A retired boxer trains a stubborn teenager in this warm, funny, beautifully shot drama.",
    "The pacing drags in the middle, but the final act is exhilarating and the cast is terrific.",
    "This is a war film about loss, brutal and heartfelt, with a lead performance that deserves awards.",
])
def test_semantic_layer_leaves_opinions_and_premise_alone(text):
    assert analyze_reader_review([text])["review"] == text


def test_plot_scores_above_opinion():
    plot, opinion = semantic.plot_margins(["The president is assassinated at the parade.", "The production design is immaculate."])
    assert plot > 0 > opinion


def test_rules_only_mode_still_works(monkeypatch):
    monkeypatch.setenv("CLEARCUT_SEMANTIC", "0")
    report = analyze_reader_review([OPEN + "The detective dies at the end."])
    assert "dies" not in report["review"]
    assert report["spoiler_detection"]["semantic"] is False
