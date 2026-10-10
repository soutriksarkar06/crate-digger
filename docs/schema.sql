-- Crate Digger schema, revised after profiling the real January 2025 Discogs dumps.
-- NOT yet executed against Postgres: run it in Phase 1 and fix whatever it reports.
--
-- Changes from the first draft, and why:
--   * duration_s (seconds), not duration_ms: Discogs gives whole seconds.
--   * cover_url dropped: the dumps contain no image fields (see profile). Cover art is a
--     stretch goal that needs another source.
--   * added main_release_id, artist_display, formats-free album filter results, labels,
--     video_urls and data_quality, all of which are present in the real data.

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram index: fast fuzzy title/artist search

CREATE TABLE albums (
    id                 BIGINT PRIMARY KEY,
    discogs_master_id  BIGINT UNIQUE NOT NULL,
    main_release_id    BIGINT NOT NULL,
    title              TEXT NOT NULL,
    artist_display     TEXT NOT NULL,         -- "Soleil & Blue Arsed Fly", rebuilt from join strings
    artist_normalized  TEXT NOT NULL,         -- lowercase, no accents/punctuation: for trigram search
    year               INTEGER NOT NULL,
    country            TEXT,                  -- RELEASE country, not artist origin (blueprint 2.4)
    genres             TEXT[] NOT NULL DEFAULT '{}',   -- real lists: genre names contain commas
    styles             TEXT[] NOT NULL DEFAULT '{}',
    labels             TEXT[] NOT NULL DEFAULT '{}',
    duration_s         INTEGER NOT NULL,      -- only albums with a duration on EVERY track
    tracklist          JSONB NOT NULL,        -- [{position, title, duration_s}]
    credits            JSONB,                 -- [{name, role}], capped
    video_urls         TEXT[] NOT NULL DEFAULT '{}',   -- YouTube links from the dump (listen links)
    data_quality       TEXT                   -- 'Correct', 'Complete and Correct', 'Needs Vote'...
);

CREATE TABLE artists (
    id               BIGINT PRIMARY KEY,      -- Discogs artist id
    name             TEXT NOT NULL,           -- disambiguation "(2)" stripped
    name_normalized  TEXT NOT NULL
);

CREATE TABLE album_artists (
    album_id   BIGINT   NOT NULL REFERENCES albums(id),
    artist_id  BIGINT   NOT NULL REFERENCES artists(id),
    position   SMALLINT NOT NULL,             -- order matters for display names
    PRIMARY KEY (album_id, artist_id)
);

CREATE TABLE styles (
    id           INTEGER PRIMARY KEY,
    name         TEXT UNIQUE NOT NULL,
    genre        TEXT,
    album_count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE album_styles (
    album_id  BIGINT  NOT NULL REFERENCES albums(id),
    style_id  INTEGER NOT NULL REFERENCES styles(id),
    PRIMARY KEY (album_id, style_id)
);

-- Precomputed k-nearest-neighbour graph (built offline in Phase 3).
CREATE TABLE neighbors (
    album_id     BIGINT   NOT NULL REFERENCES albums(id),
    neighbor_id  BIGINT   NOT NULL REFERENCES albums(id),
    similarity   REAL     NOT NULL,
    rank         SMALLINT NOT NULL,
    PRIMARY KEY (album_id, rank)
);

-- Observability and the evaluation corpus. Stores NO user identifier.
CREATE TABLE query_log (
    id           BIGSERIAL PRIMARY KEY,
    query_hash   TEXT NOT NULL,
    raw_query    TEXT NOT NULL,
    parsed_json  JSONB,
    latency_ms   INTEGER,
    cache_hit    BOOLEAN,
    status       TEXT,
    cost_usd     NUMERIC(10, 6),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    id          BIGSERIAL PRIMARY KEY,
    tool        TEXT NOT NULL,
    item_ref    TEXT NOT NULL,
    rating      SMALLINT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes: these are what make search fast, and why EXPLAIN ANALYZE matters (Phase 2).
CREATE INDEX albums_title_trgm   ON albums  USING gin (title gin_trgm_ops);
CREATE INDEX albums_artist_trgm  ON albums  USING gin (artist_normalized gin_trgm_ops);
CREATE INDEX artists_name_trgm   ON artists USING gin (name_normalized gin_trgm_ops);
CREATE INDEX albums_styles_gin   ON albums  USING gin (styles);
CREATE INDEX albums_genres_gin   ON albums  USING gin (genres);
CREATE INDEX albums_year_idx     ON albums  (year);
CREATE INDEX query_log_hash_idx  ON query_log (query_hash);
