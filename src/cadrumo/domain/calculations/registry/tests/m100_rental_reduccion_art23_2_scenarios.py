"""Scenario bodies for test_m100_rental_reduccion_art23_2, called by its authored-source and published-authority tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ..errors import RegistryValidationError
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..schema import RegistrySnapshot
from .modelo_100_registry_support import M100_NO_DESCENDANT_MATERNIDAD_BINDINGS

FILING_DATE = date(2024, 12, 31)

TIER_BINDING = "renta-rental-reduccion-art-23-2-tier"

FORMULA_ID = "renta-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2"


def calculate(
    snapshot: RegistrySnapshot,
    *,
    inputs: dict[str, Decimal],
    tier: str | None = None,
) -> RegistryCalculationResult:
    enum_bindings = {"renta-profile-tax-residence-ccaa": "madrid"}
    if tier is not None:
        enum_bindings[TIER_BINDING] = tier
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": FILING_DATE},
        binding_values={
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-profile-incremento-guarderia": Decimal("0"),
            "renta-profile-cotizaciones-ss-madre": Decimal("0"),
            **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
            "renta-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
            "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        },
        enum_binding_values=enum_bindings,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal("0"),
            "renta-modelo-131-pagos-fraccionados": Decimal("0"),
        },
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1980, 1, 1)},
    )


def check_tier_binding_is_layout_and_law_grounded(m100_2024_snapshot: RegistrySnapshot) -> None:
    binding = next(binding for binding in m100_2024_snapshot.revision.bindings if binding.id == TIER_BINDING)

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


def check_0150_uses_operator_selected_art23_2_tier(
    m100_2024_snapshot: RegistrySnapshot,
    tier: str,
    expected: Decimal,
) -> None:
    result = calculate(
        m100_2024_snapshot,
        inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
        tier=tier,
    )

    assert result.values["0149"] == Decimal("10000.00")
    assert result.values["0150"] == expected
    assert result.values["0154"] == Decimal("10000.00") - expected

    entry = next(entry for entry in result.entries if entry.target_casilla_id == "0150")
    assert entry.formula_id == FORMULA_ID
    assert entry.legal_refs == ("ley-35-2006:art-23",)
    assert entry.source_refs == ("aeat-renta-2024-manual-parte1", "lirpf-cuota-chain-authority")
    assert TIER_BINDING in entry.operand_refs
    assert f"renta-rental-reduccion-rate-{tier}" in entry.operand_refs


def check_0150_unchecked_eligibility_does_not_require_or_apply_tier(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    result = calculate(
        m100_2024_snapshot,
        inputs={"0100": Decimal("0"), "0102": Decimal("10000.00")},
    )

    assert result.values["0149"] == Decimal("10000.00")
    assert result.values["0150"] == Decimal("0.00")

    entry = next(entry for entry in result.entries if entry.target_casilla_id == "0150")
    assert TIER_BINDING not in entry.operand_refs


def check_0150_non_positive_0149_does_not_create_positive_reduction(
    m100_2024_snapshot: RegistrySnapshot,
    inputs: dict[str, Decimal],
) -> None:
    result = calculate(m100_2024_snapshot, inputs=inputs)

    assert result.values["0149"] <= Decimal("0")
    assert result.values["0150"] == Decimal("0.00")


def check_0150_positive_checked_rental_fails_closed_without_tier(
    m100_2024_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        calculate(
            m100_2024_snapshot,
            inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
        )


def check_0150_rejects_unknown_tier_key(m100_2024_snapshot: RegistrySnapshot) -> None:
    with pytest.raises(RegistryValidationError, match="dispatch_table is missing key"):
        calculate(
            m100_2024_snapshot,
            inputs={"0100": Decimal("1"), "0102": Decimal("10000.00")},
            tier="tier-65",
        )
