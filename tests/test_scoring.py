import pytest

from pipeline import analyze_reader_review
from scoring import stated_rating


def score(text):
    return analyze_reader_review([{"text": text}])["overall_score"]


@pytest.mark.parametrize("text, expected", [
    ("I'd give it 8/10.", 8.0),
    ("Rating: 7.5 / 10", 7.5),
    ("4 out of 5 stars", 8.0),
    ("3.5 stars", 7.0),
    ("★★★☆☆", 6.0),
    ("No rating given here.", None),
    ("Released in 2023/24 to acclaim", None),
])
def test_stated_rating_parsing(text, expected):
    assert stated_rating(text) == expected


def test_scores_are_ordered_by_reviewer_opinion():
    rave = score("An absolute masterpiece. The performances are stunning and the direction is flawless. Easily the best film of the year.")
    good = score("A solid, enjoyable thriller with good acting. Not perfect, but worth a watch.")
    mixed = score("The visuals are gorgeous, but the script is weak and the pacing drags. Some great moments, some boring ones.")
    bad = score("A boring, clumsy mess. The acting is wooden, the dialogue is awful and I nearly walked out.")
    awful = score("One of the worst films I have ever seen. Painful, incoherent and a complete waste of time.")
    assert rave > good > mixed > bad > awful
    assert rave >= 8 and 6.5 <= good <= 9 and 4 <= mixed <= 6.5 and bad <= 3 and awful <= 2


def test_stated_rating_dominates_text_tone():
    assert 7.5 <= score("I would rate it 8/10. The cast is fine and the music is lovely.") <= 8.5
    assert 4 <= score("2 out of 5 stars. The cinematography is beautiful though.") <= 5.5


def test_dark_subject_matter_is_not_criticism():
    assert score("A dark, violent and brutal crime thriller that is brilliantly acted and gripping from start to finish.") >= 8


def test_contrast_favours_final_verdict():
    assert score("The trailer looked great, but the film itself is dull and lifeless.") < 4.5
    assert score("This is not a good movie. The plot is not interesting at all.") < 4.5
