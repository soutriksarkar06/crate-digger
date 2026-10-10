"""Diagnostic: what do MAIN releases rejected as "not_album" actually look like?

WHY: in the first fixture run, 88.7% of main releases failed the rule "format descriptions
must include 'Album'". That is either correct (early Discogs is full of 12-inch singles) or a
sign the rule is too strict (for example LPs or CDs tagged without the word "Album"). This
script answers it by counting the real format and description combinations of the rejects.

RUN
    python -m pipeline.diagnose_formats "<RELEASES_URL>" --max-scan 100000
"""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any

from pipeline.normalize import parse_release
from pipeline.xmlstream import iter_records, open_source


def diagnose(source: str, max_scan: int) -> tuple[Counter[tuple[str, str]], Counter[str], int]:
    combos: Counter[tuple[str, str]] = Counter()
    single_descriptions: Counter[str] = Counter()
    scanned = 0
    with open_source(source) as stream:
        for record in iter_records(stream):
            scanned += 1
            _, reason = parse_release(record)
            if reason == "not_album":
                combos_key = _format_key(record)
                combos[combos_key] += 1
                for description in combos_key[1].split(", "):
                    single_descriptions[description or "(none)"] += 1
            if scanned >= max_scan:
                break
    return combos, single_descriptions, scanned


def _format_key(record: Any) -> tuple[str, str]:
    names = sorted({f.get("name") or "" for f in record.findall("formats/format")})
    descriptions = sorted(
        {(d.text or "").strip() for d in record.findall("formats/format/descriptions/description")}
    )
    return ", ".join(names), ", ".join(descriptions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect releases rejected as not_album.")
    parser.add_argument("source")
    parser.add_argument("--max-scan", type=int, default=100_000)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    combos, singles, scanned = diagnose(args.source, args.max_scan)
    total = sum(combos.values())
    print(f"\nScanned {scanned:,} releases; {total:,} main releases were rejected as not_album.\n")
    print("Most common (format, descriptions) combinations among the rejects:")
    for (names, descriptions), count in combos.most_common(args.top):
        print(f"  {count:>7,} {100 * count / total:5.1f}%  {names:<16} {descriptions or '(none)'}")
    print("\nMost common single descriptions among the rejects:")
    for description, count in singles.most_common(20):
        print(f"  {count:>7,} {100 * count / total:5.1f}%  {description}")


if __name__ == "__main__":
    main()
