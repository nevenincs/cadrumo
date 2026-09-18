"""Shared helpers for registry gate tests."""

from __future__ import annotations

from pathlib import Path

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.calculations.registry.snapshot import collect_snapshot_ref_ids

from ..compiler.loader import load_registry_tree
from ..compiler.validator import _runtime_legal_reference_ids


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


def _m130_definition() -> ModeloDefinition:
    modelos, _full = load_registry_tree(bundled_path("registry", "aeat"))
    return next(item for item in modelos if str(item.id) == "130")


def _m130_declared_reference_ids(modelo: ModeloDefinition) -> tuple[set[str], set[str]]:
    legal_ids: set[str] = {str(ref) for ref in modelo.legal_refs}
    source_ids: set[str] = {str(ref) for ref in modelo.source_refs}
    for revision in modelo.revisions.values():
        revision_legal, revision_sources = collect_snapshot_ref_ids(modelo, revision)
        legal_ids.update(str(ref) for ref in revision_legal)
        source_ids.update(str(ref) for ref in revision_sources)
    return legal_ids, source_ids


def _catalogue_carried_reference_ids(catalogues: RegistryCatalogues) -> tuple[frozenset[str], frozenset[str]]:
    """Return the legal and source ids the catalogues themselves cite, modelo aside."""
    legal = set(_runtime_legal_reference_ids(catalogues.runtime))
    sources: set[str] = set()
    for fact in catalogues.facts.facts.values():
        for variant in fact.variants:
            legal.update(str(ref) for ref in variant.legal_refs)
            sources.update(str(ref) for ref in variant.source_refs)
            sources.update(str(citation.source_ref) for citation in variant.source_citations)
    return frozenset(legal), frozenset(sources)


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
    modelo = _m130_definition()
    legal_ids, _source_ids = _m130_declared_reference_ids(modelo)
    # The catalogues carry more than one modelo's declarations: the runtime
    # tables and the governed facts cite their own legal and source identities,
    # and catalogue validation checks those whichever modelo is being validated.
    # Narrowing to the modelo's refs alone left them dangling, so every case
    # here failed on "references unknown legal id" -- again an artefact of the
    # isolation rather than a defect in what it validates. The narrowing stays
    # real for the MODELO's own refs, which is what these gates isolate.
    carried_legal, _carried_sources = _catalogue_carried_reference_ids(catalogues)
    legal_ids = legal_ids | carried_legal
    return catalogues.model_copy(
        update={
            "legal": {ref_id: catalogues.legal[ref_id] for ref_id in sorted(legal_ids) if ref_id in catalogues.legal},
            # The SOURCE map stays whole. These gates validate against the real
            # bundled source root, and the source-side checks walk that root:
            # the semantic-annotation check reads every annotation sidecar under
            # it and requires a declared source target for each. A narrowed map
            # contradicts the root the validator is reading, so it reported
            # annotations of other modelos as untargeted. The legal narrowing
            # above is what these gates isolate, and it still holds.
        },
    )
