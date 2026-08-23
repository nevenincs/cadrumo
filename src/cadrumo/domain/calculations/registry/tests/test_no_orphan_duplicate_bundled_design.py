"""No bundled record design is an unclaimed byte-identical copy of another.

WHAT THIS CATCHES. The design corpus is addressed by FILENAME -- the per-modelo
``manifest.json`` lists names, and each ``SourceReference`` carries a
``corpus_path``. A second copy of the same bytes under a slightly different name
is therefore invisible to both: it is not in the manifest, no source cites it,
and nothing reads it. It still ships in the wheel, and it still shows up on the
unregistered-design worklist as though a design were waiting to be registered.

Three such copies shipped in modelo 303, each a truncated-name twin of a
registered file -- ``...-381-kb-x.xlsx`` beside ``...-381-kb-xls.xlsx``,
``...-4t-de-20.xlsx`` beside ``...-4t-de-2018.xlsx``, ``...-27-0.xlsx`` beside
``...-27-04.xlsx``. All three were byte-identical to the file the manifest
listed, so registering them would have minted a second source id for one design
rather than closing a gap. They were stale download artifacts.

WHY BYTE-IDENTICAL IS THE RIGHT TEST, AND WHY CLAIMED-NESS IS THE OTHER HALF.
Two AEAT editions of one modelo legitimately differ by a few bytes and both
deserve registration, so similarity of NAME proves nothing and is not consulted.
Equally, two files with the same bytes are not automatically a defect: what
makes a copy an orphan is that no manifest entry and no source reference claim
it, while a twin carrying the same bytes IS claimed. Both halves are required,
so a genuinely-cited duplicate does not trip this.

WHAT IS NOT ASSERTED. An unclaimed file with UNIQUE bytes is out of scope -- it
may be a design awaiting registration, which is the unregistered-design gate's
subject, not this one.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from .....core.resources import bundled_path
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN_SUFFIXES = {".pdf", ".xls", ".xlsx"}
#: Below this the corpus was not walked and the check would pass vacuously.
_MINIMUM_DESIGNS = 100


def _design_root() -> Path:
    return bundled_path("corpus", "aeat_official", "disenos_registro")


def _claimed_paths() -> set[str]:
    _, catalogues = _committed_registry_tree()
    return {Path(str(s.corpus_path)).as_posix() for s in catalogues.sources.values()}


def _walk_designs() -> list[Path]:
    return [path for path in sorted(_design_root().rglob("files/*")) if path.suffix.lower() in _DESIGN_SUFFIXES]


def _orphan_duplicates() -> list[tuple[str, str]]:
    """Return ``(modelo dir, filename)`` for every unclaimed byte-twin."""
    claimed = _claimed_paths()
    orphans: list[tuple[str, str]] = []
    by_modelo: dict[Path, list[Path]] = {}
    for path in _walk_designs():
        by_modelo.setdefault(path.parent.parent, []).append(path)

    for modelo_dir, files in by_modelo.items():
        manifest = modelo_dir / "manifest.json"
        listed = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
        digests: dict[str, list[Path]] = {}
        for path in files:
            digests.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(), []).append(path)
        for twins in digests.values():
            if len(twins) < 2:
                continue  # unique bytes are the other gate's subject
            for path in twins:
                relative = path.relative_to(bundled_path()).as_posix()
                if path.name not in listed and relative not in claimed:
                    orphans.append((modelo_dir.name, path.name))
    return orphans


def test_no_bundled_design_is_an_unclaimed_byte_identical_copy() -> None:
    designs = _walk_designs()
    assert len(designs) >= _MINIMUM_DESIGNS, (
        f"only {len(designs)} bundled designs walked; the corpus was not read and "
        "this check would pass without examining anything"
    )

    orphans = _orphan_duplicates()

    assert not orphans, (
        "these bundled design files duplicate the bytes of a file the manifest "
        "already lists, while being claimed by no manifest entry and no source. "
        "Delete them rather than registering them -- registering would mint a "
        "second source id for one design: " + ", ".join(f"{modelo}/{name}" for modelo, name in sorted(orphans))
    )


def test_a_claimed_duplicate_is_not_reported() -> None:
    """Claimed-ness is load-bearing, so its effect is asserted directly.

    Without it the check would degrade into "no two bundled files share bytes",
    which would fire on a legitimately-cited duplicate and push an author toward
    deleting a file something reads.
    """
    claimed = _claimed_paths()
    assert claimed, "no source declares a corpus path; the claim set is empty"

    reported = {name for _, name in _orphan_duplicates()}
    claimed_names = {Path(path).name for path in claimed}

    assert not (reported & claimed_names), (
        f"a file a source cites was reported as an orphan copy: {sorted(reported & claimed_names)}"
    )
