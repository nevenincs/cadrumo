"""Shared helpers for registry gate tests."""

from __future__ import annotations

from pathlib import Path

from .._schema import RegistryCatalogues

_M130_LEGAL_REF_IDS = frozenset(
    {
        "ley-35-2006:art-27",
        "ley-35-2006:art-28",
        "ley-35-2006:art-30",
        "ley-35-2006:art-99",
        "orden-eha-672-2007:art-1",
        "rd-439-2007:art-95",
        "rd-439-2007:art-110",
        "rd-439-2007:art-109",
    },
)
_M130_SOURCE_REF_IDS = frozenset({"aeat-dr-130-2019-v12", "aeat-modelo-130-instructions"})


def fragment_declaring(directory: Path, anchor: str) -> Path:
    """The one fragment under *directory* whose text contains *anchor*.

    A source-text mutation has to name the file it rewrites, and naming it by
    FILENAME rots the moment a section is re-fragmented: two M390 mutation gates
    addressed ``0001-export_layouts.toml`` and went stale when the layout split
    into ``0002-export_layouts.part-00N.toml``, refusing with "the mutation
    target string was not found" rather than passing vacuously. Resolving by
    CONTENT survives the next split, and the exactly-one assertion keeps the
    resolution honest in both directions.

    Zero matches means the anchor genuinely no longer exists, which is a real
    staleness the caller must diagnose rather than paper over -- do NOT respond
    by pointing the anchor at a nearby string, because a mutation retargeted at
    a convenient neighbour mutates something the gate was never about. More than
    one match means the caller's ``replace(..., 1)`` would silently pick the
    first, so the mutation would no longer be the one the test describes.

    Args:
        directory: The section directory holding the fragments to search.
        anchor: The exact source text the caller intends to rewrite.

    Returns:
        The single fragment containing *anchor*.
    """
    matches = sorted(path for path in directory.glob("*.toml") if anchor in path.read_text(encoding="utf-8"))
    if not matches:
        msg = (
            f"no fragment under {directory.name} declares {anchor!r} -- the gate is stale, diagnose before re-anchoring"
        )
        raise AssertionError(msg)
    if len(matches) > 1:
        named = ", ".join(path.name for path in matches)
        msg = f"{anchor!r} appears in {len(matches)} fragments ({named}); a single-occurrence mutation is ambiguous"
        raise AssertionError(msg)
    return matches[0]


def catalogues_for_m130_gate_tests(catalogues: RegistryCatalogues) -> RegistryCatalogues:
    return catalogues.model_copy(
        update={
            "legal": {ref_id: catalogues.legal[ref_id] for ref_id in _M130_LEGAL_REF_IDS},
            "sources": {ref_id: catalogues.sources[ref_id] for ref_id in _M130_SOURCE_REF_IDS},
        },
    )
