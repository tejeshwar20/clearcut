"""Harder spoiler patterns: hidden identities, 'all a dream', character fates, kept reactions."""

import pytest

from pipeline import analyze_reader_review


def review(text):
    report = analyze_reader_review([text])
    assert report["reader_output"]["blocked"] is False
    return report["review"]


@pytest.mark.parametrize("text, forbidden", [
    ("Great visuals. It was all a simulation the whole time, which blew my mind.", ["simulation"]),
    ("Brilliant direction. Darth Vader is Luke's father, and that scene still gives me chills.", ["father", "vader"]),
    ("The music is lovely. Jack doesn't make it and freezes in the water while Rose lets go.", ["freezes", "lets go", "make it"]),
    ("I loved it. The hero loses his arm in the last battle and never walks again.", ["arm", "never walks"]),
    ("Gripping thriller. The wife was behind everything from the start.", ["wife", "behind everything"]),
    ("Fun ride. Turns out the mentor was the villain, which I didn't see coming.", ["mentor", "villain"]),
    ("Beautifully shot. The dog doesn't survive, so bring tissues.", ["dog", "survive"]),
    ("The pacing is tight. She wakes up in hospital and realises the whole film was in her head.", ["hospital", "her head", "wakes"]),
    ("Solid cast. Both brothers get shot in the final standoff.", ["shot", "standoff", "brothers"]),
    ("Clever script. The killer is the narrator himself, hiding in plain sight.", ["narrator", "killer", "plain sight"]),
    ("The score is incredible. Spoiler: the aliens were humans from the future.", ["aliens", "humans", "future"]),
    ("Heartfelt drama. Their mother had cancer all along and hid it from them.", ["cancer", "mother"]),
    ("The visual effects are stunning, but I hated that the main character dies at the end.", ["dies", "main character"]),
])
def test_hidden_spoilers_are_removed(text, forbidden):
    output = review(text).lower()
    for term in forbidden:
        assert term not in output


@pytest.mark.parametrize("text, expected", [
    ("Great visuals. It was all a simulation the whole time, which blew my mind.",
     "Great visuals. The big surprise blew my mind."),
    ("Brilliant direction. Darth Vader is Luke's father, and that scene still gives me chills.",
     "Brilliant direction. The big surprise still gives me chills."),
    ("Fun ride. Turns out the mentor was the villain, which I didn't see coming.",
     "Fun ride. I didn't see the big surprise coming."),
    ("Beautifully shot. The dog doesn't survive, so bring tissues.",
     "Beautifully shot. The story takes an emotional turn, so bring tissues."),
])
def test_reviewer_reaction_is_kept_while_spoiler_is_rewritten(text, expected):
    assert review(text) == expected


@pytest.mark.parametrize("text", [
    "Great visuals. Superb sound design.",
    "A tense, gripping war drama with strong performances.",
    "The romance between the leads is sweet and the chemistry is real.",
    "I'd watch it again tomorrow. The dream sequences are gorgeous.",
    "The father-daughter bond is heartwarming and the dialogue is sharp.",
])
def test_non_spoiler_sentences_are_kept_word_for_word(text):
    assert review(text) == text


def test_spoiler_placeholders_are_varied_and_never_repeated():
    text = ("Great acting. Rosebud turns out to be his childhood sled. The music is lovely. "
            "Jack doesn't make it and freezes in the water. The editing is sharp. "
            "The killer is the narrator himself. Wonderful film.")
    output = review(text)
    for kept in ("Great acting.", "The music is lovely.", "The editing is sharp.", "Wonderful film."):
        assert kept in output
    sentences = [part.strip() for part in output.split(".") if part.strip()]
    assert len(sentences) == len(set(sentences))
    assert "significant turn" not in output and "surprise in store" not in output


def test_consecutive_spoilers_become_one_line():
    output = review("Strong performances throughout. Dumbledore is killed by Snape on the tower. Harry escapes with Hagrid. The visuals are stunning.")
    assert output.startswith("Strong performances throughout.") and output.endswith("The visuals are stunning.")
    assert output.count(".") == 3


def test_craft_praise_is_not_moved_onto_the_plot():
    output = review("The visual effects are stunning, but I hated that the main character dies at the end.")
    assert output.startswith("The visual effects are stunning")
    assert "turn in the story is stunning" not in output
