"""Modelo 100 2024 Art. 23.2 housing-rental reduction calculation tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core import RegistryAuthorityGrade
from ..errors import RegistryValidationError
from .._formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .._schema import RegistrySnapshot
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FILING_DATE = date(2024, 12, 31)
_TIER_BINDING = "renta-2024-rental-reduccion-art-23-2-tier"
_FORMULA_ID = "renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2"


@pytest.fixture(scope="module")
def m100_2024_snapshot(registry_snapshot: Callable[..., RegistrySnapshot]) -> RegistrySnapshot:
    """A formula-runtime calculation claim, never a filing one."""
    return registry_snapshot(
        "100",
        2024,
        "0A",
        revision_id="2024",
        grade=RegistryAuthorityGrade.CALCULATION,
    )


def _calculate(
    snapshot: RegistrySnapshot,
    *,
    inputs: dict[str, Decimal],
    tier: str | None = None,
) -> RegistryCalculationResult:
    enum_bindings = {"renta-2024-profile-tax-residence-ccaa": "madrid"}
    if tier is not None:
        enum_bindings[_TIER_BINDING] = tier
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": _FILING_DATE},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
            "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-2024-profile-incremento-guarderia": Decimal("0"),
            "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-2024-profile-descendientes-guarderia": Decimal("0"),
            **_m100_2024_deduccion_maternidad_bindings(),
            "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
            "renta-2024-profile-declaration-type": Decimal("1"),
            "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2024-profile-marriage-full-year": Decimal("0"),
            "renta-2024-profile-marriage-month-start": Decimal("0"),
            "renta-2024-profile-marriage-month-end": Decimal("0"),
            "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values=enum_bindings,
        relation_values={
            "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
            "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
            "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
            "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
            "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
        },
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )


def test_tier_binding_is_layout_and_law_grounded(m100_2024_snapshot: RegistrySnapshot) -> None:
    binding = next(binding for binding in m100_2024_snapshot.revision.bindings if binding.id == _TIER_BINDING)

    assert binding.source_refs == (
        "aeat-dr-100-2024-dictionary",
        "aeat-renta-2024-manual-parte1",
        "lirpf-cuota-chain-authority",
    )
    assert m100_2024_snapshot.sources["aeat-dr-100-2024-dictionary"].evidence_tier == "layout_authority"

    citations = {citation.source_ref: citation.required_text for citation in binding.source_citations}
    assert set(citations["aeat-renta-2024-manual-parte1"]) == {
        "90 por 100",
        "70 por 100",
        "60 por 100",
        "50 por 100",
    }


@pytest.mark.parametrize(
    ("tier", "expected"),
    (
        ("tier-50", Decimal("5000.00")),
        ("tier-60", Decimal("6000.00")),
        ("tier-70", Decimal("7000.00")),
        ("tier-90", Decimal("9000.00")),
    ),
)
def test_0150_uses_operator_selected_art23_2_tier(
    m100_2024_snapshot: RegistrySnapshot,
    tier: str,
    expected: Decimal,
) -> None:
    result = _calculate(
        m100_2024_snapshot,
        inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
        tier=tier,
    )

    assert result.values["0149"] == Decimal("10000.00")
    assert result.values["0150"] == expected
    assert result.values["0154"] == Decimal("10000.00") - expected

    entry = next(entry for entry in result.entries if entry.target_casilla_id == "0150")
    assert entry.formula_id == _FORMULA_ID
    assert entry.legal_refs == ("ley-35-2006:art-23",)
    assert entry.source_refs == ("aeat-renta-2024-manual-parte1", "lirpf-cuota-chain-authority")
    assert _TIER_BINDING in entry.operand_refs
    assert f"renta-2024-rental-reduccion-rate-{tier}" in entry.operand_refs


def test_0150_unchecked_eligibility_does_not_require_or_apply_tier(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    result = _calculate(
        m100_2024_snapshot,
        inputs={"0100": Decimal("0"), "0102": Decimal("10000.00")},
    )

    assert result.values["0149"] == Decimal("10000.00")
    assert result.values["0150"] == Decimal("0.00")

    entry = next(entry for entry in result.entries if entry.target_casilla_id == "0150")
    assert _TIER_BINDING not in entry.operand_refs


@pytest.mark.parametrize(
    "inputs",
    (
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("100.00")},
        {"0100": Decimal("1"), "0102": Decimal("100.00"), "0104": Decimal("250.00")},
    ),
)
def test_0150_non_positive_0149_does_not_create_positive_reduction(
    m100_2024_snapshot: RegistrySnapshot,
    inputs: dict[str, Decimal],
) -> None:
    result = _calculate(m100_2024_snapshot, inputs=inputs)

    assert result.values["0149"] <= Decimal("0")
    assert result.values["0150"] == Decimal("0.00")


def test_0150_positive_checked_rental_fails_closed_without_tier(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        _calculate(
            m100_2024_snapshot,
            inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
        )


def test_0150_rejects_unknown_tier_key(m100_2024_snapshot: RegistrySnapshot) -> None:
    with pytest.raises(RegistryValidationError, match="dispatch_table is missing key"):
        _calculate(
            m100_2024_snapshot,
            inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
            tier="tier-65",
        )
