"""Ephemeral M303 differentiated-sector deduction row projection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from ....core import IvaDeductionFactKind, ProrrataRegisterRegime, regime_apportions_deduction
from ....core.filing_projection_ref import (
    M303DifferentiatedDeductionProjectionField,
    M303DifferentiatedDeductionProjectionRef,
)
from ....core.models import STRICT_FROZEN_CONFIG
from ...bienes_inversion import RegistroRegularizacionResult
from ...prorrata_register import ProrrataRegister
from .errors import RegistryValidationError

_KINDS = (
    IvaDeductionFactKind.DOMESTIC_CURRENT,
    IvaDeductionFactKind.DOMESTIC_INVESTMENT,
    IvaDeductionFactKind.IMPORT_CURRENT,
    IvaDeductionFactKind.IMPORT_INVESTMENT,
    IvaDeductionFactKind.INTRA_EU_CURRENT,
    IvaDeductionFactKind.INTRA_EU_INVESTMENT,
    IvaDeductionFactKind.REAGP_COMPENSATION,
    IvaDeductionFactKind.RECTIFICATION,
)
_FIELDS = tuple(M303DifferentiatedDeductionProjectionField)


class IvaDifferentiatedDeductionContributionProtocol(Protocol):
    sector_id: str
    deduction_fact_kind: IvaDeductionFactKind
    source_ledger_ids: tuple[str, ...]
    base_amount: Decimal
    deducible_iva_amount: Decimal


class _RegularisationContributionProtocol(Protocol):
    asset_id: str
    prorrata_sector_id: str | None
    amount: Decimal


class M303DifferentiatedDeductionEndpointValue(BaseModel):
    """One projected endpoint value for a differentiated-sector deduction row."""

    model_config = STRICT_FROZEN_CONFIG
    projection_ref: M303DifferentiatedDeductionProjectionRef
    value: Decimal


class M303DifferentiatedDeductionRowProjection(BaseModel):
    """A differentiated-sector prorrata deduction row projected across its 18 endpoints."""

    model_config = STRICT_FROZEN_CONFIG
    slot: int = Field(ge=1, le=2)
    sector_id: str
    regime: ProrrataRegisterRegime
    percentage: Decimal
    endpoints: tuple[M303DifferentiatedDeductionEndpointValue, ...] = Field(min_length=18, max_length=18)


def project_m303_differentiated_deduction_rows(
    *,
    projection_refs: tuple[M303DifferentiatedDeductionProjectionRef, ...],
    register: ProrrataRegister,
    ejercicio: int,
    contributions: Iterable[IvaDifferentiatedDeductionContributionProtocol],
    regularisation_result: RegistroRegularizacionResult | None = None,
) -> tuple[M303DifferentiatedDeductionRowProjection, ...]:
    """Project the two canonical sector rows, refusing every incomplete authority."""
    endpoints = _endpoint_matrix(projection_refs)
    sector_ids = _sector_ids(register)
    if not sector_ids:
        return ()
    apportioned = tuple(contributions)
    regularisations = () if regularisation_result is None else regularisation_result.sector_contributions
    _validate_ordinary_contributions(apportioned)
    _validate_regularisation_result(regularisation_result, ejercicio, regularisations)
    _validate_consumption_identities(apportioned, regularisations)
    _validate_sector_identities(sector_ids, apportioned, regularisations)
    _validate_regularisation_total(regularisation_result, regularisations)
    return tuple(
        _project_sector_row(
            slot=slot,
            sector_id=sector_id,
            register=register,
            ejercicio=ejercicio,
            apportioned=apportioned,
            regularisations=regularisations,
            endpoints=endpoints[slot],
        )
        for slot, sector_id in enumerate(sector_ids, 1)
    )


def _sector_ids(register: ProrrataRegister) -> tuple[str, ...]:
    definitions = register.sector_definitions
    if not definitions:
        return ()
    if len(definitions) != 2:
        raise RegistryValidationError("modelo 303 differentiated deductions require exactly two sectors")
    return tuple(item.sector_id for item in definitions)


def _validate_ordinary_contributions(
    contributions: tuple[IvaDifferentiatedDeductionContributionProtocol, ...],
) -> None:
    regularisation_kind = IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    if any(item.deduction_fact_kind is regularisation_kind for item in contributions):
        raise RegistryValidationError(
            "investment-goods regularisation cannot enter the ordinary deduction contribution channel"
        )


def _validate_regularisation_result(
    result: RegistroRegularizacionResult | None,
    ejercicio: int,
    contributions: tuple[_RegularisationContributionProtocol, ...],
) -> None:
    if result is None:
        return
    if result.regularizacion_year != ejercicio:
        raise RegistryValidationError("bienes-inversion regularisation year does not match the projection year")
    if result.pending_percentage_count:
        raise RegistryValidationError("bienes-inversion regularisation has unresolved sector percentages")
    row_by_id = {row.identifier: row for row in result.rows}
    if len(row_by_id) != len(result.rows):
        raise RegistryValidationError("bienes-inversion regularisation has duplicate canonical asset rows")
    if not {item.asset_id for item in contributions}.issubset(row_by_id):
        raise RegistryValidationError("bienes-inversion regularisation contribution has no canonical asset row")
    if any(row_by_id[item.asset_id].prorrata_sector_id != item.prorrata_sector_id for item in contributions):
        raise RegistryValidationError("bienes-inversion regularisation asset and contribution sectors differ")


def _validate_consumption_identities(
    contributions: tuple[IvaDifferentiatedDeductionContributionProtocol, ...],
    regularisations: tuple[_RegularisationContributionProtocol, ...],
) -> None:
    keys = [(item.sector_id, item.deduction_fact_kind) for item in contributions]
    if duplicates := sorted(key for key, count in Counter(keys).items() if count > 1):
        raise RegistryValidationError(f"differentiated deduction contributions are double-consumed: {duplicates!r}")
    _validate_unique_identities(
        [ledger_id for item in contributions for ledger_id in item.source_ledger_ids],
        blank_error="differentiated deduction contribution has blank source ledger identity",
        duplicate_error="differentiated deduction source ledgers are double-consumed",
    )
    _validate_unique_identities(
        [item.asset_id for item in regularisations],
        blank_error="regularisation contribution has blank asset identity",
        duplicate_error="regularisation contributions are double-consumed",
    )


def _validate_unique_identities(identifiers: list[str], *, blank_error: str, duplicate_error: str) -> None:
    if any(not identifier.strip() for identifier in identifiers):
        raise RegistryValidationError(blank_error)
    if duplicates := sorted(key for key, count in Counter(identifiers).items() if count > 1):
        raise RegistryValidationError(f"{duplicate_error}: {duplicates!r}")


def _validate_sector_identities(
    sector_ids: tuple[str, ...],
    contributions: tuple[IvaDifferentiatedDeductionContributionProtocol, ...],
    regularisations: tuple[_RegularisationContributionProtocol, ...],
) -> None:
    unknown = sorted(
        {item.sector_id for item in contributions if item.sector_id not in sector_ids}
        | {item.prorrata_sector_id for item in regularisations if item.prorrata_sector_id not in sector_ids},
        key=lambda item: "" if item is None else item,
    )
    if unknown:
        raise RegistryValidationError(
            f"differentiated deduction inputs have unknown or missing sector identity: {unknown!r}"
        )


def _validate_regularisation_total(
    result: RegistroRegularizacionResult | None,
    regularisations: tuple[_RegularisationContributionProtocol, ...],
) -> None:
    if (
        result is not None
        and sum((item.amount for item in regularisations), Decimal("0")) != result.proposed_casilla_43
    ):
        raise RegistryValidationError("sector regularisation contributions do not equal canonical casilla 43")


def _project_sector_row(
    *,
    slot: int,
    sector_id: str,
    register: ProrrataRegister,
    ejercicio: int,
    apportioned: tuple[IvaDifferentiatedDeductionContributionProtocol, ...],
    regularisations: tuple[_RegularisationContributionProtocol, ...],
    endpoints: dict[
        M303DifferentiatedDeductionProjectionField,
        M303DifferentiatedDeductionProjectionRef,
    ],
) -> M303DifferentiatedDeductionRowProjection:
    entry = register.entry_for(ejercicio, sector_id=sector_id)
    if entry is None or entry.interrupted or not regime_apportions_deduction(entry.regime):
        raise RegistryValidationError(f"differentiated sector {sector_id!r} has no applicable regime for {ejercicio}")
    if entry.provisional_percentage is None:
        raise RegistryValidationError(f"differentiated sector {sector_id!r} has no resolved percentage for {ejercicio}")
    amounts = _sector_amounts(sector_id, apportioned, regularisations)
    return M303DifferentiatedDeductionRowProjection(
        slot=slot,
        sector_id=sector_id,
        regime=entry.regime,
        percentage=entry.provisional_percentage,
        endpoints=tuple(
            _endpoint_value(endpoints[field], value) for field, value in zip(_FIELDS, amounts, strict=True)
        ),
    )


def _sector_amounts(
    sector_id: str,
    contributions: tuple[IvaDifferentiatedDeductionContributionProtocol, ...],
    regularisations: tuple[_RegularisationContributionProtocol, ...],
) -> tuple[Decimal, ...]:
    amounts: list[Decimal] = []
    total = Decimal("0")
    for kind in _KINDS:
        selected = tuple(
            item for item in contributions if item.sector_id == sector_id and item.deduction_fact_kind is kind
        )
        if len(selected) != 1:
            raise RegistryValidationError(
                f"differentiated sector {sector_id!r} has incomplete apportioned source {kind.value!r}"
            )
        amounts.extend((selected[0].base_amount, selected[0].deducible_iva_amount))
        total += selected[0].deducible_iva_amount
    regularisation = sum(
        (item.amount for item in regularisations if item.prorrata_sector_id == sector_id), Decimal("0")
    )
    return (*amounts, regularisation, total + regularisation)


def _endpoint_matrix(
    refs: tuple[M303DifferentiatedDeductionProjectionRef, ...],
) -> dict[int, dict[M303DifferentiatedDeductionProjectionField, M303DifferentiatedDeductionProjectionRef]]:
    resolved: dict[
        int,
        dict[M303DifferentiatedDeductionProjectionField, M303DifferentiatedDeductionProjectionRef],
    ] = {}
    casilla_ids = tuple(ref.casilla_id for ref in refs)
    if len(set(casilla_ids)) != len(casilla_ids):
        raise RegistryValidationError("differentiated deduction references duplicate endpoint casillas")
    for ref in refs:
        if ref.field in resolved.setdefault(ref.slot, {}):
            raise RegistryValidationError(
                f"duplicate differentiated deduction projection reference {ref.slot}/{ref.field.value}",
            )
        resolved[ref.slot][ref.field] = ref
    expected = {1: set(_FIELDS), 2: set(_FIELDS)}
    if {slot: set(fields) for slot, fields in resolved.items()} != expected:
        raise RegistryValidationError(
            "modelo 303 differentiated deduction endpoint matrix is incomplete or malformed",
        )
    return resolved


def _endpoint_value(
    ref: M303DifferentiatedDeductionProjectionRef,
    value: Decimal,
) -> M303DifferentiatedDeductionEndpointValue:
    return M303DifferentiatedDeductionEndpointValue(projection_ref=ref, value=value)


__all__ = [
    "M303DifferentiatedDeductionEndpointValue",
    "M303DifferentiatedDeductionRowProjection",
    "project_m303_differentiated_deduction_rows",
]
