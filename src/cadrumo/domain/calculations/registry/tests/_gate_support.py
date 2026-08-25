"""Shared helpers for registry gate tests."""

from __future__ import annotations

from pathlib import Path

from .....core.directory_scan import scan_directory
from .....core.resources import bundled_path
from ..loader import load_registry_tree
from ..schema import RegistryCatalogues
from ..snapshot import collect_snapshot_ref_ids


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
    matches = [
        path for path in scan_directory(directory, pattern="*.toml") if anchor in path.read_text(encoding="utf-8")
    ]
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
    """Narrow ``catalogues`` to exactly the refs modelo 130 declares.

    The modelo 130 gate tests validate against a NARROWED catalogue, so a rule
    leaning on an unrelated entry is caught. The narrowing was a hand-listed set
    of eight legal ids, and it went stale the moment modelo 130's applicability
    rule began citing `trlirnr-rdleg-5-2004:art-2`: every case then failed on
    "references unknown legal id", an artefact of the isolation rather than a
    defect in what it validates.

    Derived from the modelo's own declared refs instead. It stays a REAL
    narrowing -- the walk collects only what this modelo cites, never the whole
    catalogue -- and it cannot go stale, because a newly cited ref joins it the
    same way the modelo declares it.
    """
    modelos, _full = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(item for item in modelos if str(item.id) == "130")
    legal_ids: set[str] = {str(ref) for ref in modelo.legal_refs}
    source_ids: set[str] = {str(ref) for ref in modelo.source_refs}
    for revision in modelo.revisions.values():
        revision_legal, revision_sources = collect_snapshot_ref_ids(modelo, revision)
        legal_ids |= {str(ref) for ref in revision_legal}
        source_ids |= {str(ref) for ref in revision_sources}
    return catalogues.model_copy(
        update={
            "legal": {ref_id: catalogues.legal[ref_id] for ref_id in sorted(legal_ids) if ref_id in catalogues.legal},
            "sources": {
                ref_id: catalogues.sources[ref_id] for ref_id in sorted(source_ids) if ref_id in catalogues.sources
            },
        },
    )
