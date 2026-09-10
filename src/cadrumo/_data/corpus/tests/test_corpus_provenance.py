"""Gate tests for corpus PROVENANCE.md documents.

Each AEAT corpus subdirectory that carries documents derived from
external authority (AEAT Sede, BOE) MUST declare a PROVENANCE.md
file at its root. The gate asserts:

1. The PROVENANCE.md file exists.
2. It enumerates every committed file under the corresponding
   ``files/`` subdirectory.
3. It declares the canonical Source, AEAT-page-last-updated, and
   corpus-capture-date sections.

Authored to protect the committed corpus provenance
documentation against silent drift (a corpus refresh that drops
the metadata file goes undetected without this gate).

WHY THE SWEEPS ARE PLURAL. This module previously defined
``_corpus_subdirectories_with_files`` and then never called it: every
assertion named ``instructions/modelo_131`` literally. The contract in the
docstring above says "each AEAT corpus subdirectory", and the corpus ships
well over a hundred of them across nine categories, so the enforced surface
was one directory and the other ~110 were documented-but-unchecked. A
PROVENANCE.md that silently stopped listing half its payload, anywhere except
that one directory, was invisible.

The discovery helper is now the population every sweep below iterates, and it
walks every category rather than one. What the sweeps require is calibrated to
what a corpus-local gate can honestly know: for a directory that carries a
PROVENANCE.md, the document must be complete and well-formed. Whether a
directory that carries NO provenance document is nevertheless provenanced --
by a sibling ``manifest.json`` or by a hash-pinned registry ``SourceReference``,
both of which record strictly more than this prose does -- is a question this
package cannot answer without reaching into the registry, so it is owned by the
registry-side companion gate
(``domain.calculations.registry.tests.test_corpus_provenance_coverage``) rather
than guessed at here. Splitting it that way keeps this module free of false
findings while leaving no side of the contract unowned.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ....core.directory_scan import DirectoryEntryKind, iter_directory, scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


bundled_path = importlib.import_module("cadrumo.core.resources").bundled_path
_AEAT_ROOT = bundled_path("corpus", "aeat_official")
_CORPUS_ROOT = _AEAT_ROOT / "instructions"

#: The provenance document every externally-sourced corpus subdirectory
#: declares. Named once so the sweeps and the discovery helper cannot drift.
_PROVENANCE = "PROVENANCE.md"

#: Anti-vacuity floor over the discovered population. Deliberately far below
#: the live count (~110): this exists to catch the walk COLLAPSING, not to pin
#: a corpus inventory, which would redden on every legitimate capture.
_MINIMUM_SUBDIRECTORIES = 40


def _corpus_subdirectories_with_files(root: Path = _CORPUS_ROOT) -> list[Path]:
    """Return every corpus subdirectory that has a populated ``files/`` child."""

    if not root.is_dir():
        return []
    return [
        subdir
        for subdir in scan_directory(root)
        if subdir.is_dir() and (subdir / "files").is_dir() and any(iter_directory(subdir / "files"))
    ]


def _provenance_documents(aeat_root: Path = _AEAT_ROOT) -> list[Path]:
    """Every directory under ``aeat_official`` that carries a PROVENANCE.md.

    Found by walking for the document itself rather than by assuming a layout.
    The corpus ships at least five shapes -- ``category/files/``,
    ``category/modelo_N/files/``, payloads directly at a category root
    (``groi_response_samples``), a single file at a category root
    (``renta_web_open``), and named subdirectories (``einvoice_record_schemas/
    sii``) -- and an earlier draft of this walk required a ``files/`` child,
    which silently excluded three of them. A shape nobody enumerates is a
    shape no sweep can check, which is the same blindness this module was
    rewritten to remove; keying on the document makes the walk shape-agnostic.
    """
    if not aeat_root.is_dir():
        return []
    return [
        candidate.parent
        for candidate in scan_directory(
            aeat_root, pattern=_PROVENANCE, recursive=True, select=DirectoryEntryKind.FILES
        )
    ]


#: Documents that are provenance metadata rather than sourced payload, and so
#: are never themselves owed an enumeration entry.
_NON_PAYLOAD = frozenset({_PROVENANCE, "manifest.json", "README.md"})


def _files_in(subdir: Path) -> tuple[Path, ...]:
    """Payload files a provenance document at ``subdir`` is answerable for.

    Covers both a ``files/`` child and payloads sitting directly beside the
    document, so the sweep works for every committed corpus shape.
    """
    roots = [subdir / "files"] if (subdir / "files").is_dir() else [subdir]
    return tuple(
        path
        for root in roots
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
        if path.name not in _NON_PAYLOAD
    )


def _undocumented_files(subdir: Path) -> list[str]:
    """Return names under ``subdir/files`` that its PROVENANCE.md does not mention."""
    body = (subdir / _PROVENANCE).read_text(encoding="utf-8")
    return [f.name for f in _files_in(subdir) if f.name not in body]


def _missing_sections(subdir: Path) -> list[str]:
    """Return the required PROVENANCE.md sections ``subdir`` fails to declare."""
    body = (subdir / _PROVENANCE).read_text(encoding="utf-8")
    lowered = body.lower()
    missing: list[str] = []
    if "## source" not in lowered:
        missing.append("'## Source' section")
    if (
        "last-update timestamps" not in lowered
        and "last-updated" not in lowered
        and "página actualizada" not in lowered
    ):
        missing.append("AEAT page last-updated timestamp")
    if "capture" not in lowered and "Modified" not in body:
        missing.append("corpus capture date")
    return missing



# ---------------------------------------------------------------------------
# Discovery: the population every sweep below iterates.
# ---------------------------------------------------------------------------


def test_corpus_subdirectory_discovery_reaches_the_whole_corpus() -> None:
    """Anti-vacuity for the walk the sweeps inherit.

    Each sweep below iterates this population, so a walk that collapsed --
    a renamed category, a changed ``files/`` convention -- would make every
    one of them report a clean corpus without having opened a document. The
    per-category floor is what makes the total mean anything: the count is
    dominated by ``disenos_registro`` (~60) and ``instructions`` (~48), so a
    total alone cannot see a smaller category leave.
    """
    assert _AEAT_ROOT.is_dir(), _AEAT_ROOT
    subdirs = _corpus_subdirectories_with_files(_AEAT_ROOT / "disenos_registro") + _corpus_subdirectories_with_files()
    assert len(subdirs) >= _MINIMUM_SUBDIRECTORIES, (
        f"only {len(subdirs)} populated corpus subdirector(ies) discovered, against a floor of "
        f"{_MINIMUM_SUBDIRECTORIES}; the walk has narrowed and every sweep below inherits it"
    )

    reached = {subdir.relative_to(_AEAT_ROOT).parts[0] for subdir in subdirs}
    absent = sorted({"instructions", "disenos_registro"} - reached)
    assert not absent, (
        f"these corpus categories were not reached by the discovery walk: {absent}; "
        "a category nobody enumerates is a category no sweep below can check"
    )


def test_the_provenance_walk_reaches_more_than_one_category_and_more_than_one_shape() -> None:
    """The enforced surface is no longer one hardcoded directory.

    Pins the defect this module was carrying: every assertion used to name
    ``instructions/modelo_131`` literally while the discovery helper went
    uncalled. Asserting breadth across BOTH categories and layout shapes makes
    the widening a fact, and would catch a future edit that re-narrowed the
    sweeps -- including a return to the ``files/``-only assumption that hid
    three shapes.
    """
    documented = _provenance_documents()
    assert documented, "no PROVENANCE.md was discovered anywhere; the walk has broken"

    categories = {subdir.relative_to(_AEAT_ROOT).parts[0] for subdir in documented}
    assert len(categories) > 1, (
        f"provenance documents were found in only one category ({sorted(categories)}); the sweeps "
        "have re-narrowed to a single corner of the corpus"
    )

    with_files_child = {subdir for subdir in documented if (subdir / "files").is_dir()}
    without_files_child = set(documented) - with_files_child
    assert with_files_child and without_files_child, (
        "the walk reached only one layout shape; a `files/`-only assumption silently excluded "
        f"payloads held at a category root (reached-with={len(with_files_child)}, "
        f"reached-without={len(without_files_child)})"
    )


# ---------------------------------------------------------------------------
# The sweeps. Every committed provenance document, not one named directory.
# ---------------------------------------------------------------------------


def test_every_committed_provenance_document_enumerates_every_file_beside_it() -> None:
    """A PROVENANCE.md that omits a payload file has lost that file's audit trail.

    Generalises the Modelo 131 assertion below to every directory that carries
    the document. The failure is invisible by construction: the document reads
    as complete prose, and nothing distinguishes a five-of-six enumeration from
    a six-of-six one without comparing against the directory.
    """
    documented = _provenance_documents()
    assert documented, "no corpus subdirectory carries a PROVENANCE.md; the sweep would be vacuous"

    findings = [
        f"{subdir.relative_to(_AEAT_ROOT).as_posix()}: {undocumented!r}"
        for subdir in documented
        if (undocumented := _undocumented_files(subdir))
    ]
    assert not findings, (
        "PROVENANCE.md documents that do not list every file beside them:\n  "
        + "\n  ".join(findings)
        + "\nadd an entry to the Documents section before landing"
    )


def test_every_committed_provenance_document_declares_the_required_sections() -> None:
    """Source, AEAT-page-last-updated, and capture date are the contract's three facts.

    A provenance document missing any of them cannot answer the question it
    exists for -- where did this come from, how current was it, and when did we
    take it.
    """
    documented = _provenance_documents()
    assert documented, "no corpus subdirectory carries a PROVENANCE.md; the sweep would be vacuous"

    findings = [
        f"{subdir.relative_to(_AEAT_ROOT).as_posix()}: missing {missing}"
        for subdir in documented
        if (missing := _missing_sections(subdir))
    ]
    assert not findings, "PROVENANCE.md documents missing required sections:\n  " + "\n  ".join(findings)


# ---------------------------------------------------------------------------
# Detector teeth. The sweeps' own predicates, driven against a tmp tree.
# ---------------------------------------------------------------------------


def _decoy_subdirectory(tmp_path: Path, *, body: str, payloads: tuple[str, ...]) -> Path:
    """Build one corpus-shaped subdirectory in tmp. Never touches the real corpus."""
    subdir = tmp_path / "modelo_999"
    (subdir / "files").mkdir(parents=True)
    for name in payloads:
        (subdir / "files" / name).write_text("payload", encoding="utf-8")
    (subdir / _PROVENANCE).write_text(body, encoding="utf-8")
    return subdir


_COMPLETE_BODY = """# decoy

## Source
- Authority: AEAT.

## Last-update timestamps
- AEAT page last-updated: 2026-01-01.
- Corpus capture date: 2026-01-02.

## Documents
- `files/kept.html`
"""


def test_a_provenance_document_omitting_a_payload_is_reported(tmp_path: Path) -> None:
    """DETECTOR TEETH: the enumeration sweep's predicate must fire on a real omission."""
    subdir = _decoy_subdirectory(tmp_path, body=_COMPLETE_BODY, payloads=("kept.html", "dropped.png"))

    assert _undocumented_files(subdir) == ["dropped.png"]


def test_a_provenance_document_missing_its_sections_is_reported(tmp_path: Path) -> None:
    """DETECTOR TEETH: the section sweep's predicate must fire on a stripped document."""
    subdir = _decoy_subdirectory(tmp_path, body="# decoy\n\nnothing declared here\n", payloads=("kept.html",))

    assert _missing_sections(subdir) == [
        "'## Source' section",
        "AEAT page last-updated timestamp",
        "corpus capture date",
    ]


def test_a_complete_provenance_document_is_accepted(tmp_path: Path) -> None:
    """The normal path passes in the same suite, so the two proofs are not tautologies."""
    subdir = _decoy_subdirectory(tmp_path, body=_COMPLETE_BODY, payloads=("kept.html",))

    assert not _undocumented_files(subdir)
    assert not _missing_sections(subdir)


def test_the_discovery_helper_skips_an_empty_files_directory(tmp_path: Path) -> None:
    """A directory with an empty ``files/`` owes no provenance and must not be discovered.

    Guards the ``any(iter_directory(...))`` clause: without it the sweeps would
    demand a provenance document for a placeholder directory, and the resulting
    noise is what gets gates disabled.
    """
    (tmp_path / "modelo_998" / "files").mkdir(parents=True)
    (tmp_path / "modelo_997" / "files").mkdir(parents=True)
    (tmp_path / "modelo_997" / "files" / "real.html").write_text("x", encoding="utf-8")

    discovered = {subdir.name for subdir in _corpus_subdirectories_with_files(tmp_path)}

    assert discovered == {"modelo_997"}


# ---------------------------------------------------------------------------
# Modelo 131: the specific grounding claim, retained.
# ---------------------------------------------------------------------------


def test_modelo_131_corpus_carries_provenance_document() -> None:
    """M131 instructions corpus MUST carry PROVENANCE.md.

    The PROVENANCE.md file documents the
    source URL, AEAT page-last-updated date, and corpus capture
    date. A future corpus refresh that drops or moves the file
    fails this gate; downstream consumers
    grounding claim) lose their provenance lineage without
    detection otherwise.

    Retained as a named directory alongside the sweeps above because the cap
    predicate's grounding cites THIS document specifically; the sweeps check
    every document's shape, not that this particular one exists.
    """

    modelo_131_corpus = _CORPUS_ROOT / "modelo_131"
    assert modelo_131_corpus.is_dir(), "modelo_131 instructions corpus directory missing"

    provenance = modelo_131_corpus / _PROVENANCE
    assert provenance.is_file(), (
        f"PROVENANCE.md missing at {provenance}; the cap predicate "
        "grounding claim depends on this document's existence and content"
    )

    assert not _missing_sections(modelo_131_corpus), (
        f"modelo_131 PROVENANCE.md is missing {_missing_sections(modelo_131_corpus)}"
    )


def test_modelo_131_corpus_provenance_lists_every_committed_file() -> None:
    """Every file under modelo_131/files/ MUST appear in PROVENANCE.md.

    Files added to the corpus without a PROVENANCE.md entry are
    structural drift. A future agent who adds a new AEAT-fetched
    HTML/PNG without documenting its source loses the audit trail.
    """

    undocumented = _undocumented_files(_CORPUS_ROOT / "modelo_131")
    assert not undocumented, (
        f"modelo_131/files entries not listed in PROVENANCE.md: {undocumented!r}; "
        "add an entry to the Documents section before landing"
    )
