"""Modelo 390's recargo-de-equivalencia rate block is one block in every edition.

Apartado 5 of the annual return carries a base/cuota pair per recargo rate. Every
bundled Diseño de Registros labels each of those boxes the same way -- "5.
Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo
X% - Base imponible|Cuota" -- and no supported design moves a box out of that
block. So the block is one taxonomic unit: its rows belong to one ``section``,
and a row present in two editions carries the same ``section`` in both.

That matters beyond tidiness. ``section`` is what groups a casilla in the
calculation sheets and the work-review projection, so a row sectioned unlike its
siblings is presented under a heading of its own, and a row sectioned one way in
2023 and another in 2024 moves between headings for no legal reason.

Legal references are compared with the temporary-rate instruments set aside. A
Real Decreto-ley that sets a rate for part of one year belongs to the editions it
governs and to no others, so it is the one reference a row is expected to gain
and lose; everything else is the row's stable grounding and may not drift.

The oracle is the design text itself, read from the bundled corpus. The registry
side is read through the compiled typed authority, and the mutation proofs load
an isolated scratch copy through the real compiler -- no mocks, stubs, skips or
xfail, and the tracked tree is never written.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_registry_tree
from ._gate_support import mutate_declaration, scratch_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

#: The casillas of the rate block, addressed by the stem they share. The
#: rate-blind tier casillas below are the block's total layer, not rate rows.
_RATE_PREFIX = "iva.anual.repercutido.recargo.tipo-"
_TIER_CASILLAS = (
    "iva.anual.repercutido.recargo.general",
    "iva.anual.repercutido.recargo.reducido",
    "iva.anual.repercutido.recargo.super-reducido",
)
#: "5. Operaciones Reg. Gral. - Base Imponible y cuota - Recargo de equivalencia - Tipo 0,62% - Cuota [666]"
_DESIGN_ROW = re.compile(
    r"Base Imponible y cuota - Recargo de equivalencia - Tipo ([\d,]+)% - (Base imponible|Cuota) \[(\d+)\]"
)
#: A rate instrument whose vigencia covers part of a single exercise. It is the
#: reference a rate row legitimately gains in the edition it governs.
_TEMPORARY_RATE_PREFIX = "real-decreto-ley-"

_OUTLIER_SECTION = '["operaciones_regimen_general", "recargo_equivalencia"]'
_BLOCK_SECTION_SOURCE = '["iva", "anual", "devengado"]'
_TIPO_0_BASE = "iva.anual.repercutido.recargo.tipo-0.base"


def _bundled_definition() -> ModeloDefinition:
    return compiled_bundled_authority().modelo("390")


def _rate_rows(revision: ModeloRevision) -> dict[str, CasillaDefinition]:
    """The block's rate rows in one edition, keyed by lineage."""
    return {
        str(row.continuidad_id): row
        for row in revision.casillas
        if str(row.id).startswith(_RATE_PREFIX) and row.continuidad_id is not None
    }


def _editions_declaring_the_block(definition: ModeloDefinition) -> tuple[ModeloRevision, ...]:
    editions = tuple(revision for revision in ordered_revisions(definition) if _rate_rows(revision))
    assert editions, "no edition of modelo 390 declares a recargo rate row"
    return editions


def _design_boxes(revision: ModeloRevision) -> set[str]:
    """The recargo rate boxes this edition's own diseño de registro prints."""
    refs = revision.casilla_source_refs or revision.source_refs
    sources = compiled_bundled_authority().catalogues.sources
    printed: set[str] = set()
    for ref in refs:
        source = sources.get(str(ref))
        design = bundled_path() / f"{source.corpus_path}.extracted.md" if source is not None else None
        if design is None or not design.is_file():
            continue
        printed |= {box for _rate, _half, box in _DESIGN_ROW.findall(design.read_text(encoding="utf-8"))}
    assert printed, f"edition {revision.id} cites no design printing the recargo block"
    return printed


def _sections(revision: ModeloRevision) -> set[tuple[str, ...]]:
    return {tuple(row.section) for row in _rate_rows(revision).values()}


def _stable_refs(row: CasillaDefinition) -> frozenset[str]:
    return frozenset(str(ref) for ref in row.legal_refs if not str(ref).startswith(_TEMPORARY_RATE_PREFIX))


def _m390_from(root: Path) -> ModeloDefinition:
    modelos, _catalogues = load_registry_tree(root)
    return next(modelo for modelo in modelos if str(modelo.id) == "390")


def test_every_declared_recargo_rate_box_is_printed_in_that_editions_own_design() -> None:
    """Grounding: the block the registry declares is the block the design prints."""
    for revision in _editions_declaring_the_block(_bundled_definition()):
        printed = _design_boxes(revision)
        declared = {str(row.number) for row in _rate_rows(revision).values()}
        assert declared <= printed, (
            f"edition {revision.id} declares recargo rate box(es) {sorted(declared - printed)} "
            "that its own design does not print under the recargo block"
        )


def test_the_recargo_rate_block_shares_one_section_in_every_edition() -> None:
    for revision in _editions_declaring_the_block(_bundled_definition()):
        sections = _sections(revision)
        assert len(sections) == 1, (
            f"edition {revision.id} splits the recargo rate block across sections {sorted(sections)}"
        )
        tier_sections = {tuple(row.section) for row in revision.casillas if str(row.id) in _TIER_CASILLAS}
        assert tier_sections == sections, (
            f"edition {revision.id} sections the rate rows {sorted(sections)} "
            f"but their own total layer {sorted(tier_sections)}"
        )


def test_a_recargo_rate_row_keeps_its_section_in_every_edition_that_carries_it() -> None:
    by_lineage: defaultdict[str, dict[str, tuple[str, ...]]] = defaultdict(dict)
    for revision in _editions_declaring_the_block(_bundled_definition()):
        for lineage, row in _rate_rows(revision).items():
            by_lineage[lineage][str(revision.id)] = tuple(row.section)
    shared = {lineage: seen for lineage, seen in by_lineage.items() if len(seen) > 1}
    assert shared, "no recargo rate row is carried by more than one edition"
    for lineage, seen in sorted(shared.items()):
        assert len(set(seen.values())) == 1, f"{lineage} changes section across editions: {seen}"


def test_a_recargo_rate_rows_stable_grounding_does_not_drift_across_editions() -> None:
    by_lineage: defaultdict[str, dict[str, frozenset[str]]] = defaultdict(dict)
    for revision in _editions_declaring_the_block(_bundled_definition()):
        for lineage, row in _rate_rows(revision).items():
            by_lineage[lineage][str(revision.id)] = _stable_refs(row)
    for lineage, seen in sorted(by_lineage.items()):
        if len(seen) < 2:
            continue
        cores = set(seen.values())
        assert len(cores) == 1, f"{lineage} drops or gains a non-temporary legal reference across editions: " + str(
            {edition: sorted(core) for edition, core in sorted(seen.items())}
        )


def test_mutating_one_rate_rows_section_splits_the_block_and_reds_the_gate(tmp_path: Path) -> None:
    """Sectioning one rate row unlike its siblings is caught in every edition carrying it."""
    scratch_root = scratch_registry_tree(tmp_path, "390")
    mutate_declaration(
        scratch_root / "modelos" / "390",
        revision_id="2024",
        section="casillas",
        member=f'id = "{_TIPO_0_BASE}"',
        find=f"section = {_BLOCK_SECTION_SOURCE}",
        replace=f"section = {_OUTLIER_SECTION}",
    )

    mutated = _m390_from(scratch_root)
    split = {
        str(revision.id): sorted(_sections(revision))
        for revision in _editions_declaring_the_block(mutated)
        if len(_sections(revision)) > 1
    }
    assert split, "the mutation did not split any edition's block, so the gate above proves nothing"
    assert ("operaciones_regimen_general", "recargo_equivalencia") in {
        section for sections in split.values() for section in map(tuple, sections)
    }


def test_reintroducing_a_per_year_section_override_reds_the_cross_edition_gate(tmp_path: Path) -> None:
    """The removed defect: a later edition re-sections rows it inherits unchanged."""
    scratch_root = scratch_registry_tree(tmp_path, "390")
    manifest = scratch_root / "modelos" / "390" / "revisions" / "2024" / "revision.toml"
    overrides = "\n".join(
        f'\n[[revisions."2024".casilla_overrides]]\n'
        f'selector = {{ revision = "2023", id = "{casilla_id}" }}\n'
        f"fields = {{ section = {_OUTLIER_SECTION} }}\n"
        f"removed_fields = []\n"
        for casilla_id in (
            _TIPO_0_BASE,
            "iva.anual.repercutido.recargo.tipo-0.cuota",
            "iva.anual.repercutido.recargo.tipo-0-62.base",
        )
    )
    manifest.write_text(manifest.read_text(encoding="utf-8") + overrides, encoding="utf-8")

    mutated = _m390_from(scratch_root)
    by_lineage: defaultdict[str, set[tuple[str, ...]]] = defaultdict(set)
    for revision in _editions_declaring_the_block(mutated):
        for lineage, row in _rate_rows(revision).items():
            by_lineage[lineage].add(tuple(row.section))
    drifted = sorted(lineage for lineage, sections in by_lineage.items() if len(sections) > 1)
    assert drifted == [
        "iva-anual-repercutido-recargo-tipo-0-62-base",
        "iva-anual-repercutido-recargo-tipo-0-base",
        "iva-anual-repercutido-recargo-tipo-0-cuota",
    ], drifted
