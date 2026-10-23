import json

import pytest

from pipeline import analyze, analyze_reception


@pytest.mark.parametrize("title", ["An Unseen Film", "Another Unrelated Title", ""])
def test_pasted_writer_preserves_unfamiliar_opinions_without_canned_templates(title):
    from pipeline import analyze_reader_review

    source = (
        "The costume design is sumptuous and tactile. The background score is hypnotic but occasionally overbearing. "
        "The dialogue has a dry, mischievous wit. The editing feels jagged and disorienting. "
        "The heroine secretly betrays her brother and he dies in the final scene."
    )
    report = analyze_reader_review([source], title=title)
    review = report["review"].lower()
    for detail in ("sumptuous", "tactile", "hypnotic", "overbearing", "mischievous", "jagged", "disorienting"):
        assert detail in review
    for forbidden in ("makes a strong impression", "best qualities", "heroine", "brother", "betrays", "dies", "final scene"):
        assert forbidden not in review
    assert report["writer"]["mode"] == "source_grounded"
    assert report["reader_output"]["checked"] is True


BREAKING_BAD_REVIEW = (
    "***Breaking Bad* is a groundbreaking masterpiece in television history that delivers a dark, uncompromising study of human corruption.** "
    "Driven by Bryan Cranston's career-defining performance, the series flawlessly charts Walter White's evolution from a sympathetic, cancer-stricken teacher into a terrifying, ego-driven drug kingpin. "
    "The show's ultimate strength lies in its meticulous pacing and devastating tension, masterfully contrasting Walt's cold, calculating malice with the raw, tragic humanity of Jesse Pinkman. "
    "By treating its narrative as a true tragedy where every moral compromise carries irreversible consequences, the series achieves an unmatched level of narrative precision that keeps the audience captivated and conflicted until its final frame."
)


IRUMUDI_REVIEW = (
    "Shiva Nirvana's Irumudi (2026) is an emotionally heavy, gripping commercial drama that subverts expectations by trading predictable tropes for a devastating, thriller-driven tragic core. "
    "The film successfully centers on a restrained, brilliant performance by Ravi Teja as Trinadh, an alcoholic banana farmer who takes a 41-day Ayyappa Deeksha vow at the request of his daughter, Manikanta (played wonderfully by Baby Nakshathra). "
    "While the first half leans comfortably into their heartwarming father-daughter bond, the narrative takes a shocking, dark turn into a rural thriller involving missing village girls.\n\n"
    "The absolute turning point of the movie is its crushing climax: Manikanta discovers that the highly revered village leader, Guruswamy (Sai Kumar), is actually the dangerous predator behind the crimes. "
    "Before she can alert her father, Guruswamy murders her and dumps her body near a dam. "
    "The investigation culminates in a powerhouse sequence where Trinadh gets his broken phone repaired, listens to his daughter's final voice message exposing the killer, and confronts Guruswamy. "
    "By shifting seamlessly from a soulful family portrait to a gritty revenge thriller fueled by a father's profound grief, Irumudi delivers a powerful social message on women's safety that genuinely sticks with the audience."
)


DETECTIVE_REVIEW = (
    "Mysskin\u2019s Detective (2017)\u2014originally titled Thupparivaalan\u2014is a highly stylized and gripping neo-noir thriller whose narrative tension relies on an intricate, high-stakes domino effect. "
    "The brilliance of the plot lies in how a seemingly minor, innocent request by a schoolboy to find out who shot his pet dog serves as the thread that unravels a multi-layered corporate assassination ring. "
    "The investigation forces the eccentric detective Kaniyan Poongundran (Vishal) to cross paths with a ruthless syndicate led by Devil (Vinay Rai), who stage elaborate hits\u2014such as creating artificial lightning strikes\u2014to make high-profile contract murders look like natural accidents. "
    "The tension breaks in a devastating manner when Devil uncovers Kaniyan's investigation, leading to a brutal retaliation where Kaniyan\u2019s love interest, Mallika, is mercilessly murdered. "
    "The film culminates in a raw, blood-soaked final showdown in a mangrove swamp, where Kaniyan kills Devil, leading to a poetic conclusion where Devil's final words are a remorseful apology to the little boy for killing his dog"
)


def test_reader_review_recovers_detective_style_without_plot_chain():
    from pipeline import analyze_reader_review

    report = analyze_reader_review([DETECTIVE_REVIEW])
    review = report["review"]
    assert "Detective" in review.split(".")[0]
    assert "neo-noir" in review
    assert "stylized" in review
    assert "intricate" in review
    assert "tension" in review
    assert 20 <= len(review.split()) <= 190
    assert report["reader_output"]["checked"] is True
    assert report["reader_output"]["blocked"] is False
    assert review != DETECTIVE_REVIEW
    for forbidden in ("dog", "schoolboy", "assassination", "lightning", "Devil", "Mallika", "swamp", "murders", "kills", "apology", "final words"):
        assert forbidden not in review


def test_output_guard_blocks_source_copy_without_known_spoiler_keywords():
    from pipeline import analyze_reader_review, enforce_reader_output

    original = "A courier quietly forwards a location to an old acquaintance before the council meeting begins."
    report = analyze_reader_review(["The acting is excellent."])
    report["reader_review"] = original
    report["review"] = original
    result = enforce_reader_output(report, [{"text": original}])
    assert result["reader_output"]["blocked"] is True
    assert "overall_score" not in result
    assert original not in json.dumps(result)


def test_output_guard_blocks_disclosures_without_a_source_copy():
    from pipeline import analyze_reader_review, enforce_reader_output

    report = analyze_reader_review(["The acting is excellent."])
    report["reader_review"] = "The central character is actually the culprit behind the entire investigation."
    result = enforce_reader_output(report)
    assert result["reader_output"]["blocked"] is True
    assert "culprit" not in result["reader_review"]


def test_output_guard_allows_event_words_inside_a_film_title():
    from pipeline import analyze_reader_review

    report = analyze_reader_review(["The acting is excellent."], title="Kill Bill")
    assert report["reader_title"] == "Kill Bill"
    assert report["review"] == "The acting is excellent."
    assert report["reader_output"]["blocked"] is False


def test_reader_review_preserves_specifics_from_irumudi_without_climax():
    from pipeline import analyze_reader_review

    report = analyze_reader_review([IRUMUDI_REVIEW], title="Irumudi")
    review = report["review"]
    assert "Irumudi" in review.split(".")[0]
    assert "Ravi Teja" in review
    assert "restrain" in review
    assert "Baby Nakshathra" in review
    assert "father-daughter" in review
    assert "emotion" in review
    assert review.count("emotional") <= 2
    assert "powerful" in review and "social message" in review
    assert 25 <= len(review.split()) <= 190
    assert "overall_score" not in report
    for forbidden in ("Guruswamy", "Sai Kumar", "predator", "killer", "murders", "body", "dam", "phone", "voice message", "revenge", "turning point", "grief", "dark turn into"):
        assert forbidden not in review


def test_reader_review_recognizes_alternative_credits_and_relationships():
    from pipeline import analyze_reader_review

    text = "An emotionally powerful, gripping commercial drama has a subtle and brilliant performance from Ada Stone. It builds a moving mother-son relationship in a rural setting."
    report = analyze_reader_review([text], title="another story")
    assert report["reader_title"] == "Another story"
    assert "Ada Stone" in report["review"]
    assert "subtle" in report["review"] and "brilliant" in report["review"]
    assert "mother-son" in report["review"]
    assert "father-daughter" not in report["review"]
    assert "Irumudi" not in report["review"]
    assert "Ravi Teja" not in report["review"]


def test_reader_review_does_not_name_performers_marked_sensitive():
    from pipeline import analyze_reader_review

    report = analyze_reader_review([IRUMUDI_REVIEW], entities=["Ravi Teja", "Baby Nakshathra"], title="Irumudi")
    assert "Ravi Teja" not in report["review"]
    assert "Baby Nakshathra" not in report["review"]


def test_reader_review_does_not_turn_negated_context_into_praise():
    from pipeline import analyze_reader_review

    report = analyze_reader_review(["This isn't a gripping commercial drama. There is no heartwarming father-daughter bond. It has no powerful social message."])
    assert "isn't a gripping commercial drama" in report["review"]
    assert all("not" in item["description"] for item in report["opinion_evidence"])
    assert "warmth" not in report["review"]
    assert "socially conscious edge" not in report["review"]


def test_reader_review_does_not_expose_a_score():
    from pipeline import analyze_reader_review

    report = analyze_reader_review(["The film is a rural thriller with an emotionally heavy tone."])
    assert "overall_score" not in report and "score_basis" not in report


def test_reader_review_recognizes_sentence_initial_supporting_credit():
    from pipeline import analyze_reader_review

    report = analyze_reader_review(["Played wonderfully by Ada Stone, the character is memorable."])
    assert "Ada Stone" in report["review"]


def test_reader_review_preserves_opinion_inside_spoiler_heavy_paragraph():
    from pipeline import analyze_reader_review

    report = analyze_reader_review([BREAKING_BAD_REVIEW], title="Breaking Bad")
    review = report["review"]
    assert review.startswith("Breaking Bad")
    assert "Bryan Cranston" in review
    assert "pacing" in review
    assert "tension" in review
    assert "career-defining" in review
    assert "meticulous" in review
    assert review.count("tension") <= 2
    assert "without needing to reveal" not in review
    assert 20 <= len(review.split()) <= 190
    for forbidden in ("Walter", "kingpin", "cancer", "evolution", "not enough", "withheld", "Acting\n"):
        assert forbidden not in review


def test_reader_review_can_infer_an_explicit_markdown_title():
    from pipeline import analyze_reader_review

    assert analyze_reader_review([BREAKING_BAD_REVIEW])["review"].startswith("Breaking Bad")


def test_reader_review_preserves_criticism_and_mixed_feedback():
    from pipeline import analyze_reader_review

    negative = analyze_reader_review(["The acting is wooden. The writing is weak. The pacing is terrible."])
    mixed = analyze_reader_review(["The acting is excellent but the pacing is terrible."])
    assert "acting is wooden" in negative["review"]
    assert "writing is weak" in negative["review"]
    assert "the pacing is terrible" in mixed["review"]


def test_source_writer_keeps_coordinated_features_separate():
    from pipeline import analyze_reader_review

    report = analyze_reader_review(["The film has meticulous pacing and devastating tension, but the villain dies in the end."])
    assert report["review"] == "The film has meticulous pacing and devastating tension."


JAILER_REVIEW = (
    "**Nelson Dilipkumar\u2019s *[Jailer](https://www.google.com/search?q=Jailer)***** is a masterfully directed, darkly humorous action-spectacle that subverts the traditional \"mass\" superstar formula.** "
    "The narrative initially masquerades as a typical vigilante revenge thriller, following the mild-mannered, retired prison warden Muthuvel Pandian (Rajinikanth) as he steps out of retirement to wage a bloody war against the unhinged smuggler Varman (Vinayakan) under the impression that Varman murdered his son, Arjun. "
    "Armed with absolute swagger, an electric background score by Anirudh Ravichander, and jaw-dropping cameos, Muthuvel effortlessly dismantles Varman's smuggling network. "
    "However, the film pulls its most brutal card in the final act, revealing that Arjun is a corrupt criminal willing to murder his own father. "
    "This ultimate betrayal leads to a cold, emotionally crushing climax where Muthuvel orders his snipers to execute Arjun."
)


def test_redaction_keeps_original_wording_and_removes_twist():
    from pipeline import analyze_reader_review

    report = analyze_reader_review([JAILER_REVIEW])
    review = report["review"]
    for kept in ("masterfully directed, darkly humorous action-spectacle", "Rajinikanth", "wage a bloody war against the unhinged smuggler Varman", "electric background score by Anirudh Ravichander"):
        assert kept in review
    for forbidden in ("Arjun", "murder", "corrupt", "revealing", "betrayal", "snipers", "execute", "dismantles", "masquerades", "initially", "http", "["):
        assert forbidden not in review
    assert "The final act takes a brutal turn." in review
    assert "cold, emotionally crushing climax" in review
    assert report["reader_title"] == "Jailer"
    assert report["reader_output"]["blocked"] is False


@pytest.mark.parametrize("text,details", [
    ("The lighting is spectral and otherworldly.", ("spectral", "otherworldly")),
    ("The animation feels buoyant but occasionally languid.", ("buoyant", "languid")),
    ("The cinematography is austere, tactile and unhurried.", ("austere", "tactile", "unhurried")),
])
def test_source_writer_preserves_new_descriptive_vocabulary(text, details):
    from pipeline import analyze_reader_review

    report = analyze_reader_review([text])
    assert all(detail in report["review"] for detail in details)
    assert report["reader_output"]["blocked"] is False


def test_reader_review_does_not_reveal_spoiler_only_text():
    from pipeline import analyze_reader_review

    result = analyze_reader_review(["Walter White is a killer. He dies in the final scene."])
    assert "Walter" not in json.dumps(result)
    assert "dies" not in json.dumps(result)


def test_reader_review_ignores_duplicates_and_zero_confidence():
    from pipeline import analyze_reader_review

    positive = "The acting is excellent. The writing is sharp."
    single = analyze_reader_review([positive])
    duplicate = analyze_reader_review([positive, positive, {"text": "The acting is awful.", "confidence": 0}])
    assert single["review"] == duplicate["review"]


def test_reader_review_does_not_promote_negated_praise():
    from pipeline import analyze_reader_review

    result = analyze_reader_review(["The acting is not excellent. This is not a masterpiece."])
    assert "exceptional work" not in result["review"]
    assert "Strong performances" not in result["review"]


@pytest.mark.parametrize("text", [
    "In the end the protagonist returns home.",
    "The plot exposes her real identity.",
    "The final scene makes the characters siblings.",
])
def test_indirect_spoilers_are_withheld(text):
    report = analyze_reception([text])
    assert report["stats"]["risky_sentences"] == 1
    assert text not in json.dumps(report)


def test_reception_recommendation_preserves_reservations():
    report = analyze_reception(["The acting is excellent but the pacing is terrible."])
    assert "strong performances" in report["review"]
    assert "reservations about the pacing" in report["review"]
    assert report["overall"]["strengths"] == ["acting"]
    assert report["overall"]["reservations"] == ["pacing"]


def test_critics_take_has_readable_aspect_sections():
    report = analyze_reception(["The acting is excellent. The story is compelling. The pacing is terrible. The visuals are beautiful."])
    sections = {item["heading"]: item["text"] for item in report["review_sections"]}
    assert "performances emerge as a strength" in sections["Acting"]
    assert "reason to stay invested" in sections["Story and Writing"]
    assert "pacing is a sticking point" in sections["Pacing"]
    assert "striking imagery" in sections["Visuals and Cinematography"]
    assert "reservations about the pacing" in sections["Verdict"]
    assert "Parental Guidance" not in sections
    assert report["content_guidance"]["verified"] is False


def test_critics_take_missing_aspects_are_not_invented():
    report = analyze_reception(["The acting is excellent. The plot reveals that Mira is the killer."])
    sections = {item["heading"]: item["text"] for item in report["review_sections"]}
    assert "Pacing" not in sections
    assert "Story and Writing" not in sections
    assert "Mira" not in json.dumps(report)
    assert "killer" not in json.dumps(report)
    assert "TV-MA" not in report["review"]


def test_saved_report_can_be_reformatted_without_raw_reviews():
    from pipeline import format_reception_review

    report = analyze_reception(["The acting is excellent but the pacing is terrible."])
    original_stats = dict(report["stats"])
    report.pop("review_sections")
    report["review"] = "Old summary"
    formatted = format_reception_review(report)
    assert formatted["stats"] == original_stats
    assert "Acting\n" in formatted["review"]
    assert "Pacing\n" in formatted["review"]


def test_reception_ignores_zero_confidence_and_unrelated_praise():
    report = analyze_reception([{"text": "Excellent acting.", "confidence": 0}, "The box office success was excellent."])
    assert report["overall"]["tone"] == "insufficient"


def test_villain_keyword_does_not_count_as_negative_opinion():
    assert aspects(["The villain is excellent."])["characters"]["verdict"] == "Mostly Positive"


def test_negated_storytelling_misstep_is_praise():
    report = analyze_reception(["The series has never made a seriously damaging storytelling misstep."])
    assert report["overall"]["strengths"] == ["plot"]
    sections = {item["heading"]: item["text"] for item in report["review_sections"]}
    assert "storytelling is generally well received" in sections["Story and Writing"]
    assert "not a consensus" not in sections["Story and Writing"]
    assert any("single retained passage" in note for note in report["review_notes"])
    assert "writing" not in report["overall"]["strengths"]


def test_sentiment_words_in_selected_title_do_not_bias_story_opinion():
    report = analyze_reception(["Breaking Bad is that rare TV series that has never made a seriously damaging storytelling misstep."], title="Breaking Bad")
    assert report["overall"]["strengths"] == ["plot"]
    assert "storytelling is generally well received" in report["review"]


def test_neutral_context_does_not_override_consistent_praise():
    report = analyze_reception(["The acting is excellent. The cast includes several actors. The performances feature the ensemble. The writing is credited to the screenwriter."])
    assert report["overall"]["tone"] == "positive"


def test_neutral_aspect_description_is_not_a_critical_opinion():
    report = analyze_reception(["The acting is excellent. The cast includes several actors."])
    acting = next(item for item in report["aspects"] if item["aspect"] == "acting")
    assert acting["distribution"] == {"positive": 1, "neutral": 1, "negative": 0}
    assert acting["verdict"] == "Mostly Positive"
    assert "divided response" not in report["review"]


def test_review_uses_concrete_safe_observations_without_copying_source():
    source = "The pacing is a slow burn. The characters are complex and conflicted. The acting is nuanced."
    report = analyze_reception([source])
    assert "deliberate slow burn" in report["review"]
    assert "complexity" in report["review"]
    assert "nuance and restraint" in report["review"]
    assert source not in report["review"]
    assert "single retained passage" not in report["review"]
    assert "Parental Guidance" not in report["review"]


def test_unsafe_or_negated_traits_are_not_turned_into_praise():
    report = analyze_reception(["The acting is not nuanced. The plot reveals that Mira is the killer and has complex characters."])
    assert not report["editorial_evidence"]
    assert "nuance and restraint" not in report["review"]
    assert "Mira" not in json.dumps(report)


def aspects(reviews, **kwargs):
    return {item["aspect"]: item for item in analyze(reviews, **kwargs)["aspects"]}


def test_contrast():
    result = aspects(["The acting is excellent but the pacing is terrible."])
    assert result["acting"]["verdict"] == "Mostly Positive"
    assert result["pacing"]["verdict"] == "Mostly Negative"


def test_written_review_includes_strengths_and_weaknesses():
    review = analyze(["The acting is excellent but the pacing is terrible."])["review"]
    assert "acting is mostly positive" in review
    assert "pacing is mostly negative" in review
    assert "preliminary" in review


def test_written_review_handles_mixed_and_neutral():
    review = analyze(["The acting is excellent.", "The acting is terrible.", "The pacing exists."])["review"]
    assert "Opinions on acting are divided" in review
    assert "pacing are largely neutral" in review


def test_written_review_never_copies_plot_text():
    review = analyze(["The plot reveals that Mira is the killer. The ending is excellent."])["review"]
    assert "Mira" not in review
    assert "killer" not in review
    assert "not enough spoiler-safe opinion" in review
    assert "ending is intentionally left unreviewed" in review
    assert "opinions about plot have been withheld" in review


def test_written_review_does_not_invent_missing_aspects():
    review = analyze(["I watched this yesterday."])["review"]
    assert "not enough spoiler-safe opinion" in review
    assert "mostly positive" not in review


def test_written_review_allows_safe_ending_when_ungated():
    review = analyze(["The ending is excellent."], gate_ending=False)["review"]
    assert "ending is mostly positive" in review
    assert "intentionally left unreviewed" not in review


def test_spoiler_never_returned():
    result = analyze(["The plot reveals that Mira is the killer. The acting is excellent."])
    assert "Mira" not in json.dumps(result)
    assert "killer" not in json.dumps(result)
    assert result["stats"]["risky_sentences"] == 1


def test_default_ending_gate():
    assert aspects(["The ending is excellent."])["ending"]["verdict"] == "Spoiler-Gated"


def test_negation():
    assert aspects(["The acting is not good."])["acting"]["verdict"] == "Mostly Negative"


def test_duplicates():
    result = aspects(["The acting is excellent."] * 5)["acting"]
    assert result["safe_mentions"] == 1


@pytest.mark.parametrize("reviews", [None, [], {}, [""], [123], [{"text": "acting", "rating": True}], [{"text": "acting", "rating": float("nan")}], [{"text": "acting", "confidence": -1}]])
def test_bad_input(reviews):
    with pytest.raises(ValueError):
        analyze(reviews)


def test_no_evidence():
    assert aspects(["I watched this yesterday."])["acting"]["verdict"] == "Not Enough Evidence"


def test_entities_and_context():
    result = analyze(["Mira meets Jon in the plot. Their characters are excellent."], entities=["Mira", "Jon"])
    assert result["stats"]["risky_sentences"] == 2


def test_mixed():
    assert aspects(["The acting is excellent.", "The acting is terrible."])["acting"]["verdict"] == "Mixed"


def test_zero_confidence():
    assert aspects([{"text": "The acting is excellent.", "confidence": 0}])["acting"]["verdict"] == "Not Enough Evidence"


@pytest.mark.parametrize("text", ["Excellent acting and terrible pacing.", "The acting was absolutely superb and the pacing is awful.", "The acting is good, the pacing is bad."])
def test_coordinated_aspects(text):
    result = aspects([text])
    assert result["acting"]["verdict"] == "Mostly Positive"
    assert result["pacing"]["verdict"] == "Mostly Negative"


def test_shared_adjective():
    result = aspects(["The acting and writing are excellent."])
    assert result["acting"]["verdict"] == result["writing"]["verdict"] == "Mostly Positive"


def test_unicode_negation():
    assert aspects(["The acting isn\u2019t good."])["acting"]["verdict"] == "Mostly Negative"


@pytest.mark.parametrize("reviews", [["x" * 12001], ["x"] * 301, ["x" * 12000] * 11, ["Acting. " * 1100] * 2])
def test_resource_limits(reviews):
    with pytest.raises(ValueError):
        analyze(reviews)


@pytest.mark.parametrize("entities", ["Mira", [""], [1], ["Mira"] * 101, ["x" * 101]])
def test_bad_entities(entities):
    with pytest.raises(ValueError):
        analyze(["Good acting."], entities=entities)


def test_rating_is_not_sentiment():
    result = aspects([{"text": "The acting is terrible.", "rating": 10}])
    assert result["acting"]["verdict"] == "Mostly Negative"


def test_weighted_aggregation():
    result = aspects([{"text": "The acting is excellent.", "confidence": 1}, {"text": "The cast is terrible.", "confidence": 0.1}])
    assert result["acting"]["verdict"] == "Mostly Positive"


def test_ending_gate_can_be_disabled():
    assert aspects(["The ending is excellent."], gate_ending=False)["ending"]["verdict"] == "Mostly Positive"


def test_spoiler_still_blocked_without_ending_gate():
    assert aspects(["The ending reveals the killer."], gate_ending=False)["ending"]["verdict"] == "Spoiler-Gated"


@pytest.mark.parametrize("text,aspect", [("The acting is wooden.", "acting"), ("The pacing is slow.", "pacing"), ("The pacing is rushed.", "pacing"), ("The plot is predictable.", "plot")])
def test_film_vocabulary(text, aspect):
    assert aspects([text])[aspect]["verdict"] == "Mostly Negative"


def test_slow_burn_not_automatically_negative():
    assert aspects(["The pacing is a slow burn."])["pacing"]["verdict"] == "Neutral"


def test_domain_negation():
    assert aspects(["The plot is not predictable."])["plot"]["verdict"] == "Mostly Positive"


@pytest.mark.parametrize("key", ["rating", "confidence"])
def test_extremely_large_metadata(key):
    with pytest.raises(ValueError):
        analyze([{"text": "Good acting.", key: 10 ** 1000}])


def test_random_inputs_do_not_crash_or_leak():
    import random

    randomizer = random.Random(17)
    tokens = ["acting", "plot", "good", "bad", "not", "Mira", "dies", "!!!", "\u96ea", "", "and", "\u200b", "\n", "\x00", "[spoiler]"]
    for _ in range(150):
        text = " ".join(randomizer.choices(tokens, k=20))
        result = analyze([text])
        assert len(result["aspects"]) == 7
        assert "Mira" not in json.dumps(result)
        for item in result["aspects"]:
            assert sum(item["distribution"].values()) == item["safe_mentions"]
            assert len(item["evidence"]) <= 3