import pytest

from pipeline import analyze_reader_review


SPOILER_CASES = [
    ("M. Night Shyamalan's The Sixth Sense is a haunting, beautifully restrained ghost story anchored by Haley Joel Osment's astonishing performance. "
     "Bruce Willis plays child psychologist Malcolm Crowe, who tries to help a frightened boy who claims he sees dead people. "
     "The atmosphere is quietly chilling and the cinematography is gorgeously muted. "
     "In the final scene we learn that Malcolm has been dead the entire time, shot by a former patient in the opening sequence.",
     ["haunting, beautifully restrained ghost story", "cinematography is gorgeously muted"],
     ["dead the entire time", "former patient", "has been dead"]),
    ("David Fincher's Fight Club is a ferocious, darkly funny satire with razor-sharp editing and a pulsing score by the Dust Brothers. "
     "Edward Norton plays an insomniac office worker who meets the charismatic soap salesman Tyler Durden (Brad Pitt). "
     "The film's biggest twist is that Tyler is a figment of the narrator's imagination, and the two are the same person. "
     "It ends with the narrator shooting himself through the cheek as the buildings collapse.",
     ["razor-sharp editing", "Tyler Durden (Brad Pitt)"],
     ["figment", "same person", "shooting himself", "buildings collapse", "twist"]),
    ("Jeethu Joseph's Drishyam is a tightly written, deeply gripping family thriller with a superb, understated performance by Mohanlal. "
     "Georgekutty, a cable operator obsessed with films, protects his family when the son of the Inspector General goes missing. "
     "The screenplay is meticulous and the tension never lets up. "
     "In the final twist, it turns out Georgekutty buried the body under the new police station that was being built.",
     ["understated performance by Mohanlal", "screenplay is meticulous"],
     ["buried", "body", "police station", "turns out"]),
    ("Avengers: Endgame is an emotionally satisfying, crowd-pleasing spectacle with terrific visual effects and a stirring score by Alan Silvestri. "
     "After Thanos wipes out half of all life, the surviving heroes regroup to attempt a time heist. "
     "Natasha sacrifices herself on Vormir to obtain the Soul Stone. "
     "Tony Stark snaps his fingers with the Infinity Stones and dies, while an elderly Steve Rogers passes the shield to Sam.",
     ["crowd-pleasing spectacle", "stirring score by Alan Silvestri"],
     ["sacrifices", "Vormir", "dies", "snaps", "passes the shield", "elderly"]),
    ("Gone Girl is a sleek, venomous thriller with a chilling, career-best performance from Rosamund Pike and icy cinematography. "
     "When Amy Dunne disappears on her fifth wedding anniversary, suspicion falls on her husband Nick (Ben Affleck). "
     "Midway through, the film reveals that Amy faked her own disappearance to frame Nick for murder. "
     "She later kills Desi Collings and returns home, trapping Nick in the marriage.",
     ["career-best performance from Rosamund Pike"],
     ["faked", "frame", "kills", "Desi", "returns home", "trapping"]),
    ("Shutter Island is a moody, atmospheric psychological thriller, with Leonardo DiCaprio delivering a feverish, committed performance. "
     "U.S. Marshal Teddy Daniels arrives at an island asylum to investigate a missing patient. "
     "Robbie Robertson's selection of music is unnerving and the production design is superb. "
     "Teddy is actually Andrew Laeddis, a patient at the hospital who murdered his wife after she drowned their children, and he chooses a lobotomy at the end.",
     ["feverish, committed performance", "production design is superb"],
     ["Laeddis", "drowned", "lobotomy", "is actually", "murdered his wife"]),
    ("Bong Joon-ho's Parasite is a brilliantly constructed, wickedly funny class satire with immaculate production design. "
     "The poor Kim family cons their way into jobs with the wealthy Park family. "
     "The ensemble cast is uniformly excellent, and the pacing is flawless. "
     "Eventually the former housekeeper's husband is discovered living in the bunker, and the birthday party ends in a bloodbath where Ki-taek stabs Mr. Park.",
     ["wickedly funny class satire", "pacing is flawless"],
     ["bunker", "stabs", "bloodbath", "housekeeper's husband"]),
    ("Rishab Shetty's Kantara is a visually spectacular, deeply rooted folklore drama with thunderous sound design and a blistering lead performance by Shetty himself. "
     "Shiva, a rebellious villager, clashes with a forest officer over land rights. "
     "The climax features Shiva being possessed by the deity Panjurli during the Bhoota Kola, where he vanishes into the forest just like his father did years earlier.",
     ["thunderous sound design", "clashes with a forest officer"],
     ["possessed", "vanishes", "Panjurli", "Bhoota", "his father did"]),
    ("This is a warm, beautifully acted small-town drama with a lovely acoustic soundtrack. "
     "The grandmother quietly passes away in her sleep before the wedding, and her granddaughter inherits the bakery. "
     "The dialogue is witty and the cinematography is luminous.",
     ["lovely acoustic soundtrack", "dialogue is witty"],
     ["passes away", "inherits", "grandmother"]),
]


@pytest.mark.parametrize("text,kept,forbidden", SPOILER_CASES)
def test_spoiler_heavy_reviews_keep_original_opinions_and_drop_spoilers(text, kept, forbidden):
    report = analyze_reader_review([text])
    review = report["review"]
    assert report["reader_output"]["blocked"] is False
    for phrase in kept:
        assert phrase in review
    for term in forbidden:
        assert term.lower() not in review.lower()
    assert "overall_score" not in report


@pytest.mark.parametrize("text", [
    "The heist sequence is brilliantly executed and the editing is crisp.",
    "Her shattering performance is the heart of the film, and the score is triumphant.",
    "A beautifully shot, slow-burn mystery with a haunting soundtrack.",
])
def test_craft_praise_with_cue_like_words_is_not_removed(text):
    assert analyze_reader_review([text])["review"] == text


def test_mixed_review_without_spoilers_is_returned_unchanged():
    text = "The dialogue is clunky and the villain is a cardboard cutout, though the stunts are spectacular."
    assert analyze_reader_review([text])["review"] == text


def test_spoiler_free_review_is_returned_unchanged():
    text = "A warm, funny comedy with a terrific cast. The editing is brisk and the soundtrack is joyous."
    assert analyze_reader_review([text], title="Some Title")["review"] == text


@pytest.mark.parametrize("text,expected,forbidden", [
    ("I loved the cast. I couldn't believe the detective was the killer all along.",
     "I loved the cast. I couldn't believe the big surprise.", ["detective", "killer"]),
    ("The acting is great. The twist that the butler did it is predictable and lazy.",
     "The acting is great. The big surprise is predictable and lazy.", ["butler"]),
    ("The score is gorgeous. I was stunned when she died in the final scene.",
     "The score is gorgeous. I was stunned by the ending.", ["died", "she"]),
])
def test_spoiler_sentences_are_rephrased_with_the_reviewers_reaction(text, expected, forbidden):
    review = analyze_reader_review([text])["review"]
    assert review == expected
    for term in forbidden:
        assert term not in review.lower().split()


def test_multi_paragraph_reviews_keep_paragraph_breaks():
    review = analyze_reader_review(["The cast is superb.", "The music is lovely."])["review"]
    assert review == "The cast is superb.\n\nThe music is lovely."


def test_model_rewrite_is_rejected_when_it_leaks_spoiler_details(monkeypatch):
    import source_writer

    class Completions:
        def __init__(self, content):
            self.content = content

        def create(self, **kwargs):
            assert kwargs["messages"][0]["content"] == source_writer.EDITOR_PROMPT
            message = type("Message", (), {"content": self.content})
            return type("Response", (), {"choices": [type("Choice", (), {"message": message})]})

    def client(content):
        return lambda **kwargs: type("Client", (), {"chat": type("Chat", (), {"completions": Completions(content)})})

    import openai

    monkeypatch.setenv("CLEARCUT_WRITER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    text = "The cast is superb. I couldn't believe the detective was the killer all along."
    monkeypatch.setattr(openai, "OpenAI", client("The cast is superb. The final reveal genuinely caught me off guard."))
    good = analyze_reader_review([text])
    assert good["writer"]["provider"] == "openai"
    assert good["review"] == "The cast is superb. The final reveal genuinely caught me off guard."
    monkeypatch.setattr(openai, "OpenAI", client("The cast is superb. The detective's secret caught me off guard."))
    leaked = analyze_reader_review([text])
    assert leaked["writer"]["provider"] == "local"
    assert "detective" not in leaked["review"]
