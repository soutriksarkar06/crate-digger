"""Tests for normalization. Each fixture release in sample_releases_realistic.xml exercises
exactly one catalog filter, so a failure points at one rule."""

from collections import Counter
from pathlib import Path

import pytest

from pipeline.normalize import (
    display_artist,
    normalize_name,
    parse_duration,
    parse_release,
    parse_year,
    strip_disambiguation,
)
from pipeline.xmlstream import iter_records, open_source

FIXTURE = str(Path(__file__).parent.parent / "data" / "fixtures" / "sample_releases_realistic.xml")


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("4:45", 285), ("0:59", 59), ("1:02:10", 3730), ("", None), (None, None),
     ("4.45", None), ("4:75", None), ("abc", None), ("1:75:10", None)],
)
def test_parse_duration(text: str | None, seconds: int | None) -> None:
    assert parse_duration(text) == seconds


@pytest.mark.parametrize(
    ("released", "year"),
    [("1999-03-00", 1999), ("1975", 1975), ("0000-00-00", None), ("", None), (None, None)],
)
def test_parse_year(released: str | None, year: int | None) -> None:
    assert parse_year(released) == year


def test_names() -> None:
    assert strip_disambiguation("Soleil (2)") == "Soleil"
    assert strip_disambiguation("Sunn O)))") == "Sunn O)))"  # not a numeric suffix
    assert normalize_name("Björk (3)") == "bjork"
    assert normalize_name("Mr. James Barth & A.D.") == "mr james barth a d"


def test_display_artist_uses_join_strings() -> None:
    assert display_artist([("Soleil", "&"), ("Blue Arsed Fly", "")]) == "Soleil & Blue Arsed Fly"
    assert display_artist([("A", ","), ("B", ","), ("C", "")]) == "A, B, C"
    assert display_artist([("Solo", "&")]) == "Solo"  # trailing join is ignored


def _outcomes() -> dict[str, tuple[dict | None, str]]:  # type: ignore[type-arg]
    results = {}
    with open_source(FIXTURE) as stream:
        for record in iter_records(stream):
            results[record.get("id")] = parse_release(record)
    return results


def test_each_filter_fires_for_its_release() -> None:
    reasons = {rid: reason for rid, (_, reason) in _outcomes().items()}
    assert reasons == {
        "101": "ok",
        "102": "not_album",
        "103": "compilation",
        "104": "incomplete_durations",
        "105": "ok",
        "106": "not_main_release",
        "107": "no_styles",
        "108": "unparseable_duration",
    }


def test_good_album_is_fully_normalized() -> None:
    album, _ = _outcomes()["101"]
    assert album is not None
    assert album["artist_display"] == "Soleil & Blue Arsed Fly"  # (2) stripped, join used
    assert album["year"] == 1999
    assert album["genres"] == ["Electronic", "Folk, World, & Country"]  # comma kept inside
    assert [t["position"] for t in album["tracks"]] == ["A1", "A2", "B1"]  # heading row dropped
    assert album["duration_s"] == 285 + 308 + 3730
    assert album["credits"] == [{"name": "Some Producer", "role": "Producer"}]
    assert album["video_urls"] == ["https://www.youtube.com/watch?v=abc"]


def test_sub_tracks_are_summed() -> None:
    album, _ = _outcomes()["105"]
    assert album is not None
    assert album["duration_s"] == 190 + 253


def test_reason_counts_add_up() -> None:
    counts = Counter(reason for _, reason in _outcomes().values())
    assert sum(counts.values()) == 8
    assert counts["ok"] == 2
