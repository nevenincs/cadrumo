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
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.directory_scan import DirectoryEntryKind, scan_directory
from .....core.resources.bundled_data import bundled_path
from ._catalogue_verification_support import _catalogues

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
    return frozenset(source.corpus_path for source in _catalogues().sources.values())


def test_the_corpus_enumeration_reaches_designs_across_many_modelos() -> None:
    """Anti-vacuity: a gate over an empty or one-modelo corpus proves nothing."""
    files = _bundled_design_files()
    assert files, "no bundled design file was enumerated at all; the corpus path or suffix set has moved"
    modelos = {path.relative_to(bundled_path(*_DESIGN_ROOT_PARTS)).parts[0] for path in files}
    assert len(modelos) > 10, f"only {len(modelos)} modelo director(ies) reached; the walk has narrowed"


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
    unregistered = [
        path.relative_to(bundled_path()).as_posix()
        for path in _bundled_design_files()
        if path.relative_to(bundled_path()).as_posix() not in registered
    ]
    assert not unregistered, (
        f"{len(unregistered)} of {len(_bundled_design_files())} bundled record-design files under "
        f"{root.relative_to(bundled_path())} carry no registered SourceReference. Each is real corpus "
        "inventory no catalogue entry, hash-pin, or resolver can see:\n  " + "\n  ".join(unregistered)
    )
