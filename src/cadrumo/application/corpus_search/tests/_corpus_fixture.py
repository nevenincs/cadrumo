"""Shared helper: materialise a small real-corpus subset for index tests.

The full bundled corpus is large; the lexical-index tests build over a
handful of real extracted triples copied into a temp directory so a build
is fast while still exercising the real walker, chunker, and FTS5 path
against authentic BOE text.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..lexical_index import bundled_corpus_html_root

# Real bundled corpus stems with extracted triples. ley-58-2003-art-27 is
# the recargo-por-declaración-extemporánea article (LGT art. 27), the
# recall anchor several tests search for.
SAMPLE_STEMS = (
    "ley-58-2003-art-27",
    "ley-27-2014-art-15",
    "ley-12-2002",
)


def build_sample_corpus(destination: Path) -> Path:
    """Copy the sample extracted triples into ``destination`` and return it."""
    source = bundled_corpus_html_root()
    destination.mkdir(parents=True, exist_ok=True)
    for stem in SAMPLE_STEMS:
        for suffix in (".html.extracted.json", ".html.extracted.md"):
            origin = source / f"{stem}{suffix}"
            if origin.is_file():
                shutil.copy2(origin, destination / origin.name)
    return destination
