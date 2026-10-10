# Phase 0: Setup. Close-out

You have already done: environment, tests, and profiling both dumps. What is left:

## Step 1: Install the updated scaffold and run the checks

    pip install -e ".[dev]"
    ruff check .
    mypy
    pytest -q        # 28 should pass

## Step 2: Build the 1,000-album fixture from the real releases dump

    python -m pipeline.make_fixture "https://data.discogs.com/?download=data%2F2025%2Fdiscogs_20250101_releases.xml.gz" --count 1000 --max-scan 200000 --out data/fixtures/albums_sample.jsonl

This streams about 200,000 releases (roughly 100 to 150 MB), so it takes a few minutes.
At the end it prints a table of WHY releases were rejected. Read it: if "not_album" or
"incomplete_durations" is huge, a filter may be too strict. Paste that table to me.

## Step 3: Read the code

- `pipeline/xmlstream.py`: streaming and memory idiom
- `pipeline/normalize.py`: every filter and cleaning rule, with the reason for each
- `tests/test_normalize.py`: one fixture release per filter

## Step 4: Commit and push; confirm CI is green

## Phase 0 exit criteria

- [x] Both dump profiles saved in `docs/`
- [x] `docs/data-sources.md` filled in with dates and licence wording
- [x] Schema revised against real fields (`docs/schema.sql`)
- [ ] 1,000-album fixture generated and reviewed
- [ ] CI green
