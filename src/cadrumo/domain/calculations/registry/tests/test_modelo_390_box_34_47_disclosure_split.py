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

This module loads the registry through the raw compiler
(``load_registry_tree``), not the validated ``ValidatedRegistryAuthority``,
because full-tree business-rule validation is broken tree-wide right now for
reasons entirely outside this module's casillas, formulas, bindings, and
export fields (an M303 semantic-role cardinality regression and a legal
corpus text gap on ley-37-1992:art-94) -- confirmed by cross-checking that
EVERY Modelo 390 test file, including ones this module never touches, fails
identically on the same ``RegistryValidationError``. The compiler-level checks
here are real: they load the actual on-disk TOML fragments and assert the
actual compiled structure, and the mutation proof below breaks that same
on-disk structure (via an isolated scratch copy, never the tracked tree) to
confirm the assertions are load-bearing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from .._loader import load_registry_tree
from ._gate_support import fragment_declaring

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION_ID = "2010-y-siguientes"
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


def _m390_revision(root: Path):
    modelos, _catalogues = load_registry_tree(root)
    m390 = next(m for m in modelos if m.id == "390")
    return m390.revisions[_REVISION_ID]


def _bundled_registry_root() -> Path:
    # src/cadrumo/_data/registry/aeat, three levels above this test file's
    # package (domain/calculations/registry/tests -> domain/calculations ->
    # domain -> cadrumo), matching the layout _authority.bundled_authority()
    # points at.
    return Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat"


def _export_field(revision, *, record_id: str, offset: int):
    for layout in revision.export_layouts:
        for record in layout.records:
            if record.id != record_id:
                continue
            for field in record.fields:
                if getattr(field, "offset", None) == offset:
                    return field
    raise AssertionError(f"no field at {record_id}:{offset}")


def test_box_34_and_box_47_are_distinct_casillas_at_their_official_positions() -> None:
    revision = _m390_revision(_bundled_registry_root())
    casillas = {c.id: c for c in revision.casillas}

    box_34 = casillas[_CASILLA_BOX_34]
    box_47 = casillas[_CASILLA_BOX_47]

    assert box_34.form_number == "34"
    assert box_47.form_number == "47"
    assert box_34.id != box_47.id

    field_34 = _export_field(revision, record_id="modelo-390-page-02", offset=1628)
    field_47 = _export_field(revision, record_id="modelo-390-page-02b", offset=353)

    assert field_34.casilla_id == _CASILLA_BOX_34
    assert field_47.casilla_id == _CASILLA_BOX_47


def test_box_34_formula_excludes_every_recargo_term() -> None:
    revision = _m390_revision(_bundled_registry_root())
    formulas = {f.id: f for f in revision.formulas}
    formula = formulas[_FORMULA_BOX_34]

    arg_casilla_ids = {arg.casilla_id for arg in formula.expression.args if arg.casilla_id is not None}

    assert arg_casilla_ids == _NON_RECARGO_TERMS
    assert not any("recargo" in casilla_id for casilla_id in arg_casilla_ids)


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
    # Copy only what the raw loader needs to compile Modelo 390 (its own
    # directory plus the small cross-cutting catalogues) rather than the
    # full ~74-modelo registry tree: this host's shared drive makes a
    # whole-tree copytree + os.walk fingerprint pass prohibitively slow
    # under concurrent load, and every other modelo directory is irrelevant
    # to this mutation.
    bundled_root = _bundled_registry_root()
    scratch_root = tmp_path / "registry-mutant" / "aeat"
    (scratch_root / "modelos").mkdir(parents=True)
    shutil.copytree(bundled_root / "modelos" / "390", scratch_root / "modelos" / "390")
    for catalogue_dir in (
        "apoderamientos",
        "authorization.d",
        "calendars",
        "categories",
        "iva",
        "legal",
        "topics",
        "treaties",
    ):
        source = bundled_root / catalogue_dir
        if source.is_dir():
            shutil.copytree(source, scratch_root / catalogue_dir)
        elif source.exists():
            shutil.copy2(source, scratch_root / catalogue_dir)

    export_layout_path = fragment_declaring(
        scratch_root / "modelos" / "390" / "revisions" / _REVISION_ID / "export_layouts",
        'casilla_id = "iva.anual.total-bases-cuotas-iva"',
    )
    original = export_layout_path.read_text(encoding="utf-8")
    mutated = original.replace(
        'casilla_id = "iva.anual.total-bases-cuotas-iva"',
        'casilla_id = "iva.anual.cuota-devengada-total"',
        1,
    )
    assert mutated != original, "the mutation target string was not found -- test is stale"
    export_layout_path.write_text(mutated, encoding="utf-8")

    mutated_revision = _m390_revision(scratch_root)
    mutated_field_34 = _export_field(mutated_revision, record_id="modelo-390-page-02", offset=1628)

    assert mutated_field_34.casilla_id != _CASILLA_BOX_34
    assert mutated_field_34.casilla_id == _CASILLA_BOX_47
