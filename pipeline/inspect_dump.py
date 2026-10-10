"""Phase 0 exercise: discover the REAL structure of a Discogs data dump.

WHY THIS EXISTS
---------------
The blueprint makes several promises that depend on what the dump actually contains
(styles on every album? usable years? track durations for "Tonight"?). Rather than
assume, this script streams the first N records and reports, for every XML path:

  * how often it is present,
  * how often it has non-empty text,
  * a few example values.

It deliberately does NOT assume any field names. Whatever the dump contains shows up
in the report, so a wrong guess in this repo's fixtures cannot hide a real difference.

HOW IT STAYS MEMORY-SAFE
------------------------
A Discogs dump is a single XML document of many GB. Loading it as a tree would exhaust
memory. Instead we use lxml's `iterparse`, which fires events as the parser reads, and we
free each record as soon as we have processed it (see `iter_records`).

HOW TO RUN
----------
    python -m pipeline.inspect_dump <path-or-url> --limit 5000 --out docs/profile_masters.json

`<path-or-url>` may be a local .xml / .xml.gz file or an http(s) URL. With a URL the file
is decompressed while streaming, so you can inspect the first few thousand records of a
multi-GB dump WITHOUT downloading all of it: we simply stop reading after --limit records.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.xmlstream import iter_records, open_source

MAX_EXAMPLES = 3  # distinct example values kept per path
EXAMPLE_LEN = 60  # truncate long values so the report stays readable


# --------------------------------------------------------------------------------------
# 1. Profiling one record
# --------------------------------------------------------------------------------------
def collect_paths(record: Any) -> dict[str, str | None]:
    """Map every element/attribute path inside `record` to a sample text value.

    Paths look like "/master/styles/style" or "/release/master_id@is_main_release".
    The value is the first non-empty text seen at that path in this record, or None if
    the path exists but only ever holds empty text. Repeated elements (many <style>
    tags) collapse into one path: we care about presence, not multiplicity, here.
    """
    found: dict[str, str | None] = {}

    def walk(el: Any, prefix: str) -> None:
        if not isinstance(el.tag, str):  # skip comments / processing instructions
            return
        path = f"{prefix}/{el.tag}"
        text = (el.text or "").strip()
        if path not in found or found[path] is None:
            found[path] = text or None
        for attr, value in el.attrib.items():
            found.setdefault(f"{path}@{attr}", value or None)
        for child in el:
            walk(child, path)

    walk(record, "")
    return found


@dataclass
class Profile:
    """Accumulates presence statistics across many records."""

    record_tag: str | None = None
    records: int = 0
    present: Counter[str] = field(default_factory=Counter)
    nonempty: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=dict)

    def add(self, record: Any) -> None:
        if self.record_tag is None:
            self.record_tag = str(record.tag)
        self.records += 1
        for path, sample in collect_paths(record).items():
            self.present[path] += 1
            if sample is None:
                continue
            self.nonempty[path] += 1
            bucket = self.examples.setdefault(path, [])
            short = " ".join(sample.split())[:EXAMPLE_LEN]
            if len(bucket) < MAX_EXAMPLES and short not in bucket:
                bucket.append(short)

    def rows(self) -> list[dict[str, Any]]:
        out = []
        for path in sorted(self.present):
            out.append(
                {
                    "path": path,
                    "present_pct": round(100 * self.present[path] / self.records, 1),
                    "nonempty_pct": round(100 * self.nonempty[path] / self.records, 1),
                    "examples": self.examples.get(path, []),
                }
            )
        return out


@dataclass
class DurationStats:
    """Answers one design question: how many releases have usable track durations?

    "Tonight" only works for albums whose every track has a duration, so this number
    decides the size of its candidate pool. We report three numbers instead of one
    because real data has quirks (for example heading rows inside a tracklist) that we
    want to SEE before deciding how to clean them. Verify against real data in Phase 1.
    """

    with_tracklist: int = 0
    all_tracks_have_duration: int = 0
    some_tracks_have_duration: int = 0
    total_tracks: int = 0

    def add(self, record: Any) -> None:
        tracks = record.findall("tracklist/track")
        if not tracks:
            return
        durations = [(t.findtext("duration") or "").strip() for t in tracks]
        self.with_tracklist += 1
        self.total_tracks += len(tracks)
        if all(durations):
            self.all_tracks_have_duration += 1
        if any(durations):
            self.some_tracks_have_duration += 1


# --------------------------------------------------------------------------------------
# 2. Command line
# --------------------------------------------------------------------------------------
def profile_source(source: str, limit: int) -> tuple[Profile, DurationStats]:
    profile = Profile()
    durations = DurationStats()
    with open_source(source) as stream:
        for record in iter_records(stream):
            profile.add(record)
            if record.tag == "release":
                durations.add(record)
            if profile.records >= limit:
                break  # stop early: this is what saves us from downloading the whole dump
    return profile, durations


def print_report(profile: Profile, durations: DurationStats) -> None:
    print(f"\nRecord tag: <{profile.record_tag}>   records profiled: {profile.records}\n")
    header = f"{'path':<58} {'present':>8} {'non-empty':>10}  examples"
    print(header)
    print("-" * len(header))
    for row in profile.rows():
        examples = " | ".join(row["examples"])
        print(
            f"{row['path']:<58} {row['present_pct']:>7}% {row['nonempty_pct']:>9}%  {examples}"
        )
    if durations.with_tracklist:
        n = durations.with_tracklist
        print("\nTrack durations (releases with a tracklist):")
        print(f"  releases with a tracklist        : {n}")
        print(f"  every track has a duration       : {durations.all_tracks_have_duration}"
              f" ({100 * durations.all_tracks_have_duration / n:.1f}%)")
        print(f"  at least one track has a duration: {durations.some_tracks_have_duration}"
              f" ({100 * durations.some_tracks_have_duration / n:.1f}%)")
        print(f"  mean tracks per release          : {durations.total_tracks / n:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile the structure of a Discogs dump.")
    parser.add_argument("source", help="local .xml/.xml.gz path or http(s) URL")
    parser.add_argument("--limit", type=int, default=5000, help="records to profile")
    parser.add_argument("--out", type=Path, help="write the full report as JSON here")
    args = parser.parse_args()

    profile, durations = profile_source(args.source, args.limit)
    if profile.records == 0:
        raise SystemExit("No records found. Is this a Discogs dump file?")
    print_report(profile, durations)

    if args.out:
        payload = {
            "source": args.source,
            "record_tag": profile.record_tag,
            "records": profile.records,
            "paths": profile.rows(),
            "durations": durations.__dict__ if durations.with_tracklist else None,
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nFull report written to {args.out}")


if __name__ == "__main__":
    main()
