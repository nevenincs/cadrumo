"""A transcription must never be mistaken for a capture.

``corpus/normatives/pdf/`` holds two kinds of file under one directory and one
registry row shape. Three are BOE PDFs downloaded whole, where the bundled
bytes are the bytes the publisher served and the ``sha256`` on the row verifies
the document. Nine are plain-text transcriptions of a form annex, typed here
because the annex exists only as a scanned image: their ``sha256`` pins the
transcription against later edits and verifies nothing about the original, and
no address would ever serve those bytes.

Nothing in the catalogue distinguishes them -- both carry ``sha256``, ``bytes``,
``retrieved_at`` and ``source_url`` -- so the distinction lives in
``PROVENANCE.md`` beside the files. That makes the record load-bearing, and a
record that silently falls behind the directory is worse than none: it reads as
though every file in the tree has been classified when the newest one has not.

This gate holds the record to the directory in both directions. It does not
re-verify digests, which the registry already pins, and it does not classify
anything itself -- deciding whether a new file was downloaded or typed is a
judgement made with the source open, and recording it is the author's act.

Run with::

    uv run --no-sync pytest dev/corpus/tests/test_normatives_pdf_provenance_record.py -q
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ...registry.conformance.registry_schema_support import committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TREE_PARTS = ("corpus", "normatives", "pdf")
_TREE_PREFIX = "/".join(_TREE_PARTS) + "/"
_RECORD_NAME = "PROVENANCE.md"
_CAPTURES_HEADING = "## Captures"
_TRANSCRIPTIONS_HEADING = "## Transcriptions"
#: The leading backticked filename and the ``Bytes`` column are all this gate
#: reads; the prose columns are for people.
_ROW = re.compile(r"^\|\s*`(?P<name>[^`]+)`\s*\|(?P<rest>.*)\|\s*$")
_BYTES_HEADING = "bytes"


def _tree() -> Path:
    return bundled_path(*_TREE_PARTS)


def _bundled_files() -> tuple[Path, ...]:
    return tuple(sorted(path for path in _tree().iterdir() if path.is_file() and path.name != _RECORD_NAME))


def _bytes_column(cells: list[str]) -> int | None:
    """Locate the ``Bytes`` column from a table's own header row.

    Read by heading rather than by position or by shape: the two tables order
    their columns differently, and the transcription table's ``Modelo`` column
    is a bare integer too, so "the first numeric cell" silently reads 117 as a
    byte count.
    """
    for index, cell in enumerate(cells):
        if cell.strip().casefold() == _BYTES_HEADING:
            return index
    return None


def _record_sections() -> dict[str, dict[str, int | None]]:
    """Return each table's rows as ``{filename: declared bytes or None}``."""
    text = (_tree() / _RECORD_NAME).read_text(encoding="utf-8")
    sections: dict[str, dict[str, int | None]] = {_CAPTURES_HEADING: {}, _TRANSCRIPTIONS_HEADING: {}}
    current: str | None = None
    column: int | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in sections:
            current, column = stripped, None
            continue
        if stripped.startswith("## ") and stripped not in sections:
            current, column = None, None
            continue
        if current is None or not stripped.startswith("|"):
            continue
        cells = stripped.strip("|").split("|")
        if column is None:
            column = _bytes_column(cells)
            continue
        match = _ROW.match(stripped)
        if match is None:
            continue
        declared = cells[column].strip() if 0 <= column < len(cells) else ""
        sections[current][match.group("name")] = int(declared) if declared.isdigit() else None
    return sections


def test_each_table_declares_a_bytes_column() -> None:
    """Without it the length comparison below would pass over an empty mapping."""
    text = (_tree() / _RECORD_NAME).read_text(encoding="utf-8")
    for heading in (_CAPTURES_HEADING, _TRANSCRIPTIONS_HEADING):
        body = text.split(heading, 1)[1]
        header = next(line for line in body.splitlines() if line.strip().startswith("|"))
        assert _bytes_column(header.strip().strip("|").split("|")) is not None, (
            f"the table under {heading!r} has no 'Bytes' column, so no length can be compared"
        )


def test_the_record_and_the_directory_are_both_populated() -> None:
    """Anti-vacuity: an empty tree or an unparsed record would satisfy every comparison below."""
    files = _bundled_files()
    assert len(files) > 5, f"only {len(files)} file(s) enumerated; the corpus tree or its layout has moved"

    sections = _record_sections()
    assert sections[_CAPTURES_HEADING], "the provenance record lists no captures; its table shape has moved"
    assert sections[_TRANSCRIPTIONS_HEADING], "the provenance record lists no transcriptions; its table shape has moved"


def test_every_bundled_file_is_classified_exactly_once() -> None:
    """A file in neither table is unclassified; a file in both asserts two origins."""
    sections = _record_sections()
    captures = set(sections[_CAPTURES_HEADING])
    transcriptions = set(sections[_TRANSCRIPTIONS_HEADING])
    bundled = {path.name for path in _bundled_files()}

    unclassified = sorted(bundled - captures - transcriptions)
    assert not unclassified, (
        f"{len(unclassified)} file(s) under {_TREE_PREFIX} are in neither table of {_RECORD_NAME}. "
        "Record whether each was downloaded or typed, which is the one thing the catalogue row "
        "cannot say:\n  " + "\n  ".join(unclassified)
    )

    both = sorted(captures & transcriptions)
    assert not both, f"file(s) listed as both a capture and a transcription: {both}"


def test_the_record_names_no_file_that_has_left_the_tree() -> None:
    """A row outliving its file attests an origin for bytes that are gone."""
    sections = _record_sections()
    listed = set(sections[_CAPTURES_HEADING]) | set(sections[_TRANSCRIPTIONS_HEADING])
    bundled = {path.name for path in _bundled_files()}

    stale = sorted(listed - bundled)
    assert not stale, f"{_RECORD_NAME} names file(s) no longer in the tree: {stale}"


def test_each_declared_length_still_matches_its_file() -> None:
    """The cheapest evidence that the record was updated with the bytes it describes.

    The digest is pinned on the registry row and is not re-checked here. What
    this catches is the record being left behind when a file is re-typed or
    re-downloaded -- the case where the row keeps describing the previous bytes.
    """
    sections = _record_sections()
    declared = {**sections[_CAPTURES_HEADING], **sections[_TRANSCRIPTIONS_HEADING]}
    tree = _tree()

    drifted = sorted(
        f"{name}: record {size} vs file {(tree / name).stat().st_size}"
        for name, size in declared.items()
        if size is not None and (tree / name).is_file() and (tree / name).stat().st_size != size
    )

    assert not drifted, f"{_RECORD_NAME} states a length its file no longer has:\n  " + "\n  ".join(drifted)


def test_every_bundled_file_is_cited_by_a_source_row() -> None:
    """Bytes nothing cites are unpinned: no digest guards them and no consumer needs them."""
    _modelos, catalogues = committed_registry_tree()
    cited = {
        source.corpus_path.removeprefix(_TREE_PREFIX)
        for source in catalogues.sources.values()
        if source.corpus_path.startswith(_TREE_PREFIX)
    }

    uncited = sorted({path.name for path in _bundled_files()} - cited)

    assert not uncited, (
        f"{len(uncited)} file(s) under {_TREE_PREFIX} are cited by no source row, so nothing pins "
        "their digest:\n  " + "\n  ".join(uncited)
    )
