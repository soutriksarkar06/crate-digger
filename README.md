# Crate Digger

AI music search, bridges and listening guides on open data.

- **Ask**: plain-English music search ("albums like Kid A but less electronic")
- **Bridge**: a step-by-step path of albums between two artists or genres
- **Tonight**: one album that fits your time budget, with a listening guide

Status: **Phase 0 (setup), closing out**. See `docs/PHASE0.md`.

## Build phases

- [ ] 0. Setup: repo, CI, licences, schema draft, dump profiling
- [ ] 1. Data pipeline: stream-parse dumps into a 50k to 100k album catalog
- [ ] 2. Catalog and API shell: search, album page, first deploy
- [ ] 3. Similarity engine: TF-IDF, SVD, kNN, from scratch
- [ ] 4. Ask: natural-language search with a validated LLM parser
- [ ] 5. Bridge: beam-search paths with a similarity floor
- [ ] 6. Tonight: duration-fitted album and grounded guide
- [ ] 7. Hardening and launch
- [ ] 8. Stretch goals

## Quick start

    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    pytest -q

## Layout

    pipeline/      offline data pipeline (dump -> catalog -> similarity artifacts)
    apps/api/      FastAPI service (Phase 2)
    apps/web/      frontend (Phase 2)
    packages/core/ shared similarity code (Phase 3)
    eval/          evaluation sets and runners
    data/fixtures/ tiny synthetic files for tests
    docs/          data-sources register, schema, phase guides
