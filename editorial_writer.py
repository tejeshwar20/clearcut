"""Optional language-model editing of bounded, plot-free evidence only."""

import json
import logging
import os
import re

from pipeline import enforce_reader_output, spoiler_risk


HEADINGS = {"Overall Impression", "Acting", "Story and Writing", "Pacing", "Visuals and Cinematography", "Characters", "Verdict"}


def evidence_for_report(report):
    facts = {item["id"]: {key: item[key] for key in ("aspect", "description", "sentiment")} for item in report.get("editorial_evidence", [])}
    for item in report["aspects"]:
        if item["safe_mentions"] and item["aspect"] != "ending":
            facts["aspect:" + item["aspect"]] = {"aspect": item["aspect"], "description": item["verdict"], "passages": item["safe_mentions"]}
    return facts


def validate_sections(payload, facts):
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list) or not 2 <= len(sections) <= 7:
        raise ValueError("Invalid editorial sections.")
    seen = set()
    result = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Invalid editorial section.")
        heading = section.get("heading")
        text = section.get("text")
        references = section.get("evidence_ids")
        if heading not in HEADINGS or heading in seen or not isinstance(text, str) or not 20 <= len(text) <= 1400:
            raise ValueError("Invalid editorial text.")
        if not isinstance(references, list) or not references or any(not isinstance(reference, str) or reference not in facts for reference in references):
            raise ValueError("Editorial claims require known evidence.")
        aspects = {facts[reference]["aspect"] for reference in references}
        required = {"Acting": {"acting"}, "Story and Writing": {"plot", "writing"}, "Pacing": {"pacing"}, "Visuals and Cinematography": {"cinematography"}, "Characters": {"characters"}}.get(heading)
        if required is not None and not aspects <= required:
            raise ValueError("Editorial references do not match the section.")
        if spoiler_risk(text, []) or re.search(r"\d|https?://|\b(?:TV-MA|PG-13|rated|season|episode|award|Oscar|Emmy)\b", text, re.I) or "<" in text or ">" in text:
            raise ValueError("Editorial text contains unverified or spoiler-sensitive detail.")
        result.append({"heading": heading, "text": text.strip(), "evidence_ids": references})
        seen.add(heading)
    if "Verdict" not in seen or sum(len(section["text"]) for section in result) > 5500:
        raise ValueError("Editorial review needs a bounded verdict.")
    return result


def _request_rewrite(facts):
    from openai import OpenAI

    schema = {"type": "object", "additionalProperties": False, "required": ["sections"], "properties": {"sections": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["heading", "text", "evidence_ids"], "properties": {"heading": {"type": "string", "enum": sorted(HEADINGS)}, "text": {"type": "string"}, "evidence_ids": {"type": "array", "items": {"type": "string", "enum": list(facts)}}}}}}}
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=25, max_retries=0)
    response = client.chat.completions.create(
        model=os.environ.get("CLEARCUT_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": "Write an engaging, balanced, spoiler-free review of about 150-230 words using ONLY the supplied evidence. No title, names, plot events, genre guesses, ratings, seasons, episodes, awards, invented details, or outside knowledge. Explain what the acting, storytelling, rhythm and visual experience feel like when supported. Preserve disagreement and criticism; do not turn mixed evidence into praise. Do not call a single passage a consensus. Omit unsupported sections rather than filling them with disclaimers. No repetitive warnings, phrases about retained passages, or descriptions of your process. End with who will appreciate it and any real trade-off. Return structured sections with valid supporting evidence IDs for every section."},
            {"role": "user", "content": json.dumps(facts)},
        ],
        response_format={"type": "json_schema", "json_schema": {"name": "editorial_review", "strict": True, "schema": schema}},
        max_completion_tokens=1400,
    )
    return json.loads(response.choices[0].message.content)


def write_editorial(report):
    report["writer"] = {"provider": "local", "status": "ready"}
    if os.environ.get("CLEARCUT_WRITER", "local") != "openai":
        return report
    if not os.environ.get("OPENAI_API_KEY"):
        report["writer"]["status"] = "not_configured"
        return report
    facts = evidence_for_report(report)
    if len(facts) < 3 or report.get("quality", {}).get("supported_aspects", 0) < 2:
        report["writer"]["status"] = "limited_evidence"
        return report
    try:
        sections = validate_sections(_request_rewrite(facts), facts)
    except Exception as error:
        logging.getLogger(__name__).warning("Editorial provider unavailable or rejected: %s", type(error).__name__)
        report["writer"]["status"] = "fallback"
        return report
    report["review_sections"] = sections
    report["review"] = "\n\n".join(section["heading"] + "\n" + section["text"] for section in sections)
    report["reader_review"] = " ".join(section["text"] for section in sections)
    report["writer"] = {"provider": "openai", "status": "ready", "model": os.environ.get("CLEARCUT_MODEL", "gpt-4.1-mini")}
    return enforce_reader_output(report)