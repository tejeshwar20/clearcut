import pytest

import editorial_writer
from pipeline import analyze_reception


def sample_report():
    return analyze_reception(["The acting is nuanced. The writing is sharp. The pacing drags."])


def test_local_mode_never_contacts_provider(monkeypatch):
    monkeypatch.setenv("CLEARCUT_WRITER", "local")
    monkeypatch.setattr(editorial_writer, "_request_rewrite", lambda facts: pytest.fail("must not call provider"))
    assert editorial_writer.write_editorial(sample_report())["writer"]["provider"] == "local"


def test_missing_key_uses_honest_local_fallback(monkeypatch):
    monkeypatch.setenv("CLEARCUT_WRITER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert editorial_writer.write_editorial(sample_report())["writer"]["status"] == "not_configured"


def test_provider_failure_preserves_safe_review(monkeypatch):
    monkeypatch.setenv("CLEARCUT_WRITER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-not-a-real-key")

    def unavailable(facts):
        raise TimeoutError()

    monkeypatch.setattr(editorial_writer, "_request_rewrite", unavailable)
    report = sample_report()
    original = report["review"]
    result = editorial_writer.write_editorial(report)
    assert result["review"] == original
    assert result["writer"]["status"] == "fallback"


@pytest.mark.parametrize("text,reference", [
    ("The protagonist dies after the final confrontation.", "aspect:acting"),
    ("The acting is excellent and this deserves a rating of 10.", "aspect:acting"),
    ("The acting provides a consistently engaging experience.", "invented-evidence"),
])
def test_generated_claims_must_be_safe_and_referenced(text, reference):
    payload = {"sections": [{"heading": "Acting", "text": text, "evidence_ids": [reference]}, {"heading": "Verdict", "text": "Worth considering for the performances and writing.", "evidence_ids": ["aspect:acting"]}]}
    with pytest.raises(ValueError):
        editorial_writer.validate_sections(payload, editorial_writer.evidence_for_report(sample_report()))


def test_valid_editorial_output_uses_only_safe_structured_evidence(monkeypatch):
    monkeypatch.setenv("CLEARCUT_WRITER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test-not-a-real-key")

    def rewrite(facts):
        assert all("text" not in fact for fact in facts.values())
        return {"sections": [
            {"heading": "Acting", "text": "Understated performances give the material emotional texture.", "evidence_ids": ["acting:nuanced"]},
            {"heading": "Verdict", "text": "Worth considering for restrained acting, provided a slower rhythm is not a deal-breaker.", "evidence_ids": ["acting:nuanced", "pacing:dragging"]},
        ]}

    monkeypatch.setattr(editorial_writer, "_request_rewrite", rewrite)
    report = editorial_writer.write_editorial(sample_report())
    assert report["writer"]["provider"] == "openai"
    assert "Understated" in report["review"]