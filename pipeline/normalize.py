"""Turn one raw Discogs <release> element into a clean album record (or a rejection reason).

WHY A REJECTION REASON, NOT JUST "SKIP"
---------------------------------------
Catalog quality is decided by filters (is it an album? are durations complete?). If we
silently dropped records we could not tell whether a filter is too strict. Every rejected
record therefore comes back with a short reason code, and callers COUNT them. That turns
"why is my catalog small?" from a guess into a table.

Everything here was designed from the real field profile of the January 2025 releases
dump (docs/profile_releases.json): artists have name/join, formats carry descriptions such
as "Album", durations are "m:ss" strings, some tracks hold sub_tracks, and
master_id carries an is_main_release flag.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

# A release counts as an "album" if one of its format descriptions says so.
# Singles, EPs and compilations are separate descriptions and are excluded.
ALBUM_DESCRIPTIONS = {"Album", "LP"}
EXCLUDED_DESCRIPTIONS = {"Compilation", "Mixed", "Sampler", "Single", "Maxi-Single"}

MAX_CREDITS = 40
MAX_VIDEOS = 3

_DISAMBIGUATION = re.compile(r"\s*\(\d+\)$")  # Discogs adds "(2)" to tell artists apart
_DURATION = re.compile(r"^(\d+):(\d{1,2})(?::(\d{1,2}))?$")  # m:ss or h:mm:ss


def strip_disambiguation(name: str) -> str:
    """'Soleil (2)' -> 'Soleil'. The number is Discogs bookkeeping, not part of the name."""
    return _DISAMBIGUATION.sub("", name.strip())


def normalize_name(name: str) -> str:
    """Lowercase, accent-free, punctuation-free form used for fuzzy (trigram) search."""
    text = unicodedata.normalize("NFKD", strip_disambiguation(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


def parse_duration(text: str | None) -> int | None:
    """'4:45' -> 285, '1:02:10' -> 3730, '' -> None. Unknown formats -> None (never guess)."""
    if not text:
        return None
    match = _DURATION.match(text.strip())
    if not match:
        return None
    first, second, third = match.groups()
    if third is None:  # m:ss
        minutes, seconds = int(first), int(second)
        return minutes * 60 + seconds if seconds < 60 else None
    hours, minutes, seconds = int(first), int(second), int(third)  # h:mm:ss
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds


def parse_year(released: str | None) -> int | None:
    """'1999-03-00' -> 1999. Discogs uses 00 for unknown month/day, and 0000 for unknown year."""
    if not released or len(released) < 4 or not released[:4].isdigit():
        return None
    year = int(released[:4])
    return year if 1900 <= year <= 2100 else None


def display_artist(artists: list[tuple[str, str]]) -> str:
    """Rebuild 'A & B' from (name, join) pairs. The join string FOLLOWS its artist."""
    parts: list[str] = []
    for index, (name, join) in enumerate(artists):
        parts.append(name)
        if index < len(artists) - 1:
            join = join.strip()
            parts.append(", " if join == "," else f" {join} " if join else " ")
    return "".join(parts).replace(" ,", ",").strip()


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen)


def _parse_tracks(release: Any) -> tuple[list[dict[str, Any]] | None, str]:
    """Return (tracks, "ok") or (None, reason). Requires a usable duration on every track."""
    tracks: list[dict[str, Any]] = []
    for node in release.findall("tracklist/track"):
        position = (node.findtext("position") or "").strip()
        title = (node.findtext("title") or "").strip()
        raw = (node.findtext("duration") or "").strip()
        seconds = parse_duration(raw)
        if seconds is None and not raw:
            # Some tracks carry their time only on sub_tracks (e.g. a medley).
            subs = node.findall("sub_tracks/track")
            sub_seconds = [parse_duration(s.findtext("duration")) for s in subs]
            if subs and all(value is not None for value in sub_seconds):
                seconds = sum(v for v in sub_seconds if v is not None)
        if seconds is None:
            if not raw and not position:
                continue  # a heading row ("Side A"): no position, no time. Not a track.
            return None, "unparseable_duration" if raw else "incomplete_durations"
        tracks.append({"position": position, "title": title, "duration_s": seconds})
    if not tracks:
        return None, "no_tracklist"
    return tracks, "ok"


def parse_release(release: Any) -> tuple[dict[str, Any] | None, str]:
    """Return (album_record, "ok") or (None, reason_code).

    Checks run cheapest-and-most-decisive first, so the reason counts mean something.
    """
    master = release.find("master_id")
    if master is None or not (master.text or "").strip():
        return None, "no_master"
    if master.get("is_main_release") != "true":
        return None, "not_main_release"

    descriptions = {
        (d.text or "").strip() for d in release.findall("formats/format/descriptions/description")
    }
    if not descriptions & ALBUM_DESCRIPTIONS:
        return None, "not_album"
    if descriptions & EXCLUDED_DESCRIPTIONS:
        return None, "compilation"

    genres = _unique([(g.text or "").strip() for g in release.findall("genres/genre")])
    if "Non-Music" in genres:
        return None, "non_music"
    styles = _unique([(s.text or "").strip() for s in release.findall("styles/style")])
    if not styles:
        return None, "no_styles"

    year = parse_year(release.findtext("released"))
    if year is None:
        return None, "no_year"

    artists: list[dict[str, Any]] = []
    pairs: list[tuple[str, str]] = []
    for node in release.findall("artists/artist"):
        name = strip_disambiguation(node.findtext("name") or "")
        if not name:
            continue
        artists.append({"id": int((node.findtext("id") or "0").strip() or 0), "name": name})
        pairs.append((name, (node.findtext("join") or "")))
    if not artists:
        return None, "no_artist"
    if artists[0]["name"] == "Various":
        return None, "various_artists"

    tracks, reason = _parse_tracks(release)
    if tracks is None:
        return None, reason

    credits_seen: dict[tuple[str, str], None] = {}
    for node in release.findall("extraartists/artist"):
        name = strip_disambiguation(node.findtext("name") or "")
        role = (node.findtext("role") or "").strip()
        if name and role:
            credits_seen[(name, role)] = None
    credits = [{"name": n, "role": r} for n, r in list(credits_seen)[:MAX_CREDITS]]

    video_urls = [v.get("src") or "" for v in release.findall("videos/video")]
    display = display_artist(pairs)
    return (
        {
            "release_id": int(release.get("id")),
            "master_id": int(master.text or 0),
            "title": (release.findtext("title") or "").strip(),
            "artist_display": display,
            "artist_normalized": normalize_name(display),
            "artists": artists,
            "year": year,
            "country": (release.findtext("country") or "").strip() or None,
            "genres": genres,
            "styles": styles,
            "labels": _unique([lab.get("name") or "" for lab in release.findall("labels/label")]),
            "tracks": tracks,
            "duration_s": sum(t["duration_s"] for t in tracks),
            "credits": credits,
            "video_urls": [u for u in video_urls if u][:MAX_VIDEOS],
            "data_quality": (release.findtext("data_quality") or "").strip() or None,
        },
        "ok",
    )
