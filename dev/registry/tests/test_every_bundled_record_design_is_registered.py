"""Every bundled record-design file must be registered by a ``SourceReference``.

A file can sit in ``disenos_registro/`` and never be enrolled in the shared
sources catalogue: nothing on disk forces a ``[sources."..."]`` entry to exist,
so an unregistered design is invisible to ``resolve_record_design_binary``,
to hash-pin verification, and to every downstream completeness gate that only
ever walks the catalogue rather than the corpus. The gap is silent by
construction -- the file is real, it opens, it looks correct, and nothing
fails until an operator or a later audit goes looking for it by name and finds
nothing pointing at it.

THE ENUMERATION IS INDEPENDENT, deliberately mirroring the sibling gate in
``test_every_bundled_design_is_read_or_reported``: it walks the corpus root
recursively for anything with a parseable suffix and asks the sources
catalogue nothing about what it already knows, so it cannot inherit a
narrowing the catalogue or its consumers acquired.

NO COUNT IS PINNED. The number of registered and unregistered files moves as
the corpus grows and as entries are authored. Gating on a tally would encode
this moment and detect nothing afterward.

THIS GATE IS EXPECTED TO LAND RED. Per the standing project directive, a red
signal over a genuine unregistered-file population is the correct report --
scoping this gate to only the currently-registered set would make it pass
vacuously and remove the exact visibility it exists to provide.

WHICH CATALOGUE COUNTS AS "REGISTERED" is the whole question, and this module
previously read the wrong one. ``registry_tree`` is the PUBLISHED view, and it
carries only the source references that published modelos cite -- the sibling
``authored_catalogues`` docstring states exactly that, and exists for checks
about the committed tree's own integrity. But "does a sources entry exist for
this file" is an authoring-tree fact, and the published projection cannot
answer it: a source that is authored, hash-pinned and correct, but not cited by
any published modelo, is simply absent there.

Read against the published view this gate reported 91 of 219 files
unregistered. Read against the authored tree it reports 2. The difference was
not corpus debt; every one of those files has a committed sources entry
(``aeat-dr-200-2010`` in ``legal/is.toml`` names
``modelo_200/files/02-200-ejercicio-2010-472-kb-pdf.pdf``, which the published
reading called unregistered). A worklist that is overwhelmingly false positives
buries the real entries inside it, which is the same loss of visibility this
gate exists to prevent, arriving through a measurement error instead of a
narrowing.

The corpus enumeration below is UNCHANGED and still independent. What changed
is only which catalogue it is compared against, and it changed towards the one
that can answer the question.

ONE POPULATION IS OUT OF SCOPE, and it is out of scope because a registration
would be false rather than because the gap is acceptable. A ``SourceReference``
states a retrieval -- the URL, the date, the digest -- and those come off the
capture record the ingest harness wrote. A payload that has no capture row has
none of them, so authoring an entry for it would assert an acquisition nobody
recorded. The corpus sync module already declares exactly that population and
checks it for equality, so it cannot grow quietly, and this gate reads that
declaration rather than keeping a second list of its own.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from dev.corpus.sync_aeat_record_design_corpus import UNATTESTED_CORPUS_FILES

from .catalogue_verification_support import authored_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_ROOT_PARTS = ("corpus", "aeat_official", "disenos_registro")
#: Suffixes a bundled record-design file ships under. Declared here rather than
#: imported from the sibling read/report gate so a suffix quietly dropped there
#: does not silently narrow this gate's enumeration too.
_DESIGN_SUFFIXES = frozenset({".pdf", ".xls", ".xlsx", ".xlsm"})


def _bundled_design_files() -> tuple[Path, ...]:
    """Every design-suffixed file under ``disenos_registro/``, enumerated independently."""
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    return tuple(
        path
        for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES)
        if path.suffix.lower() in _DESIGN_SUFFIXES
    )


def _registered_corpus_paths() -> frozenset[str]:
    return frozenset(source.corpus_path for source in authored_catalogues().sources.values())


def test_the_corpus_enumeration_reaches_designs_across_many_modelos() -> None:
    """Anti-vacuity: a gate over an empty or one-modelo corpus proves nothing."""
    files = _bundled_design_files()
    assert files, "no bundled design file was enumerated at all; the corpus path or suffix set has moved"
    modelos = {path.relative_to(bundled_path(*_DESIGN_ROOT_PARTS)).parts[0] for path in files}
    assert len(modelos) > 10, f"only {len(modelos)} modelo director(ies) reached; the walk has narrowed"


def _unattested_corpus_paths() -> frozenset[str]:
    """Corpus files the ingest census already declares as named by no manifest.

    A ``SourceReference`` states where a file came from and when it was
    retrieved, and those fields come off the capture record the ingest harness
    wrote. A payload with no capture row has none of them, so registering it
    would mean asserting a retrieval nobody recorded -- which is worse than the
    gap, because it looks like evidence.

    That population is not invented here. The corpus sync module declares it as
    a census it checks for EQUALITY, so a newly unattested file fails there and
    so does dropping one from the census without attesting it. Reading that
    declaration keeps one home for the fact instead of a second allowlist that
    could drift away from it.
    """
    prefix = "/".join(_DESIGN_ROOT_PARTS)
    return frozenset(f"{prefix}/{relative}" for relative in UNATTESTED_CORPUS_FILES)


def test_the_unattested_census_still_names_only_bundled_design_files() -> None:
    """The exemption cannot outlive what it exempts.

    A census entry naming a file that is gone, or one outside this gate's own
    enumeration, would silently widen the exemption while reading as though it
    covered the same single case.
    """
    enumerated = {path.relative_to(bundled_path()).as_posix() for path in _bundled_design_files()}

    stale = sorted(_unattested_corpus_paths() - enumerated)
    assert not stale, f"the unattested corpus census names files this gate does not enumerate: {stale}"


def test_every_bundled_record_design_file_is_registered_by_a_source() -> None:
    """THE WORKLIST. Landed red deliberately if a genuine gap exists; the gap is the finding.

    A file under ``disenos_registro/`` that no ``SourceReference.corpus_path``
    names is unregistered: it cannot be hash-pin verified, it cannot be
    resolved by :func:`resolve_record_design_binary`, and no consumer of the
    sources catalogue can ever see it. Each entry below names the modelo
    directory and the filename so the gap can be closed by authoring the
    missing ``[sources."..."]`` entry, never by narrowing this enumeration.
    """
    root = bundled_path(*_DESIGN_ROOT_PARTS)
    registered = _registered_corpus_paths()
    unattested = _unattested_corpus_paths()
    unregistered = [
        path.relative_to(bundled_path()).as_posix()
        for path in _bundled_design_files()
        if path.relative_to(bundled_path()).as_posix() not in registered
        and path.relative_to(bundled_path()).as_posix() not in unattested
    ]
    assert not unregistered, (
        f"{len(unregistered)} of {len(_bundled_design_files())} bundled record-design files under "
        f"{root.relative_to(bundled_path())} carry no registered SourceReference. Each is real corpus "
        "inventory no catalogue entry, hash-pin, or resolver can see:\n  " + "\n  ".join(unregistered)
    )
