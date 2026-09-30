"""Modelo 303 boxes the first supported design already prints hydrate from the support floor.

The devengado projections, the informativa bindings for [120] and [122], the
resultado chain [64] to [69], the promotor's autoconsumo and the box-equals-source
predicates apply to every design from the one covering the registry's support
floor: each of those boxes is printed there with the meaning later designs
repeat. They are authored once at that edition and inherited forward. Boxes a
later design introduces stay out of every edition whose own design omits them.
The rate-row cuotas [03], [06] and [09] are not among them: their meaning follows
the paired Tipo % field, which the floor design leaves free, and
``test_modelo_303_record_projection_year_parity`` pins where they are derived.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.iva.flow import IvaFlowDirection
from cadrumo.domain.iva.schema import IvaCategory, IvaRateKind

from .authored_edition_support import authored_revisions, revision_covering, source_reference
from .ledger_iva_aggregation_support import _calculate_303_from_observations, _observation
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

# Official box -> the semantic carrier its single-source projection copies.
_PROJECTED_BOXES = {
    "10": "iva.autorepercutido.intracomunitaria.devengado.base",
    "11": "iva.autorepercutido.intracomunitaria.devengado",
    "13": "iva.autorepercutido.interior.devengado",
    "27": "iva.cuota-devengada-total",
}
_EQUALS_PREDICATES = {
    "equals:dr303-11-equals-iva-autorepercutido-intracomunitaria-devengado",
    "equals:dr303-13-equals-iva-autorepercutido-interior-devengado",
    "equals:dr303-27-equals-iva-cuota-devengada-total",
    "equals:dr303-33-equals-iva-soportado-importaciones",
    "equals:dr303-37-equals-iva-autorepercutido-intracomunitaria-deducible",
    "equals:dr303-45-equals-iva-cuota-deducible-total",
}
# Numbered boxes that appear on some designs only: the transitional-rate rungs,
# the devoluciones box and the later informativa and result boxes.
_DESIGN_SCOPED_BOXES = (
    "108",
    "109",
    "111",
    "112",
    *(str(box) for box in range(150, 159)),
    *(str(box) for box in range(165, 171)),
)


def _floor_revision() -> ModeloRevision:
    return revision_covering("303", committed_supported_filing_years().floor)


@cache
def _design_text(source_id: str) -> str:
    """Return the extracted text of one catalogued record design."""
    source = source_reference(source_id)
    return (bundled_path() / f"{source.corpus_path}.extracted.md").read_text(encoding="utf-8")


def _design(revision: ModeloRevision) -> str:
    """Return the record design an edition's own casillas cite."""
    assert revision.casilla_source_refs, f"edition {revision.id} cites no record design for its casillas"
    return _design_text(str(revision.casilla_source_refs[0]))


def _casilla(revision: ModeloRevision, casilla_id: str):
    (casilla,) = (item for item in revision.casillas if str(item.id) == casilla_id)
    return casilla


def _expression(revision: ModeloRevision, formula_id: str) -> object:
    (formula,) = (item for item in revision.formulas if str(item.id) == formula_id)
    return formula.expression.model_dump(mode="json", exclude_none=True, exclude_defaults=True)


def test_the_support_floor_edition_is_an_authored_edition_of_its_own_design() -> None:
    floor = committed_supported_filing_years().floor
    revision = _floor_revision()
    assert revision.valid_from.year == floor
    assert revision is authored_revisions("303")[0]


def test_devengado_box_projections_hydrate_in_every_edition() -> None:
    failures: list[str] = []
    for revision in authored_revisions("303"):
        design = _design(revision)
        for box, carrier in _PROJECTED_BOXES.items():
            formula_id = f"modelo-303-dr303-{box}-projection"
            casilla = _casilla(revision, box)
            if f"[{box}]" not in design:
                failures.append(f"{revision.id}: design does not print [{box}]")
            elif casilla.input_kind is not InputKind.COMPUTED or str(casilla.formula) != formula_id:
                failures.append(f"{revision.id}: box {box} is {casilla.input_kind} / {casilla.formula}")
            elif _expression(revision, formula_id) != {"casilla_id": carrier}:
                failures.append(f"{revision.id}: {formula_id} projects {_expression(revision, formula_id)!r}")
    assert not failures, "\n".join(failures)


def test_devengado_total_sums_every_box_the_floor_design_names() -> None:
    revision = _floor_revision()
    design = _design(revision)
    # The design's own statement of box [27], which names [15] and [26] as well
    # as the rate, inversión del sujeto pasivo and recargo boxes.
    assert "( [03] + [06] + [09] + [11] + [13] + [15] + [18] + [21] + [24] + [26]) [27]" in design
    arguments = _expression(revision, "modelo-303-iva-cuota-devengada-total")
    assert isinstance(arguments, dict)
    assert arguments["op"] == "add"
    summed = {argument["casilla_id"] for argument in arguments["args"]}
    assert {"15", "18", "21", "24", "26", "iva.autoconsumo.promotor.cuota"} <= summed
    assert {"iva.repercutido.general", "iva.repercutido.reducido", "iva.repercutido.super-reducido"} <= summed


def test_resultado_chain_hydrates_in_every_edition() -> None:
    """[64] to [66] hold in every edition; [69] is checked where the design states it as four terms.

    A later design adds a rectificativa-only box to [69]; that edition's own
    statement is not this move's claim and is left to its own grounding.
    """
    failures: list[str] = []
    four_term_result = "( [66] + [77] - [78] + [68] ) [69]"
    assert four_term_result in _design(_floor_revision())
    for revision in authored_revisions("303"):
        design = _design(revision)
        if "Suma de resultados ( [46] + [58] + [76] ) [64]" not in design:
            failures.append(f"{revision.id}: design does not print [64] as [46] + [58] + [76]")
        if str(_casilla(revision, "64").formula) != "modelo-303-iva-suma-resultados":
            failures.append(f"{revision.id}: [64] is not the suma de resultados")
        if str(_casilla(revision, "65").binding) != "modelo-303-profile-state-attribution-ratio":
            failures.append(f"{revision.id}: [65] is not the State attribution percentage")
        if str(_casilla(revision, "66").formula) != "modelo-303-iva-atribuible-estado":
            failures.append(f"{revision.id}: [66] is not the State-attributable result")
        if _expression(revision, "modelo-303-iva-suma-resultados") != {
            "op": "add",
            "args": [{"casilla_id": "iva.resultado-regimen-general"}, {"casilla_id": "58"}, {"casilla_id": "76"}],
        }:
            failures.append(f"{revision.id}: [64] is not [46] + [58] + [76]")
        if four_term_result in design and _expression(revision, "modelo-303-iva-resultado") != {
            "op": "subtract",
            "args": [
                {
                    "op": "add",
                    "args": [{"op": "add", "args": [{"casilla_id": "66"}, {"casilla_id": "77"}]}, {"casilla_id": "68"}],
                },
                {"casilla_id": "iva.compensacion-aplicada-periodo"},
            ],
        }:
            failures.append(f"{revision.id}: [69] is not [66] + [77] - [78] + [68]")
    assert not failures, "\n".join(failures)


def test_informativa_boxes_120_and_122_are_bound_in_every_edition() -> None:
    expected = {
        "120": "modelo-303-casilla-120-no-sujetas-localizacion-base",
        "122": "modelo-303-casilla-122-inversion-sujeto-pasivo-base",
    }
    for revision in authored_revisions("303"):
        design = _design(revision)
        for box, binding in expected.items():
            assert f"[{box}]" in design, (revision.id, box)
            casilla = _casilla(revision, box)
            assert casilla.input_kind is InputKind.BOUND, (revision.id, box)
            assert str(casilla.binding) == binding, (revision.id, box)


def test_intracomunitaria_base_and_cuota_select_one_population_in_every_edition() -> None:
    """Box [10] and box [11] read the same acquisitions, whatever rates an edition admits."""
    for revision in authored_revisions("303"):
        providers = {
            str(binding.id): binding.model_dump(mode="json")["provider"]
            for binding in revision.bindings
            if str(binding.id)
            in {
                "modelo-303-iva-autorepercutido-intracomunitaria-devengado-base",
                "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota",
            }
        }
        base = providers["modelo-303-iva-autorepercutido-intracomunitaria-devengado-base"]
        cuota = providers["modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"]
        for axis in ("categories", "rate_kinds", "flow_direction", "observation_roles", "cash_accounting_treatments"):
            left, right = base[axis], cuota[axis]
            if isinstance(left, list):
                left, right = sorted(left), sorted(right)
            assert left == right, (revision.id, axis, left, right)


def test_box_equals_source_predicates_hold_in_every_edition() -> None:
    for revision in authored_revisions("303"):
        declared = {str(predicate.id) for predicate in revision.verification_predicates}
        assert declared >= _EQUALS_PREDICATES, (revision.id, sorted(_EQUALS_PREDICATES - declared))


def test_design_scoped_boxes_are_declared_exactly_where_their_design_prints_them() -> None:
    failures: list[str] = []
    for revision in authored_revisions("303"):
        design = _design(revision)
        declared = {str(casilla.id) for casilla in revision.casillas}
        for box in _DESIGN_SCOPED_BOXES:
            printed = f"[{box}]" in design
            if printed != (box in declared):
                failures.append(f"{revision.id}: [{box}] printed={printed} declared={box in declared}")
    assert not failures, "\n".join(failures)


def _domestic_sales(exercise: int) -> tuple[IvaLedgerObservation, ...]:
    def sale(ledger_id: str, category: str, rate_kind: str, rate: str, base: str, iva: str) -> IvaLedgerObservation:
        return _observation(
            ledger_id=ledger_id,
            txn_date=date(exercise, 5, 15),
            category=IvaCategory(category),
            rate_kind=IvaRateKind(rate_kind),
            flow=IvaFlowDirection.from_registry("repercutido"),
            applied_rate=Decimal(rate),
            base=Decimal(base),
            iva=Decimal(iva),
        )

    return (
        sale("general", "domestic_general", "general", "0.21", "1000.00", "210.00"),
        sale("reducido", "domestic_reduced", "reduced", "0.10", "200.00", "20.00"),
        sale("super-reducido", "domestic_super_reduced", "super_reduced", "0.04", "100.00", "4.00"),
    )


def test_floor_exercise_carries_its_sales_to_the_printed_result() -> None:
    """A floor-year quarter's sales reach [27] and carry to [69].

    The expected figures are the three sales' own cuotas and the design's box
    arithmetic ([27] = [03] + [06] + [09] with no other devengado, [46] = [27] -
    [45] with nothing deductible, [64] = [46], [66] = [64] at a 100 % State
    share and [69] = [66]), not the registry's formulas. The floor design leaves
    the rate rows' Tipo % free, so the rows themselves stay operator input there.
    """
    exercise = committed_supported_filing_years().floor
    result = _calculate_303_from_observations(filing_year=exercise, period="2T", observations=_domestic_sales(exercise))
    values = result.values

    def box(casilla_id: str) -> Decimal:
        return values[validated_casilla_id(casilla_id)]

    assert box("27") == Decimal("234.00")
    assert box("64") == Decimal("234.00")
    assert box("66") == Decimal("234.00")
    assert box("iva.resultado") == Decimal("234.00")
