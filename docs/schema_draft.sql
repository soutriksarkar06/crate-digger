-- DRAFT schema for Crate Digger. NOT yet executed against Postgres and NOT final.
-- Finalise it at the end of Phase 0, after profiling the real dumps: column names and
-- types below follow the blueprint, but must be adjusted to what the data really holds.

CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram index: fast fuzzy title/artist search

CREATE TABLE albums (
    id                 BIGINT PRIMARY KEY,
    discogs_master_id  BIGINT UNIQUE NOT NULL,
    title              TEXT NOT NULL,
    year               INTEGER,
    country            TEXT,                 -- release country, NOT artist origin (see blueprint 2.4)
    genres             TEXT[] NOT NULL DEFAULT '{}',
    styles             TEXT[] NOT NULL DEFAULT '{}',
    duration_ms        INTEGER,              -- total; NULL unless every track has a duration
    tracklist          JSONB,
    credits            JSONB,
    cover_url          TEXT
);

CREATE TABLE artists (
    id               BIGINT PRIMARY KEY,
    name             TEXT NOT NULL,
    name_normalized  TEXT NOT NULL
);

CREATE TABLE album_artists (
    album_id   BIGINT NOT NULL REFERENCES albums(id),
    artist_id  BIGINT NOT NULL REFERENCES artists(id),
    role       TEXT,
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
    id         BIGSERIAL PRIMARY KEY,
    tool       TEXT NOT NULL,
    item_ref   TEXT NOT NULL,
    rating     SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes: these are what make search fast, and why EXPLAIN ANALYZE matters (Phase 2).
CREATE INDEX albums_title_trgm   ON albums  USING gin (title gin_trgm_ops);
CREATE INDEX artists_name_trgm   ON artists USING gin (name_normalized gin_trgm_ops);
CREATE INDEX albums_styles_gin   ON albums  USING gin (styles);
CREATE INDEX albums_genres_gin   ON albums  USING gin (genres);
CREATE INDEX albums_year_idx     ON albums  (year);
CREATE INDEX query_log_hash_idx  ON query_log (query_hash);
