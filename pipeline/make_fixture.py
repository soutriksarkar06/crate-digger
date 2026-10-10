"""Build a small, DIVERSE album fixture from the real releases dump.

WHY: tests and local development need a few hundred real-shaped albums, not 10 GB.

HOW: stream the first `--max-scan` releases, keep those that pass every catalog filter in
`normalize.parse_release`, and pick `--count` of them by RESERVOIR SAMPLING. Reservoir
sampling (Algorithm R) gives every passing record an equal chance of being chosen without
knowing in advance how many will pass, and without storing them all. A plain "take the
first 1,000" would give you one tiny corner of the database (the oldest, mostly 1990s
electronic releases), which is useless for testing similarity.

It also prints WHY records were rejected. Read that table: it tells you whether a filter
(for example "must be an Album") is too strict before you build the full pipeline on it.

RUN
    python -m pipeline.make_fixture "<RELEASES_URL>" --count 1000 --max-scan 200000 \
        --out data/fixtures/albums_sample.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline.normalize import parse_release
from pipeline.xmlstream import iter_records, open_source


def build(
    source: str, count: int, max_scan: int, seed: int
) -> tuple[list[dict[str, Any]], int, int, Counter[str]]:
    rng = random.Random(seed)  # fixed seed: the same command gives the same fixture
    reservoir: list[dict[str, Any]] = []
    scanned = passed = 0
    reasons: Counter[str] = Counter()
    with open_source(source) as stream:
        for record in iter_records(stream):
            scanned += 1
            album, reason = parse_release(record)
            reasons[reason] += 1
            if album is not None:
                passed += 1
                if len(reservoir) < count:
                    reservoir.append(album)
                else:
                    slot = rng.randrange(passed)  # 0..passed-1, uniform
                    if slot < count:
                        reservoir[slot] = album
            if scanned % 20000 == 0:
                print(f"  scanned {scanned:,}  passing {passed:,}", file=sys.stderr)
            if scanned >= max_scan:
                break
    return reservoir, scanned, passed, reasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a diverse album fixture.")
    parser.add_argument("source", help="releases dump: local path or http(s) URL")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--max-scan", type=int, default=200_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data/fixtures/albums_sample.jsonl"))
    args = parser.parse_args()

    albums, scanned, passed, reasons = build(args.source, args.count, args.max_scan, args.seed)
    albums.sort(key=lambda a: a["release_id"])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for album in albums:
            handle.write(json.dumps(album, ensure_ascii=False) + "\n")

    print(f"\nScanned {scanned:,} releases; {passed:,} passed all filters; kept {len(albums):,}.")
    print("\nOutcome of every scanned release:")
    for reason, number in reasons.most_common():
        print(f"  {reason:<24} {number:>9,}  ({100 * number / scanned:5.1f}%)")
    styles = Counter(s for a in albums for s in a["styles"])
    decades = Counter(f"{a['year'] // 10 * 10}s" for a in albums)
    print(f"\nDistinct styles in fixture: {len(styles)}   top: {styles.most_common(8)}")
    print(f"Decades: {sorted(decades.items())}")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
