"""Ephemeral M303 differentiated-sector deduction row projection."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG, CasillaId, IvaDeductionFactKind, ProrrataRegisterRegime
from ...bienes_inversion import RegistroRegularizacionResult
from ...prorrata_register import ProrrataRegister
from ._errors import RegistryValidationError
from ._schema import CasillaDefinition, ModeloRevision
from ._schema_input_kind import InputKind

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
_FIELDS = (
    *(
        field
        for family in (
            "domestic-current",
            "domestic-investment",
            "import-current",
            "import-investment",
            "intra-eu-current",
            "intra-eu-investment",
            "reagp",
            "rectification",
        )
        for field in (f"{family}-base", f"{family}-cuota")
    ),
    "investment-regularisation",
    "total",
)
_PREFIX = ("iva", "deducciones", "sectores-diferenciados")


class IvaDifferentiatedDeductionContributionProtocol(Protocol):
    sector_id: str
    deduction_fact_kind: IvaDeductionFactKind
    source_ledger_ids: tuple[str, ...]
    base_amount: Decimal
    deducible_iva_amount: Decimal


class M303DifferentiatedDeductionEndpointValue(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    casilla_id: CasillaId
    value: Decimal


class M303DifferentiatedDeductionRowProjection(BaseModel):
    model_config = STRICT_FROZEN_CONFIG
    slot: int = Field(ge=1, le=2)
    sector_id: str
    regime: ProrrataRegisterRegime
    percentage: Decimal
    endpoints: tuple[M303DifferentiatedDeductionEndpointValue, ...] = Field(min_length=18, max_length=18)


def project_m303_differentiated_deduction_rows(
    revision: ModeloRevision,
    *,
    register: ProrrataRegister,
    ejercicio: int,
    contributions: Iterable[IvaDifferentiatedDeductionContributionProtocol],
    regularisation_result: RegistroRegularizacionResult | None = None,
) -> tuple[M303DifferentiatedDeductionRowProjection, ...]:
    """Project the two canonical sector rows, refusing every incomplete authority."""
    endpoints = _endpoint_matrix(revision)
    definitions = register.sector_definitions
    if not definitions:
        return ()
    if len(definitions) != 2:
        raise RegistryValidationError("modelo 303 differentiated deductions require exactly two sectors")
    sector_ids = tuple(item.sector_id for item in definitions)
    apportioned = tuple(contributions)
    if any(
        item.deduction_fact_kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
        for item in apportioned
    ):
        raise RegistryValidationError(
            "investment-goods regularisation cannot enter the ordinary deduction contribution channel"
        )
    regularisations = () if regularisation_result is None else regularisation_result.sector_contributions
    if regularisation_result is not None:
        if regularisation_result.regularizacion_year != ejercicio:
            raise RegistryValidationError("bienes-inversion regularisation year does not match the projection year")
        if regularisation_result.pending_percentage_count:
            raise RegistryValidationError("bienes-inversion regularisation has unresolved sector percentages")
        row_identifiers = [row.identifier for row in regularisation_result.rows]
        if len(row_identifiers) != len(set(row_identifiers)):
            raise RegistryValidationError("bienes-inversion regularisation has duplicate canonical asset rows")
        row_by_id = {row.identifier: row for row in regularisation_result.rows}
        row_ids = set(row_by_id)
        contribution_ids = {item.asset_id for item in regularisations}
        if not contribution_ids.issubset(row_ids):
            raise RegistryValidationError("bienes-inversion regularisation contribution has no canonical asset row")
        if any(
            row_by_id[item.asset_id].prorrata_sector_id != item.prorrata_sector_id
            for item in regularisations
            if item.asset_id in row_by_id
        ):
            raise RegistryValidationError("bienes-inversion regularisation asset and contribution sectors differ")
    keys = [(item.sector_id, item.deduction_fact_kind) for item in apportioned]
    if duplicates := sorted(key for key, count in Counter(keys).items() if count > 1):
        raise RegistryValidationError(f"differentiated deduction contributions are double-consumed: {duplicates!r}")
    ledger_ids = [ledger_id for item in apportioned for ledger_id in item.source_ledger_ids]
    if any(not ledger_id.strip() for ledger_id in ledger_ids):
        raise RegistryValidationError("differentiated deduction contribution has blank source ledger identity")
    if duplicates := sorted(key for key, count in Counter(ledger_ids).items() if count > 1):
        raise RegistryValidationError(f"differentiated deduction source ledgers are double-consumed: {duplicates!r}")
    asset_ids = [item.asset_id for item in regularisations]
    if any(not asset_id.strip() for asset_id in asset_ids):
        raise RegistryValidationError("regularisation contribution has blank asset identity")
    if duplicates := sorted(key for key, count in Counter(asset_ids).items() if count > 1):
        raise RegistryValidationError(f"regularisation contributions are double-consumed: {duplicates!r}")
    unknown = sorted(
        {item.sector_id for item in apportioned if item.sector_id not in sector_ids}
        | {item.prorrata_sector_id for item in regularisations if item.prorrata_sector_id not in sector_ids},
        key=lambda item: "" if item is None else item,
    )
    if unknown:
        raise RegistryValidationError(
            f"differentiated deduction inputs have unknown or missing sector identity: {unknown!r}"
        )
    if regularisation_result is not None:
        projected_regularisation_total = sum((item.amount for item in regularisations), Decimal("0"))
        if projected_regularisation_total != regularisation_result.proposed_casilla_43:
            raise RegistryValidationError("sector regularisation contributions do not equal canonical casilla 43")
    projected: list[M303DifferentiatedDeductionRowProjection] = []
    for slot, sector_id in enumerate(sector_ids, 1):
        entry = register.entry_for(ejercicio, sector_id=sector_id)
        if entry is None or entry.interrupted or entry.regime is ProrrataRegisterRegime.NINGUNA:
            raise RegistryValidationError(
                f"differentiated sector {sector_id!r} has no applicable regime for {ejercicio}"
            )
        if entry.provisional_percentage is None:
            raise RegistryValidationError(
                f"differentiated sector {sector_id!r} has no resolved percentage for {ejercicio}"
            )
        amounts: list[Decimal] = []
        total = Decimal("0")
        for kind in _KINDS:
            selected = tuple(
                item for item in apportioned
                if item.sector_id == sector_id and item.deduction_fact_kind is kind
            )
            if len(selected) != 1:
                raise RegistryValidationError(
                    f"differentiated sector {sector_id!r} has incomplete apportioned source {kind.value!r}"
                )
            base = selected[0].base_amount
            cuota = selected[0].deducible_iva_amount
            amounts.extend((base, cuota))
            total += cuota
        regularisation = sum(
            (item.amount for item in regularisations if item.prorrata_sector_id == sector_id), Decimal("0")
        )
        amounts.extend((regularisation, total + regularisation))
        projected.append(
            M303DifferentiatedDeductionRowProjection(
                slot=slot,
                sector_id=sector_id,
                regime=entry.regime,
                percentage=entry.provisional_percentage,
                endpoints=tuple(
                    _endpoint_value(endpoints[slot][field], value)
                    for field, value in zip(_FIELDS, amounts, strict=True)
                ),
            )
        )
    return tuple(projected)


def _endpoint_matrix(revision: ModeloRevision) -> dict[int, dict[str, CasillaDefinition]]:
    resolved: dict[int, dict[str, CasillaDefinition]] = {}
    for casilla in revision.casillas:
        section = tuple(casilla.section)
        if section[:3] != _PREFIX:
            continue
        if len(section) != 5 or section[3] not in {"sector_1", "sector_2"} or section[4] not in _FIELDS:
            raise RegistryValidationError(f"invalid differentiated deduction endpoint section {section!r}")
        if (
            casilla.input_kind is not InputKind.PROJECTION_ONLY
            or casilla.formula
            or casilla.binding
            or casilla.alternate_bindings
        ):
            raise RegistryValidationError(
                f"differentiated deduction endpoint {casilla.id!r} has an independent producer"
            )
        slot = int(section[3][-1])
        if section[4] in resolved.setdefault(slot, {}):
            raise RegistryValidationError(f"duplicate differentiated deduction endpoint {slot}/{section[4]}")
        resolved[slot][section[4]] = casilla
    expected = {1: set(_FIELDS), 2: set(_FIELDS)}
    if {slot: set(fields) for slot, fields in resolved.items()} != expected:
        raise RegistryValidationError("modelo 303 differentiated deduction endpoint matrix is incomplete or malformed")
    return resolved


def _endpoint_value(casilla: CasillaDefinition, value: Decimal) -> M303DifferentiatedDeductionEndpointValue:
    if casilla.constraints is not None and (reason := casilla.constraints.violates(value)) is not None:
        raise RegistryValidationError(f"differentiated deduction endpoint {casilla.id!r} rejects value: {reason}")
    return M303DifferentiatedDeductionEndpointValue(casilla_id=casilla.id, value=value)


__all__ = [
    "M303DifferentiatedDeductionEndpointValue",
    "M303DifferentiatedDeductionRowProjection",
    "project_m303_differentiated_deduction_rows",
]
