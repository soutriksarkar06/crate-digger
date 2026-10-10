# Data sources register

The document that protects you if anyone asks "where did this data come from, and are you
allowed to use it?". Keep exact dates, and quote licence text rather than paraphrasing it.

## 1. Discogs data dumps

| Field | Value |
| --- | --- |
| Where | Discogs "Download Discogs Data" page, a plain file listing with monthly dumps |
| Files profiled | `discogs_20250101_masters.xml.gz` (about 525 MB) and `discogs_20250101_releases.xml.gz` (about 9.6 GB) |
| Dump date profiled | 2025-01-01 (first 5,000 records of each; Phase 1 should use the newest month that has BOTH files, since some months lack a masters file) |
| Licence statement | The listing page states: "This data is made available under the CC0 No Rights Reserved license." The Discogs API documentation home page also states: "Our monthly data dumps are available under the CC0 No Rights Reserved license." Both read on 2026-10-10. |
| Do not use | Data fetched through the Discogs API: the API documentation says some of it is restricted under the API Terms of Use. The API is also rate-limited (60 requests per minute authenticated). We use dumps only. |
| Profiles | `docs/profile_masters.json`, `docs/profile_releases.json` |
| Sample caveat | Each profile covers the first 5,000 records, which are the OLDEST (ids start at 1 and 113, mostly 1990s electronic). Re-measure percentages on the full file in Phase 1. |

### Fields confirmed present (first 5,000 records)

**Masters:** `title`, `year` (100%), `main_release` (100%), `artists` (name, id, join),
`genres` (100%), `styles` (99.3%), `data_quality`, `notes` (12.7%), `videos` (92.4%).

**Releases:** `title`, `country` (100%), `released` (98.6%, partial dates like `1999-03-00`),
`artists` (name, join), `extraartists` with roles (81.6%), `formats` (name, descriptions such
as "Album"), `genres`, `styles` (99.9%), `labels`, `identifiers` including barcodes (78.6%),
`master_id` with an `is_main_release` flag, `tracklist` with `position` and `duration`,
`videos` with YouTube links (80.7%), `data_quality`.

### Fields confirmed ABSENT

- Popularity of any kind (no have/want counts, no ratings). Use data richness as a proxy.
- Images or cover art. Cover art needs another source and is a stretch goal.
- Artist country of origin. `country` is the RELEASE country, a labeled proxy only.
- Mood or descriptor fields.

### Measured facts that shape the design

- Releases where every track has a duration: **54.4%** of the first 5,000 (at least one
  track: 58.7%; mean 5.9 tracks per release). This sets the size of the "Tonight" pool.
- Durations are `m:ss` strings. Some tracks carry their time only on `sub_tracks`.
- Artist names carry disambiguation suffixes such as "Soleil (2)".
- Genre names can contain commas ("Folk, World, & Country").
- Releases include singles, EPs and compilations, so "is an album" must be a filter.

### Transformations (implemented in `pipeline/normalize.py`)

Keep only the main release of each master that is an Album, not a Compilation, not
"Various" artists, not "Non-Music", has at least one style, a year, and a usable duration on
every track. Every rejected record gets a reason code and is counted.

## 2. MusicBrainz (optional, Phase 8)

Artist origin area for a proper "from Japan" filter. Core data and supplementary data
(such as tags) are licensed differently; record which you use. Status: not used yet.

## 3. Cover Art Archive (optional)

Album artwork. Images are not all freely licensed: link, do not redistribute, attribute.
Status: not used yet.

## 4. Outbound listen links

YouTube links already present in the dump (`videos`) and search URLs for streaming
services. No API, no keys, no data stored beyond the URLs.

## Licence check (Phase 0 exit criterion)

- [x] Read the Discogs data page and copied the licence wording (2026-10-10)
- [ ] Decide what the public site may display (titles, styles, durations, links)
- [ ] Plan the attribution footer (blueprint Section 12)
- [ ] Re-check before public launch (Phase 7)
