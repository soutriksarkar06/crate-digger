"""Tests for the Phase 0 profiler, run against tiny synthetic fixtures.

Fixtures are small on purpose: tests must run in milliseconds and offline. They check the
LOGIC of the profiler. They cannot tell you what the real dump contains; only running the
profiler on the real dump does that.
"""

import gzip
from pathlib import Path

from lxml import etree

from pipeline.inspect_dump import DurationStats, profile_source
from pipeline.xmlstream import iter_records, open_source

FIXTURES = Path(__file__).parent.parent / "data" / "fixtures"
MASTERS = str(FIXTURES / "sample_masters.xml")
RELEASES = str(FIXTURES / "sample_releases.xml")


def test_counts_records_and_detects_record_tag() -> None:
    profile, _ = profile_source(MASTERS, limit=100)
    assert profile.records == 3
    assert profile.record_tag == "master"


def test_presence_vs_nonempty() -> None:
    profile, _ = profile_source(MASTERS, limit=100)
    # <styles> exists in 2 of 3 masters -> the missing one is a real data gap we must see.
    assert profile.present["/master/styles/style"] == 2
    # <year> exists in all 3, but one is empty -> "present" and "non-empty" must differ.
    assert profile.present["/master/year"] == 3
    assert profile.nonempty["/master/year"] == 2


def test_limit_stops_early() -> None:
    profile, _ = profile_source(MASTERS, limit=2)
    assert profile.records == 2


def test_attributes_are_profiled() -> None:
    profile, _ = profile_source(RELEASES, limit=100)
    assert profile.present["/release/master_id@is_main_release"] == 2


def test_gzip_matches_plain(tmp_path: Path) -> None:
    gz_path = tmp_path / "sample_masters.xml.gz"
    gz_path.write_bytes(gzip.compress(Path(MASTERS).read_bytes()))
    plain, _ = profile_source(MASTERS, limit=100)
    zipped, _ = profile_source(str(gz_path), limit=100)
    assert zipped.records == plain.records
    assert zipped.present == plain.present


def test_duration_stats() -> None:
    _, durations = profile_source(RELEASES, limit=100)
    assert durations.with_tracklist == 2  # the third release has no tracklist
    assert durations.all_tracks_have_duration == 1  # only release 5001 is complete
    assert durations.some_tracks_have_duration == 2


def test_iter_records_frees_siblings() -> None:
    """The streaming idiom must not break iteration: every record is still yielded once."""
    with open_source(MASTERS) as stream:
        titles = [r.findtext("title") for r in iter_records(stream)]
    assert len(titles) == 3


def test_duration_stats_ignores_records_without_tracklist() -> None:
    """A release with no <tracklist> must not count toward any duration statistic."""
    stats = DurationStats()
    stats.add(etree.fromstring("<release id='1'><title>No tracks</title></release>"))
    assert stats.with_tracklist == 0
    assert stats.total_tracks == 0
