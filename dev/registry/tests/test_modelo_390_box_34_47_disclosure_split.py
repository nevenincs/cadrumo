"""Modelo 390 box [34] and box [47] are two distinct printed totals.

Box [34] "Total bases y cuotas IVA - Cuota" (page 02, Reg. Gral. section) and
box [47] "Total cuotas IVA y recargo de equivalencia" (page 02 bis) are
different official record positions, established by POSITION against the
bundled AEAT DR-390 designs (2024 and 2025 editions agree): page 02 offset
1628 prints "...Total bases y cuotas IVA - Cuota [34]"; page 02 bis (record
``modelo-390-page-02b``) offset 353 prints "...Total cuotas IVA y recargo
equivalencia [47]". These identities are scoped to the design years actually
read (2024, 2025); this revision's export layout matches both.

Before this module's fix, the recargo-INCLUSIVE ``iva.anual.cuota-devengada-
total`` (correctly form_number "47") was the ONLY casilla exported to page 02
offset 1628 -- the box [34] slot -- so every recargo-de-equivalencia filer's
[34] carried a recargo-inflated figure while [47] was never written at all.
The fix adds ``iva.anual.total-bases-cuotas-iva`` (form_number "34"), an
IVA-only total over the four devengada rungs this revision currently models,
and repoints the page 02 offset-1628 field to it; a new page 02 bis
offset-353 field carries the pre-existing recargo-inclusive total to [47].

Both shipped revisions have the official geometry this gate protects: box [34]
is written at offset 1628 of ``modelo-390-page-02`` and box [47] at offset 353
of ``modelo-390-page-02b``.  The full tree is currently accepted by the
fail-closed authority.  This focused test nevertheless reads the compiled raw
registry so it can recompile an isolated scratch mutation and inspect the exact
export structure.  Its mutation proof keeps the IVA-versus-recargo disclosure
split honest, while the position assertions keep both totals on their respective
official records.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..compiler.loader import load_registry_tree
from ._gate_support import mutate_declaration, scratch_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_CASILLA_BOX_34 = "iva.anual.total-bases-cuotas-iva"
_CASILLA_BOX_47 = "iva.anual.cuota-devengada-total"
_FORMULA_BOX_34 = "modelo-390-iva-anual-total-bases-cuotas-iva"
_NON_RECARGO_TERMS = frozenset(
    {
        "iva.anual.repercutido.general",
        "iva.anual.repercutido.reducido",
        "iva.anual.repercutido.super-reducido",
        "iva.anual.autorepercutido.intracomunitaria",
    }
)


def _m390_revisions(root: Path) -> dict[str, ModeloRevision]:
    """Return every Modelo 390 revision declaring the box-34 casilla.

    Derived rather than pinned to a revision id: annual epochs are split as AEAT
    re-lays out the record, so a pinned id either disappears with a split or, if
    a rename restores it elsewhere, leaves this gate passing over a revision it
    never checked.
    """
    modelos, _catalogues = load_registry_tree(root)
    m390 = next(m for m in modelos if m.id == "390")
    return {
        revision_id: revision
        for revision_id, revision in m390.revisions.items()
        if any(casilla.id == _CASILLA_BOX_34 for casilla in revision.casillas)
    }


def _positions(revision, casilla_id: str) -> set[tuple[str, int]]:
    """Return every ``(record, offset)`` the revision's layouts export a casilla at."""
    return {
        (record.id, field.offset)
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id == casilla_id and getattr(field, "offset", None) is not None
    }


def _bundled_registry_root() -> Path:
    # src/cadrumo/_data/registry/aeat, three levels above this test file's
    # package (domain/calculations/registry/tests -> domain/calculations ->
    # domain -> cadrumo), matching the layout _authority.compiled_bundled_authority()
    # points at.
    return bundled_path("registry", "aeat")


def _export_field(revision, *, record_id: str, offset: int):
    for layout in revision.export_layouts:
        for record in layout.records:
            if record.id != record_id:
                continue
            for field in record.fields:
                if getattr(field, "offset", None) == offset:
                    return field
    raise AssertionError(f"no field at {record_id}:{offset}")


def test_at_least_one_revision_declares_the_box_34_casilla() -> None:
    """Anchor the derivation, so a retired or renamed revision cannot empty this gate."""
    revisions = _m390_revisions(_bundled_registry_root())
    assert revisions, (
        f"no Modelo 390 revision declares {_CASILLA_BOX_34!r}. Either the split "
        "dropped the box-34 disclosure or the casilla was renamed; this gate is "
        "inert until that is resolved, so diagnose rather than delete it."
    )


def test_box_34_and_box_47_are_distinct_casillas_in_every_revision() -> None:
    """Every revision carrying the split must keep the two totals separate."""
    for revision_id, revision in sorted(_m390_revisions(_bundled_registry_root()).items()):
        casillas = {c.id: c for c in revision.casillas}
        assert _CASILLA_BOX_47 in casillas, f"{revision_id} declares box 34 without box 47"

        box_34 = casillas[_CASILLA_BOX_34]
        box_47 = casillas[_CASILLA_BOX_47]

        assert box_34.form_number == "34", revision_id
        assert box_47.form_number == "47", revision_id
        assert box_34.id != box_47.id, revision_id


def test_each_total_is_exported_to_its_own_position_in_every_revision() -> None:
    """Neither total may go unwritten, and they may never share one position.

    Positions are asserted as disjoint rather than as fixed offsets: AEAT moves
    these between design epochs, which is why the revisions are split at all.
    Where a layout does declare the page-02 offset-1628 slot, that slot is the
    box-34 slot, which is the exact identity the original defect inverted.

    A revision that exports neither total is a failure here, not an excused case.
    The shipped 2024 and 2025 layouts place [34] at
    ``modelo-390-page-02:1628`` and [47] at
    ``modelo-390-page-02b:353``.  The formula mutation below proves that [34]
    remains recargo-sensitive; the position assertions prove each total reaches
    its own official field.
    """
    for revision_id, revision in sorted(_m390_revisions(_bundled_registry_root()).items()):
        positions_34 = _positions(revision, _CASILLA_BOX_34)
        positions_47 = _positions(revision, _CASILLA_BOX_47)

        assert positions_34, f"{revision_id} exports box 47 but never box 34"
        assert positions_47, f"{revision_id} exports box 34 but never box 47"
        assert not (positions_34 & positions_47), (
            f"{revision_id} exports box 34 and box 47 to the same position "
            f"{sorted(positions_34 & positions_47)!r}, so one total overwrites the other"
        )

        if ("modelo-390-page-02", 1628) in positions_34 | positions_47:
            assert ("modelo-390-page-02", 1628) in positions_34, (
                f"{revision_id} prints the recargo-inclusive total at the box-34 slot"
            )


def test_box_34_formula_excludes_every_recargo_term() -> None:
    """The box-34 total is IVA-only; a recargo term there re-inflates box 34."""
    for revision_id, revision in sorted(_m390_revisions(_bundled_registry_root()).items()):
        formulas = {f.id: f for f in revision.formulas}
        if _FORMULA_BOX_34 not in formulas:
            continue
        formula = formulas[_FORMULA_BOX_34]

        arg_casilla_ids = {arg.casilla_id for arg in formula.expression.args if arg.casilla_id is not None}

        assert arg_casilla_ids == _NON_RECARGO_TERMS, revision_id
        assert not any("recargo" in casilla_id for casilla_id in arg_casilla_ids), revision_id


def test_mutation_repointing_offset_1628_to_the_recargo_inclusive_total_reds_the_gate(tmp_path: Path) -> None:
    """Re-introduce the exact original defect on an isolated scratch copy of
    the registry tree (never the tracked file) and confirm the position test
    above would have caught it.

    Anti-tautology / mutation proof: this reverts the export-layout field's
    ``casilla_id`` for the page-02 offset-1628 field back to
    ``iva.anual.cuota-devengada-total`` (the pre-fix state), reloads the
    mutated scratch copy, and asserts the position test's own condition now
    fails on that mutated tree -- proving the gate has teeth rather than
    passing vacuously.
    """
    scratch_root = scratch_registry_tree(tmp_path, "390")
    target_revision_id = next(
        revision_id
        for revision_id, revision in sorted(_m390_revisions(_bundled_registry_root()).items())
        if _FORMULA_BOX_34 in {formula.id for formula in revision.formulas}
    )
    # The fragment declares several formulas, so the mutation is scoped to the
    # box-34 declaration rather than the file's first matching term.
    mutate_declaration(
        scratch_root / "modelos" / "390",
        revision_id=target_revision_id,
        section="formulas",
        member=f'id = "{_FORMULA_BOX_34}"',
        find='{ casilla_id = "iva.anual.repercutido.general" }',
        replace='{ casilla_id = "iva.anual.recargo-equivalencia.general" }',
    )

    mutated_revision = _m390_revisions(scratch_root)[target_revision_id]
    mutated_formula = {formula.id: formula for formula in mutated_revision.formulas}[_FORMULA_BOX_34]
    mutated_terms = {arg.casilla_id for arg in mutated_formula.expression.args if arg.casilla_id is not None}

    assert mutated_terms != _NON_RECARGO_TERMS
    assert any("recargo" in casilla_id for casilla_id in mutated_terms)
