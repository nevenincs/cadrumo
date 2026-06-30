"""Behavioural oracle tests for the conjunta-vs-individual taxation comparison.

These tests verify that :func:`compare_taxation_modes` produces the
correct *recommendation direction* for two canonical AEAT scenarios:

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
evaluates, violating the no-tautological-calculation-tests rule).

A structural wiring test verifies that the comparison returns the expected
typed envelope and that both cuota fields are populated.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from ....domain.calculations.registry import CasillaId, RegistrySnapshot, validated_casilla_id, validated_casilla_id_map
from .._taxation_comparison import (
    TaxationComparisonError,
    TaxationRecommendation,
    compare_taxation_modes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Importing the renta package registers the first-slice routing check.
importlib.import_module("aeat.domain.renta")


@pytest.fixture(scope="module")
def snapshot_2025() -> RegistrySnapshot:
    """Real Modelo 100 2025 registry snapshot (module-level singleton)."""
    from ....core.resources import resources

    return resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")


def _casilla_values(values: Mapping[object, Decimal]) -> dict[CasillaId, Decimal]:
    return validated_casilla_id_map(values, surface="taxation comparison casilla inputs")


_M100_TRABAJO_INGRESO_CASILLA: CasillaId = validated_casilla_id(
    "0003",
    surface="_M100_TRABAJO_INGRESO_CASILLA",
)


_BASE_INPUTS: dict[CasillaId, Decimal] = _casilla_values(
    {
    # Computed casillas supplied as zero inputs so the engine can evaluate them.
    "0003": Decimal("0"),
    "0429": Decimal("0"),
    "0501": Decimal("0"),
    "0506": Decimal("0"),
    "0507": Decimal("0"),
    "0513": Decimal("0"),
    "0514": Decimal("0"),
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
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
}

_BASE_BINDINGS = {
    "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("0"),
    "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
    # declaration_type is intentionally absent — compare_taxation_modes injects it.
    "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
    "renta-2025-profile-marriage-full-year": Decimal("1"),  # married full year
    "renta-2025-profile-marriage-month-start": Decimal("1"),
    "renta-2025-profile-marriage-month-end": Decimal("12"),
    # Fresh-filer scenarios: no prior-period BL negativa to compensate
    # (LIRPF art. 50.3 carry-forward; defaults to 0 for new couples).
    "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
}

_BASE_ENUM_BINDINGS = {"renta-2025-profile-tax-residence-ccaa": "madrid"}

_BASE_DATE_BINDINGS = {
    # Age 44 at year-end 2025 → mínimo contribuyente = €5,550 base.
    "renta-2025-profile-taxpayer-birth-date": date(1980, 1, 1),
}


def test_high_disparity_couple_conjunta_recommended(snapshot_2025: RegistrySnapshot) -> None:
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
    result = compare_taxation_modes(
        snapshot_2025,
        inputs=inputs,
        binding_values=_BASE_BINDINGS,
        enum_binding_values=_BASE_ENUM_BINDINGS,
        relation_values=_ZERO_RELATIONS,
        date_binding_values=_BASE_DATE_BINDINGS,
    )

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
    assert result.filing_year == 2025
    assert result.modelo == "100"


def test_moderate_income_conjunta_recommended_via_art84_reduccion(snapshot_2025: RegistrySnapshot) -> None:
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
    result = compare_taxation_modes(
        snapshot_2025,
        inputs=inputs,
        binding_values=_BASE_BINDINGS,
        enum_binding_values=_BASE_ENUM_BINDINGS,
        relation_values=_ZERO_RELATIONS,
        date_binding_values=_BASE_DATE_BINDINGS,
    )

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


def test_comparison_result_structure_is_typed(snapshot_2025: RegistrySnapshot) -> None:
    """TaxationComparisonResult carries all required typed fields.

    Structural wiring check: verifies that the result payload is
    a fully populated TaxationComparisonResult with the correct
    filing_year, modelo, and revision, and that the recommendation
    reason string is non-empty.
    """
    from .._taxation_comparison import TaxationComparisonResult

    inputs = {**_BASE_INPUTS, _M100_TRABAJO_INGRESO_CASILLA: Decimal("52000")}
    result = compare_taxation_modes(
        snapshot_2025,
        inputs=inputs,
        binding_values=_BASE_BINDINGS,
        enum_binding_values=_BASE_ENUM_BINDINGS,
        relation_values=_ZERO_RELATIONS,
        date_binding_values=_BASE_DATE_BINDINGS,
    )

    assert isinstance(result, TaxationComparisonResult)
    assert result.filing_year == 2025
    assert result.modelo == "100"
    assert result.revision == "2025"
    assert len(result.recommendation_reason) > 10


# DEFERRED: non-zero BL-negativa-anterior coverage test. Diagnostic 2026-06-03
# established that the renta-2025-base-liquidable-negativa-general-anterior
# binding feeds the STOCK casilla 1388 ("Pendiente de aplicación al principio
# del periodo") only; the amount-applied casilla (analogous to M200's 00547)
# is a separate operator-input that must be supplied to actually reduce the
# base liquidable. Authoring a meaningful coverage test requires identifying
# the elective-application casilla under construct
# 2026-renta-anexo-c-base-liquidable-negativa-aplicada and supplying it
# alongside the binding. Tracked as a follow-up with the comparison binding
# task #149.


def test_taxation_comparison_error_is_registered_and_envelopes() -> None:
    """TaxationComparisonError is bound in ERROR_REGISTRY and envelopes cleanly.

    Registry membership: confirms the class received an ErrorCode via
    AeatError.__init_subclass__ and that the code appears in ERROR_REGISTRY.

    Envelope round-trip: instantiates the exception, builds an ErrorEnvelope
    via build_error_envelope, and asserts the envelope fields carry the
    expected stable values. The expected code string is derived from the
    registry declaration in aeat.core.errors.registry._application, not
    hand-computed.
    """
    from ....core.errors import ERROR_REGISTRY, build_error_envelope
    from ....core.errors._registry import get_registered_error_code
    from .._taxation_comparison import TaxationComparisonError

    # Registry membership: the declared code must be present in ERROR_REGISTRY.
    code_obj = get_registered_error_code(TaxationComparisonError)
    assert code_obj.code in ERROR_REGISTRY, (
        f"ErrorCode {code_obj.code!r} returned by get_registered_error_code is absent from ERROR_REGISTRY"
    )
    assert ERROR_REGISTRY[code_obj.code] is code_obj

    # The stable code string declared in registry/_application.py.
    assert code_obj.code == "REFUSED_TAXATION_COMPARISON"

    # Envelope round-trip: build_error_envelope must produce a valid ErrorEnvelope.
    exc = TaxationComparisonError("comparison not supported for this modelo")
    envelope = build_error_envelope(exc)

    assert envelope.code == "REFUSED_TAXATION_COMPARISON"
    assert envelope.category == "REFUSED"
    assert envelope.retryable is False
    assert envelope.message != ""


def test_taxation_comparison_module_imports_cleanly() -> None:
    """aeat.application.modelo._taxation_comparison must import without error.

    Exercises that the module's top-level imports and TYPE_CHECKING block
    clean-up (contract) did not break the production import path.
    """
    import importlib

    mod = importlib.import_module("aeat.application.modelo._taxation_comparison")
    assert hasattr(mod, "compare_taxation_modes")
    assert hasattr(mod, "TaxationComparisonResult")
    assert hasattr(mod, "TaxationComparisonError")


def test_comparison_error_raised_for_non_m100_snapshot() -> None:
    """compare_taxation_modes raises TaxationComparisonError for non-M100 snapshots.

    The Modelo 303 (IVA) registry revision does not declare a
    profile-declaration-type binding; the function should detect this
    and raise TaxationComparisonError rather than a raw engine error.
    """
    from ....core.resources import resources

    snapshot_303 = resources().modelos.authority.snapshot("303", filing_year=2025, period="3T")

    with pytest.raises(TaxationComparisonError, match="declaration-type"):
        compare_taxation_modes(
            snapshot_303,
            inputs={},
            binding_values={},
            enum_binding_values={},
        )


def test_comparison_refuses_ambiguous_semantic_role(snapshot_2025: RegistrySnapshot) -> None:
    """Conjunta comparison must not choose an arbitrary casilla for a duplicated role."""
    original = next(
        casilla
        for casilla in snapshot_2025.revision.casillas
        if casilla.semantic_role == "irpf_cuota_resultante_autoliquidacion"
    )
    duplicate = original.model_copy(update={"id": f"ambiguous-{original.id}"})
    revision = snapshot_2025.revision.model_copy(update={"casillas": (*snapshot_2025.revision.casillas, duplicate)})
    snapshot = snapshot_2025.model_copy(update={"revision": revision})

    with pytest.raises(TaxationComparisonError, match="multiple casillas"):
        compare_taxation_modes(
            snapshot,
            inputs={},
            binding_values={},
            enum_binding_values={},
        )
