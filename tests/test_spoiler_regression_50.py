"""Regression set: 36 long reviews with real spoilers and 14 safe reviews with spoiler-looking words."""

import re

import pytest

from pipeline import analyze_reader_review
from tests.spoiler_cases_50 import CASES

# Each case is (text, forbidden, must_keep). Forbidden strings must not appear; opinions must survive.


@pytest.mark.parametrize("text, forbidden, keep", CASES, ids=[f"case{index}" for index in range(1, len(CASES) + 1)])
def test_spoilers_removed_and_opinions_kept(text, forbidden, keep):
    report = analyze_reader_review([text])
    review = report["review"]
    assert report["reader_output"]["blocked"] is False
    lower = review.lower()
    for term in forbidden:
        assert term not in lower
    for term in keep:
        assert term in lower
    # No glued words such as "lovedthe" from clause joins, no doubled spaces.
    assert not re.search(r"\b\w+ed(?:the|a)\b", review)
    assert "  " not in review


@pytest.mark.parametrize("text, forbidden, keep", [case for case in CASES if not case[1]])
def test_safe_reviews_are_unchanged(text, forbidden, keep):
    assert analyze_reader_review([text])["review"] == text
