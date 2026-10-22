"""Evaluate against an independently annotated JSON file of sentence examples."""

import argparse
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report

from pipeline import analyze, spoiler_risk


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(__file__).parent / "data" / "evaluation_examples.json")
    args = parser.parse_args()
    examples = json.loads(args.data.read_text(encoding="utf-8"))
    actual_spoilers, predicted_spoilers = [], []
    actual_sentiment, predicted_sentiment = [], []
    for example in examples:
        actual_spoilers.append(example["spoiler"])
        predicted_spoilers.append(spoiler_risk(example["text"], example.get("entities", [])))
        if not example["spoiler"] and "aspect" in example:
            actual_sentiment.append(example["sentiment"])
            result = analyze([example["text"]], entities=example.get("entities", []), gate_ending=False)
            aspect = next(item for item in result["aspects"] if item["aspect"] == example["aspect"])
            verdict = aspect["verdict"]
            predicted_sentiment.append({"Mostly Positive": "positive", "Mostly Negative": "negative", "Neutral": "neutral"}.get(verdict, "abstained"))
    print(f"Dataset: {args.data} ({len(examples)} examples)")
    print("Bundled data is synthetic sanity-check data, NOT a held-out benchmark.")
    print("\nSpoiler classification (True = risky):")
    print(classification_report(actual_spoilers, predicted_spoilers, zero_division=0))
    if actual_sentiment:
        print(f"Safe aspect sentiment: accuracy = {accuracy_score(actual_sentiment, predicted_sentiment):.3f}")
        print(classification_report(actual_sentiment, predicted_sentiment, zero_division=0))


if __name__ == "__main__":
    main()