"""Modelo 303's record-design boxes are derived in every year whose design admits it.

The diseño de registro carries a box layer beside the semantic casillas: boxes [11]
and [13] restate the annual adquisiciones intracomunitarias and domestic inversión
del sujeto pasivo cuotas, and boxes [120] and [122] restate the informational
volúmenes for operations Spain does not tax and for the supplier's side of a
domestic reverse charge. Every supported design prints those four boxes with the
same number, width, type and concept, and none of them has a rate field of its own
whose constraint could change what the box means. So the registry must derive them
in every edition, not leave one edition asking the operator for a figure it already
resolves.

Two neighbouring box families deliberately do NOT follow that shape, and this module
pins the distinction so a later sweep does not "fix" them:

- Boxes [03], [06] and [09] are the cuotas of the régimen general rate rows. Their
  meaning comes from the paired `Tipo %` box, which the 2022 design leaves a free
  three-integer-two-decimal field and every later design pins to a constant. Only
  once the rate is pinned does row one mean super-reducido, row two reducido and row
  three general, so only then may the registry project a rate-specific carrier.
- Box [18] is the recargo de equivalencia cuota, whose paired `Tipo % [17]` is a free
  field in 2022, an enumeration of three tiers in 2023 and the early 2024 design, an
  open note in the late 2024 design and a single constant in 2025. The registry
  follows each design rather than one shape.

The oracle for all of it is the design text in the bundled corpus. The registry side
is the compiled typed authority and the real calculation engine; the mutation proof
runs against an isolated scratch registry and never the tracked tree.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.ledger_iva_bindings import (
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.period import calculation_filing_date

from ..compiler.authority import compiled_bundled_authority
from ..compiler.loader import load_registry_tree
from ._gate_support import mutate_declaration, scratch_registry_tree
from ._modelo_303_registry_support import _M303_RECORD_DESIGN_SOURCE_BY_REVISION

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_domain,
    pytest.mark.usefixtures("governed_fact_scope"),
]

_REVISIONS = tuple(_M303_RECORD_DESIGN_SOURCE_BY_REVISION)

#: The boxes this module requires every edition to derive, and the carrier or
#: binding each one restates.
_DERIVED_BOXES = {
    "11": ("computed", "modelo-303-dr303-11-projection"),
    "13": ("computed", "modelo-303-dr303-13-projection"),
    "120": ("bound", "modelo-303-casilla-120-no-sujetas-localizacion-base"),
    "122": ("bound", "modelo-303-casilla-122-inversion-sujeto-pasivo-base"),
}
#: The rate-row cuotas whose meaning depends on the paired Tipo % constraint.
_RATE_ROW_BOXES = ("03", "06", "09")
_RATE_FIELD_BY_BOX = {"03": "02", "06": "05", "09": "08"}
#: A free rate field states only its own width; a pinned one names a constant.
_FREE_RATE_FIELD = "3 enteros y 2 decimales"
#: The wording each derived box keeps in every design. Its printed POSITION moves as
#: later designs insert rows before it, which is a layout fact, not a change of
#: meaning; the width, the type and this wording are what must not move.
_BOX_CONCEPT = {
    "11": "Adquisiciones intracomunitarias de bienes y servicios - Cuota",
    "13": "inversión del sujeto pasivo (excepto. adq. intracom) - Cuota",
    "120": "no sujetas por reglas de localización",
    "122": "sujetas con inversión del sujeto pasivo",
}


def _revision(revision_id: str) -> ModeloRevision:
    return compiled_bundled_authority().modelo("303").revisions[revision_id]


def _design_text(revision_id: str) -> str:
    source = compiled_bundled_authority().catalogues.sources[_M303_RECORD_DESIGN_SOURCE_BY_REVISION[revision_id]]
    return (bundled_path() / f"{source.corpus_path}.extracted.md").read_text(encoding="utf-8")


def _design_row(revision_id: str, box: str) -> str:
    rows = [line for line in _design_text(revision_id).split("\n") if re.search(rf"\[{box}\]\s*\|", line)]
    assert len(rows) == 1, f"{revision_id}: design prints {len(rows)} rows for [{box}]"
    return rows[0]


def _derived_state(revision: ModeloRevision, box: str) -> tuple[str, str | None]:
    row = next(row for row in revision.casillas if str(row.id) == box)
    return str(row.input_kind), str(row.formula or row.binding) if (row.formula or row.binding) else None


@pytest.mark.parametrize("box", sorted(_DERIVED_BOXES))
def test_a_derived_box_is_declared_the_same_way_in_every_edition(box: str) -> None:
    expected = _DERIVED_BOXES[box]
    for revision_id in _REVISIONS:
        assert _derived_state(_revision(revision_id), box) == expected, (
            f"edition {revision_id} declares [{box}] as {_derived_state(_revision(revision_id), box)}"
        )


@pytest.mark.parametrize("box", sorted(_DERIVED_BOXES))
def test_every_design_prints_a_derived_box_with_one_unchanging_shape(box: str) -> None:
    """Grounding: the width, type and wording the design gives the box never move."""
    shapes = set()
    for revision_id in _REVISIONS:
        row = _design_row(revision_id, box)
        fields = [cell.strip() for cell in row.split("|")]
        shapes.add((fields[2], fields[3]))
        assert _BOX_CONCEPT[box] in row, f"{revision_id}: [{box}] is printed as {fields[4]!r}"
    assert len(shapes) == 1, f"[{box}] changes width or type across designs: {sorted(shapes)}"


def test_the_rate_row_cuotas_are_derived_only_where_the_design_pins_their_rate() -> None:
    """The kept divergence: a free Tipo % field cannot carry a rate-specific carrier."""
    for revision_id in _REVISIONS:
        revision = _revision(revision_id)
        for box in _RATE_ROW_BOXES:
            rate_row = _design_row(revision_id, _RATE_FIELD_BY_BOX[box])
            pinned = "Constante" in rate_row
            assert (_FREE_RATE_FIELD in rate_row) != pinned, (
                f"{revision_id}: [{_RATE_FIELD_BY_BOX[box]}] is neither a free field nor a constant"
            )
            kind, _source = _derived_state(revision, box)
            assert (kind == "computed") == pinned, (
                f"{revision_id}: [{box}] is {kind} while its rate field "
                f"{'pins a constant' if pinned else 'is a free field'}"
            )


def test_box_18_follows_its_own_designs_rate_constraint_rather_than_one_shape() -> None:
    """The other kept divergence, stated as the designs state it."""
    observed = {revision_id: _derived_state(_revision(revision_id), "18")[0] for revision_id in _REVISIONS}
    enumerated = {
        revision_id for revision_id in _REVISIONS if '"00000", "00050", "00062"' in _design_row(revision_id, "17")
    }
    assert enumerated, "no design enumerates the recargo tiers; the premise of this test is gone"
    for revision_id in _REVISIONS:
        expected = "bound" if revision_id in enumerated else "manual"
        assert observed[revision_id] == expected, (
            f"{revision_id}: [18] is {observed[revision_id]} while its design "
            f"{'enumerates' if revision_id in enumerated else 'does not enumerate'} the tiers"
        )


@pytest.mark.parametrize(("filing_year", "revision_id"), [(2022, "2022"), (2023, "2023"), (2025, "2025")])
def test_the_derived_boxes_carry_the_same_value_in_every_year(filing_year: int, revision_id: str) -> None:
    """One ledger-free input set computes one value for each derived box, every year."""
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot("303", filing_year=filing_year, period="4T")
    assert snapshot.revision.id == revision_id
    declared_bindings = {binding.id for binding in snapshot.revision.bindings}
    binding_values = {
        binding_id: value
        for binding_id, value in {
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0"),
            "modelo-303-profile-state-attribution-ratio": Decimal("100"),
            **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, ()),
        }.items()
        if binding_id in declared_bindings
    }
    inputs: dict[CasillaId, Decimal] = dict(
        resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    )
    calculated = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": calculation_filing_date(Period.from_year_and_code(filing_year, "4T"))},
    )
    # An empty ledger resolves every derived box to a proven zero, and it must be
    # the same proven zero in each year rather than an absence in one of them.
    for box in sorted(_DERIVED_BOXES):
        assert calculated.values[validated_casilla_id(box)] == Decimal("0"), f"{revision_id}: [{box}]"


def _m303_kinds(root: Path, box: str) -> dict[str, str]:
    modelos, _catalogues = load_registry_tree(root)
    mutated = next(modelo for modelo in modelos if str(modelo.id) == "303")
    return {
        revision_id: str(next(row for row in revision.casillas if str(row.id) == box).input_kind)
        for revision_id, revision in mutated.revisions.items()
    }


def test_dropping_box_11_from_the_baseline_reds_the_gate_in_every_edition(tmp_path: Path) -> None:
    """Authoring it once is what makes the years agree: remove it and they all lose it."""
    scratch_root = scratch_registry_tree(tmp_path, "303")
    mutate_declaration(
        scratch_root / "modelos" / "303",
        revision_id="2022",
        section="casillas",
        member='id = "11"',
        find='input_kind = "computed"\nformula = "modelo-303-dr303-11-projection"\n',
        replace="",
    )

    kinds = _m303_kinds(scratch_root, "11")
    assert set(kinds.values()) == {"manual"}, kinds
    assert kinds != {revision_id: "computed" for revision_id in kinds}


def test_reintroducing_the_per_year_override_reds_the_cross_edition_gate(tmp_path: Path) -> None:
    """The removed defect exactly: the baseline leaves the box manual and 2023 patches it."""
    scratch_root = scratch_registry_tree(tmp_path, "303")
    modelo_dir = scratch_root / "modelos" / "303"
    mutate_declaration(
        modelo_dir,
        revision_id="2022",
        section="casillas",
        member='id = "11"',
        find='input_kind = "computed"\nformula = "modelo-303-dr303-11-projection"\n',
        replace="",
    )
    manifest = modelo_dir / "revisions" / "2023" / "revision.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8")
        + "\n[[revisions.2023.casilla_overrides]]\n"
        + 'selector = { revision = "2022", id = "11" }\n'
        + 'fields = { formula = "modelo-303-dr303-11-projection", input_kind = "computed" }\n'
        + "removed_fields = []\n",
        encoding="utf-8",
    )

    kinds = _m303_kinds(scratch_root, "11")
    assert kinds["2022"] == "manual", kinds
    assert kinds["2023"] == "computed", kinds
    assert len(set(kinds.values())) > 1, "the mutation did not split the editions"
