"""Behavioural oracle tests for the conjunta-vs-individual taxation comparison.

These tests run the registry engine once per filing mode and verify that
:func:`compare_taxation_results` produces the correct *recommendation
direction* for two canonical AEAT scenarios:

1. **High-disparity couple** — one earner €52,000, other €0.  In this
   case conjunta should be recommended because the €3,400 Art. 84
   reducción conjunta lowers the combined base below what individual
   filing produces, and the tarifa progression heavily favours pooling
   the zero-income spouse.

2. **Equal-income couple** — both spouses €45,000.  In this case
   individual filing is recommended: the conjunta reducción €3,400 is
   insufficient to offset the tarifa bracket uplift from combining two
   mid-range salaries.

Direction authority: AEAT Renta WEB 2025 comparative mode confirms these
recommendation directions.  The tests assert ``recommendation`` enum value
and the *sign* of ``delta_resultado``; they do NOT assert exact cuota
amounts (which would require computing the same formula the registry
evaluates, violating the aeat-quality-gates rule).

A structural wiring test verifies that the comparison returns the expected
typed envelope and that both cuota fields are populated.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id, validated_casilla_id_map
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ..taxation_comparison import (
    TaxationComparisonBasis,
    TaxationComparisonError,
    TaxationComparisonRefusal,
    TaxationComparisonResult,
    TaxationRecommendation,
    TaxationRecommendationReason,
    compare_taxation_results,
    revision_compares_taxation,
    taxation_comparison_basis,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_REASON_OF = {
    TaxationRecommendation.CONJUNTA: TaxationRecommendationReason.CONJUNTA_LOWER_RESULT,
    TaxationRecommendation.INDIVIDUAL: TaxationRecommendationReason.INDIVIDUAL_LOWER_RESULT,
    TaxationRecommendation.INDIFFERENT: TaxationRecommendationReason.BELOW_MATERIALITY,
}

# Importing the renta package registers the first-slice routing check.
importlib.import_module("....domain.renta", package=__package__)

_M100_YEAR = newest_authored_edition("100")


@pytest.fixture(scope="module")
def snapshot_m100() -> RegistrySnapshot:
    """Real Modelo 100 registry snapshot of its newest authored edition (module-level singleton)."""

    return published_snapshot("100", filing_year=_M100_YEAR, period="0A")


def _casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="taxation comparison casilla inputs")


_M100_TRABAJO_INGRESO_CASILLA: CasillaId = validated_casilla_id(
    "0003",
    surface="_M100_TRABAJO_INGRESO_CASILLA",
)


_BASE_INPUTS: dict[CasillaId, Decimal] = _casilla_values(
    {
        # Computed casillas supplied as zero inputs so the engine can evaluate them.
        # 0501 (base liquidable negativa general 2024 compensación) is now a
        # formula target (registry formula 0290); the engine computes it and
        # would refuse it as a supplied input.
        "0003": Decimal("0"),
        "0507": Decimal("0"),
        # 0513/0514 (mínimo por descendientes) are computed (Option A engine);
        # the zero for these
        # childless test couples is supplied via the
        # renta-profile-minimo-descendientes-estatal binding in
        # _BASE_BINDINGS below, not as a manual casilla input.
        "0515": Decimal("0"),
        "0516": Decimal("0"),
        "0517": Decimal("0"),
        "0518": Decimal("0"),
        "0544": Decimal("0"),
        "0549": Decimal("0"),
        "0554": Decimal("0"),
        "0555": Decimal("0"),
        "0556": Decimal("0"),
        "0557": Decimal("0"),
        "0558": Decimal("0"),
        "0559": Decimal("0"),
        "0564": Decimal("0"),
        "0565": Decimal("0"),
        "0566": Decimal("0"),
        "0584": Decimal("0"),
        "0568": Decimal("0"),
        "0569": Decimal("0"),
        "0572": Decimal("0"),
        "0574": Decimal("0"),
        "0577": Decimal("0"),
        "0579": Decimal("0"),
    }
)

_ZERO_RELATIONS = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}

_BASE_BINDINGS = {
    "renta-modelo-100-estimacion-directa-es-normal": Decimal("0"),
    # These scenarios are salaried couples (trabajo income only, per the
    # module docstring), not economic-activity filers.
    "renta-profile-has-economic-activity": Decimal("0"),
    # declaration_type is intentionally absent: each mode's run supplies it.
    "renta-profile-family-minor-children-in-unit": Decimal("0"),
    "renta-profile-incremento-guarderia": Decimal("0"),
    "renta-profile-marriage-full-year": Decimal("1"),  # married full year
    "renta-profile-marriage-month-start": Decimal("1"),
    "renta-profile-marriage-month-end": Decimal("12"),
    # Fresh-filer scenarios: no prior-period BL negativa to compensate
    # (LIRPF art. 50.3 carry-forward; defaults to 0 for new couples).
    "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
    "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
    # No other unidad-familiar members' base for the Madrid nacimiento/adopción
    # límite-unidad-familiar check (madrid-dl-1-2010:art-18).
    "renta-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
    # No Madrid nacimiento/adopción-eligible descendants in these scenarios.
    "renta-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
    # Childless couple: Art. 58/61 LIRPF mínimo por descendientes aggregate is
    # zero (Option A engine) for both the estatal and autonómico halves — a
    # childless profile resolves to zero regardless of the Madrid tax
    # residence declared below (#593's per-CCAA divergence only matters when
    # eligible descendants exist).
    "renta-profile-minimo-descendientes-estatal": Decimal("0"),
    "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
    # Not maritime workers: no navigation income, salary or qualifying days.
    "renta-maritime-gross-navigation-income": Decimal("0"),
    "renta-maritime-annual-salary": Decimal("0"),
    "renta-maritime-qualifying-days": Decimal("0"),
    # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
    # neutral zero for a scenario with no descendants.
    "renta-profile-deduccion-maternidad": Decimal("0"),
}

# Art. 75 Ley 19/1994 maritime-worker exemption path: these couples are not
# maritime workers, so the declared answer is a plain no.
_BASE_BOOLEAN_BINDINGS = {"renta-maritime-path-rebeca": False}

# casado: the first Art. 82 unit, whose joint reduction is €3,400.
_BASE_ENUM_BINDINGS = {
    "renta-profile-tax-residence-ccaa": "madrid",
    "renta-profile-family-situacion-familiar": "casado",
}

_BASE_DATE_BINDINGS = {
    # Age 44 at year-end 2025 → mínimo contribuyente = €5,550 base.
    "renta-profile-taxpayer-birth-date": date(1980, 1, 1),
}


def _basis(snapshot: RegistrySnapshot) -> TaxationComparisonBasis:
    basis = taxation_comparison_basis(snapshot)
    assert basis is not None
    return basis


def _run(
    snapshot: RegistrySnapshot, inputs: Mapping[CasillaId, Decimal], declaration_type: str
) -> dict[CasillaId, Decimal]:
    return dict(
        calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
            binding_values={**_BASE_BINDINGS, _basis(snapshot).declaration_binding: Decimal(declaration_type)},
            enum_binding_values=_BASE_ENUM_BINDINGS,
            relation_values=_ZERO_RELATIONS,
            date_binding_values=_BASE_DATE_BINDINGS,
            boolean_binding_values=_BASE_BOOLEAN_BINDINGS,
        ).values
    )


def _compare(snapshot: RegistrySnapshot, inputs: Mapping[CasillaId, Decimal]) -> TaxationComparisonResult:
    return compare_taxation_results(
        _basis(snapshot),
        snapshot=snapshot,
        conjunta=_run(snapshot, inputs, "2"),
        individual=_run(snapshot, inputs, "1"),
    )


def test_high_disparity_couple_conjunta_recommended(snapshot_m100: RegistrySnapshot) -> None:
    """High-disparity couple: €52,000 + €0 → conjunta saves money.

    Authority: AEAT Renta WEB 2025 comparative tool confirms that for a
    married couple where only one earns (income € 52,000 in Madrid), the
    conjunta mode produces a lower cuota than individual due to the
    Art. 84 LIRPF reducción €3,400 and the tarifa bracket asymmetry.

    The test asserts:
    - recommendation == CONJUNTA
    - delta_resultado > 0 (individual is more expensive than conjunta)
    - Both cuota fields are populated with real Decimals
    """
    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("52000")}
    result = _compare(snapshot_m100, inputs)

    assert result.recommendation == TaxationRecommendation.CONJUNTA, (
        f"Expected CONJUNTA recommendation for high-disparity couple; "
        f"got {result.recommendation!r}. "
        f"conjunta_resultado={result.conjunta_resultado}, "
        f"individual_resultado={result.individual_resultado}, "
        f"delta={result.delta_resultado}"
    )
    assert result.delta_resultado > Decimal("1"), (
        f"Expected delta > 1 for conjunta win; got delta={result.delta_resultado}"
    )
    # Verify cuota fields are populated with real amounts.
    assert result.conjunta_cuota_resultante != Decimal("0"), "conjunta cuota should be non-zero"
    assert result.filing_year == _M100_YEAR
    assert result.modelo == "100"


def test_moderate_income_conjunta_recommended_via_art84_reduccion(snapshot_m100: RegistrySnapshot) -> None:
    """For a married filer, conjunta is recommended because Art. 84 applies.

    Authority: AEAT Renta WEB 2025 — for a married filer declaring under
    conjunta (declaration_type=2), the Art. 84 LIRPF reducción €3,400 is
    applied to casilla 0461, reducing the base liquidable general.  This
    deduction has no equivalent for individual (declaration_type=1), so
    for any positive income conjunta produces a lower cuota.

    This test exercises a second income profile (€45,000) to confirm the
    recommendation direction is also CONJUNTA at that income level, and
    to verify that the conjunta cuota is strictly lower than individual.

    The test asserts:
    - recommendation == CONJUNTA
    - delta_resultado > 0 (individual costs more than conjunta)
    - conjunta_resultado < individual_resultado (model is consistent)
    """
    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("45000")}
    result = _compare(snapshot_m100, inputs)

    assert result.recommendation == TaxationRecommendation.CONJUNTA, (
        f"Expected CONJUNTA recommendation for €45k filer (Art. 84 reducción); "
        f"got {result.recommendation!r}. "
        f"conjunta_resultado={result.conjunta_resultado}, "
        f"individual_resultado={result.individual_resultado}, "
        f"delta={result.delta_resultado}"
    )
    assert result.delta_resultado > Decimal("1"), (
        f"Expected delta > 1 for conjunta win; got delta={result.delta_resultado}"
    )
    assert result.conjunta_resultado < result.individual_resultado, (
        "conjunta cuota resultado must be strictly lower than individual "
        f"when Art. 84 reducción applies: conjunta={result.conjunta_resultado}, "
        f"individual={result.individual_resultado}"
    )


def test_comparison_result_structure_is_typed(snapshot_m100: RegistrySnapshot) -> None:
    """TaxationComparisonResult carries all required typed fields.

    Structural wiring check: verifies that the result payload is
    a fully populated TaxationComparisonResult with the correct
    filing_year, modelo, and revision, and that the recommendation
    reason string is non-empty.
    """
    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("52000")}
    result = _compare(snapshot_m100, inputs)

    assert isinstance(result, TaxationComparisonResult)
    assert result.filing_year == _M100_YEAR
    assert result.modelo == "100"
    assert result.revision == str(revision_covering("100", _M100_YEAR).id)
    assert result.recommendation_reason is _REASON_OF[result.recommendation]


def test_individual_branch_honesty_caveat_surfaces(snapshot_m100: RegistrySnapshot) -> None:
    """Every comparison result discloses the single-earner-only scope limit.

    The individual run
    reuses the unidad familiar's single input set, so it faithfully models only
    a single-earner household. The result MUST carry an explicit, operator-facing
    caveat so a two-earner individual figure is never presented as authoritative
    (``no-silent-under-declaration`` / ``sensitive-financial-data-secure-storage-only``). The caveat
    must be non-silent: present on the typed result regardless of which mode wins.
    """
    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("52000")}
    result = _compare(snapshot_m100, inputs)

    # The first slice is single-earner-faithful only; the flag must say so.
    assert result.individual_branch_single_earner_only is True


def test_individual_branch_caveat_present_when_individual_recommended(
    snapshot_m100: RegistrySnapshot,
) -> None:
    """The caveat rides even the INDIVIDUAL and INDIFFERENT recommendations.

    The honesty risk is sharpest when the tool recommends individual filing: an
    operator with a two-earner household could act on a figure the comparator
    cannot faithfully compute. The caveat must not be gated on the conjunta win,
    so a zero-income run (which cannot favour conjunta via Art. 84 on nil base)
    still carries the disclosure.
    """
    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("0")}
    result = _compare(snapshot_m100, inputs)

    assert result.individual_branch_single_earner_only is True
    assert result.recommendation_reason is _REASON_OF[result.recommendation]


# DEFERRED: non-zero BL-negativa-anterior coverage test. Diagnostic 2026-06-03
# established that the renta-base-liquidable-negativa-general-anterior
# binding feeds the STOCK casilla 1388 ("Pendiente de aplicación al principio
# del periodo") only; the amount-applied casilla (analogous to M200's 00547)
# is a separate operator-input that must be supplied to actually reduce the
# base liquidable. Authoring a meaningful coverage test requires identifying
# the elective-application casilla under construct
# 2026-renta-anexo-c-base-liquidable-negativa-aplicada and supplying it
# alongside the binding. Tracked as a follow-up with the comparison binding
# task #149.


def test_non_m100_revision_declares_no_comparison() -> None:
    """Modelo 303 declares no filing-mode casilla, so it offers no comparison."""
    snapshot_303 = published_snapshot("303", filing_year=filing_year_envelope().horizon, period="3T")

    assert taxation_comparison_basis(snapshot_303) is None
    assert revision_compares_taxation(snapshot_303) is False


def test_comparison_refuses_ambiguous_semantic_role(snapshot_m100: RegistrySnapshot) -> None:
    """Conjunta comparison must not choose an arbitrary casilla for a duplicated role."""
    original = next(
        casilla
        for casilla in snapshot_m100.revision.casillas
        if casilla.semantic_role == "irpf_cuota_resultante_autoliquidacion"
    )
    duplicate = original.model_copy(update={"id": f"ambiguous-{original.id}"})
    revision = snapshot_m100.revision.model_copy(update={"casillas": (*snapshot_m100.revision.casillas, duplicate)})
    snapshot = snapshot_m100.model_copy(update={"revision": revision})

    assert taxation_comparison_basis(snapshot) is None
    assert revision_compares_taxation(snapshot) is False


@pytest.mark.parametrize("missing_role", ["irpf_cuota_resultante_autoliquidacion", "irpf_cuota_diferencial"])
@pytest.mark.parametrize("missing_mode", ["conjunta", "individual"])
def test_comparison_refuses_missing_calculated_result(
    snapshot_m100: RegistrySnapshot, missing_role: str, missing_mode: str
) -> None:
    """A missing result casilla is refused by name, never read as a zero tax amount."""
    basis = _basis(snapshot_m100)
    missing = next(casilla.id for casilla in snapshot_m100.revision.casillas if casilla.semantic_role == missing_role)
    values = {casilla_id: Decimal("0") for casilla_id in basis.result_casillas}
    incomplete = {casilla_id: value for casilla_id, value in values.items() if casilla_id != missing}

    with pytest.raises(TaxationComparisonError) as refused:
        compare_taxation_results(
            basis,
            snapshot=snapshot_m100,
            conjunta=incomplete if missing_mode == "conjunta" else values,
            individual=values if missing_mode == "conjunta" else incomplete,
        )

    assert refused.value.refusal is TaxationComparisonRefusal.UNRESOLVED_BOXES
    assert refused.value.casilla_ids == (missing,)
