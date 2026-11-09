"""Train Oryven's lightweight Multinomial Naive Bayes intent router.

Input CSV columns: text,label
No third-party ML dependency is required, making the artifact easy to audit and ship.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
import json
import re
import unicodedata

TOKEN = re.compile(r"[a-z0-9_.+-]+", re.I)


def tokens(text: str):
    text = "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")
    return TOKEN.findall(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = []
    with args.dataset.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("text", "").strip() and row.get("label", "").strip():
                rows.append((row["text"].strip(), row["label"].strip()))
    if len(rows) < 10:
        raise SystemExit("dataset pequeno demais")
    per_class = defaultdict(Counter)
    docs = Counter()
    vocabulary = set()
    for text, label in rows:
        ts = tokens(text)
        per_class[label].update(ts)
        vocabulary.update(ts)
        docs[label] += 1
    total_docs = sum(docs.values())
    model = {"format": 1, "classes": sorted(docs), "vocabulary": sorted(vocabulary), "stats": {}}
    for label in sorted(docs):
        model["stats"][label] = {
            "prior": docs[label] / total_docs,
            "token_total": sum(per_class[label].values()),
            "token_counts": dict(per_class[label]),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"trained rows={len(rows)} classes={len(docs)} vocab={len(vocabulary)} -> {args.output}")


if __name__ == "__main__":
    main()
