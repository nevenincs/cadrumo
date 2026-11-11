"""Box 0150 of the Modelo 100, the art. 23.2 LIRPF dwelling-rental reduction, in every supported ejercicio.

Art. 23.2 LIRPF as worded on 31 December 2021 reduces the positive net income of
a dwelling rental by 60 per cent whatever the contract (Manual Renta 2022 and
2023: "se reducirá en un 60 por 100"). Ley 12/2023 replaced that wording from
1 January 2024 with the 90, 70, 60 and 50 per cent tiers. The bundled legal
declaration of the earlier wording closes on the day before, so the regime each
ejercicio follows comes from that declaration and the ejercicios from the
registry's support envelope, never from a year written here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..authority import PinnedAuthorityOperation
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..errors import RegistryValidationError
from ..formula_runtime import RegistryCalculationEntry, RegistryCalculationResult, calculate_registry_snapshot
from ..schema import RegistrySnapshot
from .authored_editions import filing_year_envelope
from .m100_rental_reduccion_art23_2_scenarios import FORMULA_ID, TIER_BINDING
from .modelo_100_registry_support import neutral_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ELIGIBILITY: CasillaId = validated_casilla_id("0100", surface="_ELIGIBILITY")
_RENT: CasillaId = validated_casilla_id("0102", surface="_RENT")
_REPAIRS: CasillaId = validated_casilla_id("0104", surface="_REPAIRS")
_NET_INCOME: CasillaId = validated_casilla_id("0149", surface="_NET_INCOME")
_REDUCTION: CasillaId = validated_casilla_id("0150", surface="_REDUCTION")
_WORDING_2021 = "ley-35-2006:art-23-2021"
_WORDING_2021_RATE = Decimal("0.60")
_RENT_AMOUNT = Decimal("10000.00")


def _snapshot(registry_snapshot: Callable[..., RegistrySnapshot], year: int) -> RegistrySnapshot:
    return registry_snapshot("100", year, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(
    snapshot: RegistrySnapshot, year: int, inputs: dict[CasillaId, Decimal], tier: str | None = None
) -> RegistryCalculationResult:
    bindings = tuple(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in bindings if binding.id != TIER_BINDING
    )
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {"renta-profile-declaration-type": Decimal(1)}
    if tier is not None:
        enums[TIER_BINDING] = tier
    return calculate_registry_snapshot(
        snapshot,
        inputs={**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals)},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )


def _wording_2021_governs(authority: PinnedAuthorityOperation, year: int) -> bool:
    effective_to = authority.legal_reference(_WORDING_2021).effective_to
    return effective_to is not None and date(year, 12, 31) <= effective_to


def _reduction_entry(result: RegistryCalculationResult) -> RegistryCalculationEntry:
    return next(entry for entry in result.entries if entry.target_casilla_id == _REDUCTION)


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_0150_applies_the_art23_2_wording_in_force_in_the_ejercicio(
    registry_snapshot: Callable[..., RegistrySnapshot], registry_authority: PinnedAuthorityOperation, year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)
    eligible = {_ELIGIBILITY: Decimal(1), _RENT: _RENT_AMOUNT}

    if _wording_2021_governs(registry_authority, year):
        assert TIER_BINDING not in {binding.id for binding in snapshot.revision.bindings}
        result = _calculate(snapshot, year, eligible)
        assert result.values[_NET_INCOME] == _RENT_AMOUNT
        assert result.values[_REDUCTION] == _RENT_AMOUNT * _WORDING_2021_RATE
        assert _reduction_entry(result).legal_refs == (_WORDING_2021,)
        return

    result = _calculate(snapshot, year, eligible, tier="tier-50")
    assert result.values[_REDUCTION] == Decimal("5000.00")
    entry = _reduction_entry(result)
    assert entry.formula_id == FORMULA_ID
    assert TIER_BINDING in entry.operand_refs
    with pytest.raises(RegistryValidationError, match="has no supplied value"):
        _calculate(snapshot, year, eligible)


@pytest.mark.parametrize("year", filing_year_envelope().years)
def test_0150_never_reduces_a_loss_or_an_ineligible_rental(
    registry_snapshot: Callable[..., RegistrySnapshot], year: int
) -> None:
    snapshot = _snapshot(registry_snapshot, year)

    loss = _calculate(snapshot, year, {_ELIGIBILITY: Decimal(1), _RENT: Decimal("100.00"), _REPAIRS: Decimal("250.00")})
    ineligible = _calculate(snapshot, year, {_ELIGIBILITY: Decimal(0), _RENT: _RENT_AMOUNT})

    assert loss.values[_NET_INCOME] < Decimal(0)
    assert loss.values[_REDUCTION] == Decimal("0.00")
    assert ineligible.values[_REDUCTION] == Decimal("0.00")
