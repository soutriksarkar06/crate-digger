"""Streaming helpers shared by every pipeline script.

A Discogs dump is one XML document of many GB, so nothing in this project ever builds a
whole tree. Everything flows through `open_source` (bytes in) and `iter_records`
(one finished record at a time, memory freed behind it).
"""

from __future__ import annotations

import gzip
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any, cast

from lxml import etree

# Some hosts reject Python's default client name with 403. Identify ourselves honestly.
USER_AGENT = "CrateDigger/0.1 (learning project)"


@contextmanager
def open_source(source: str) -> Iterator[IO[bytes]]:
    """Yield a binary stream over `source` (local path or http(s) URL), un-gzipping on the fly.

    Streaming gzip means we never hold the whole file: the decompressor hands bytes to
    the XML parser as they arrive. If we stop early, we simply close the connection.
    """
    if source.startswith(("http://", "https://")):
        request = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        raw: Any = urllib.request.urlopen(request)  # network stream, read sequentially
    else:
        raw = open(source, "rb")
    try:
        if source.endswith(".gz") or "xml.gz" in source:
            with gzip.GzipFile(fileobj=raw) as gz:
                yield cast(IO[bytes], gz)
        else:
            yield raw
    finally:
        raw.close()


def iter_records(stream: IO[bytes]) -> Iterator[Any]:
    """Yield each top-level record (a direct child of the root element), one at a time.

    The dump looks like  <masters> <master>...</master> <master>...</master> ... </masters>.
    We track nesting depth from start/end events:
        depth 1 = the root   depth 2 = one record   deeper = fields inside a record.
    When a depth-2 element *ends*, it is complete and we hand it to the caller.

    MEMORY IDIOM (important): after the caller is done with a record we
      1) `elem.clear()`   - drop its children and text, and
      2) delete earlier siblings from the root.
    Without step 2 the root would keep thousands of empty record shells alive and memory
    would still grow linearly with file size.
    """
    depth = 0
    for event, elem in etree.iterparse(stream, events=("start", "end")):
        if event == "start":
            depth += 1
            continue
        if depth == 2:
            yield elem  # caller processes the finished record here
            elem.clear()
            parent = elem.getparent()
            if parent is not None:
                while elem.getprevious() is not None:
                    del parent[0]
        depth -= 1
