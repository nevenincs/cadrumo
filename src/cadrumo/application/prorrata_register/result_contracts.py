"""Canonical private result and public projection schemas for prorrata operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.prorrata_register.register import (
    ProrrataOperatorGrossDeclaration,
    ProrrataRegister,
    ProrrataRegisterEntry,
    SectorDefinition,
)
from . import operation_requests
from .projection_contracts import (
    GROSS_DECLARATION_OPERATION_IDS,
    PRORRATA_ELECTION_REFUSAL_CODE,
    PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
    PRORRATA_VALIDATION_REFUSAL_CODE,
    PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    ProrrataFindingProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
    ProrrataSeedSourceProjection,
)


class ProrrataListedReference(BaseModel):
    """The canonical reference of one listed entry's percentage in force."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    reference_id: str
    kind: str


class ProrrataOperationExecutionResult(BaseModel):
    """Private complete outcome retained under secure operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: operation_requests.ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    register_snapshot: ProrrataRegister | None = None
    listed_references: tuple[ProrrataListedReference | None, ...] = ()
    entry: ProrrataRegisterEntry | None = None
    sector_definition: SectorDefinition | None = None
    gross_declaration: ProrrataOperatorGrossDeclaration | None = None
    seed_source: ProrrataSeedSourceProjection | None = None
    findings: tuple[ProrrataFindingProjection, ...] = ()
    prior_ejercicio: int | None = None
    count: NonNegativeInt | None = None
    refusal: ProrrataRefusalProjection | None = None

    @model_validator(mode="after")
    def _result_arm_is_closed(self) -> ProrrataOperationExecutionResult:
        if self.outcome == "refused":
            _validate_refused_execution_result(self)
        else:
            _validate_successful_execution_result(self)
        return self


def _validate_refused_execution_result(result: ProrrataOperationExecutionResult) -> None:
    success_values = (
        result.register_snapshot,
        result.entry,
        result.sector_definition,
        result.gross_declaration,
        result.seed_source,
        result.prior_ejercicio,
        result.count,
    )
    if (
        result.operation_id == "list"
        or result.refusal is None
        or any(value is not None for value in success_values)
        or result.findings
    ):
        raise ValueError("prorrata refusal result has an incompatible payload")


def _validate_successful_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if result.refusal is not None or result.register_snapshot is None or result.count is None:
        raise ValueError("prorrata success result is incomplete")
    if result.operation_id != "list" and (result.gross_declaration is not None) != (
        result.operation_id in GROSS_DECLARATION_OPERATION_IDS
    ):
        raise ValueError("prorrata gross declaration differs from its operation")
    if result.operation_id == "list":
        _validate_list_execution_result(result)
    elif result.operation_id in GROSS_DECLARATION_OPERATION_IDS:
        _validate_gross_declaration_execution_result(result)
    elif result.operation_id == "declare_sector":
        _validate_sector_declaration_execution_result(result)
    else:
        _validate_entry_execution_result(result)


def _validate_list_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if any(
        value is not None
        for value in (result.entry, result.sector_definition, result.gross_declaration, result.seed_source)
    ):
        raise ValueError("prorrata list result contains mutation details")
    if result.register_snapshot is None or len(result.listed_references) != len(result.register_snapshot.entries):
        raise ValueError("prorrata list result names a reference per entry")


def _validate_sector_declaration_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if result.sector_definition is None or any(
        value is not None for value in (result.entry, result.seed_source, result.prior_ejercicio)
    ):
        raise ValueError("prorrata sector declaration result is incomplete")


def _require_complete_gross_result(
    result: ProrrataOperationExecutionResult,
) -> tuple[ProrrataRegister, ProrrataOperatorGrossDeclaration]:
    register = result.register_snapshot
    declaration = result.gross_declaration
    if (
        register is None
        or declaration is None
        or any(value is not None for value in (result.entry, result.sector_definition, result.seed_source))
        or result.prior_ejercicio is not None
        or result.findings
        or result.count != len(register.gross_declarations)
    ):
        raise ValueError("prorrata gross declaration result is incomplete")
    return register, declaration


def _validate_gross_declaration_execution_result(result: ProrrataOperationExecutionResult) -> None:
    register, declaration = _require_complete_gross_result(result)
    held = register.gross_declaration_for(declaration.period, sector_id=declaration.sector_id)
    if (result.operation_id == "declare_gross") != (held == declaration):
        raise ValueError("prorrata gross declaration result contradicts its committed register")
    if result.operation_id == "remove_gross" and held is not None:
        raise ValueError("prorrata gross removal result still holds the removed declaration")


def _validate_entry_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if result.entry is None or result.sector_definition is not None:
        raise ValueError("prorrata entry mutation result is incomplete")
    if (result.operation_id == "seed") != (result.seed_source is not None):
        raise ValueError("prorrata whole-seed source differs from its operation")
    if (result.operation_id == "seed_sector") != (result.prior_ejercicio is not None):
        raise ValueError("prorrata sector prior year differs from its operation")


@dataclass(frozen=True, slots=True)
class ProrrataOperationContract:
    """Closed request, result, mutation, and refusal schema for one operation."""

    operation_id: operation_requests.ProrrataOperationId
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    mutation: bool
    refusal_codes: frozenset[str]


_MUTATION_REFUSALS = frozenset({PRORRATA_VALIDATION_REFUSAL_CODE})
_ELECTION_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_ELECTION_REFUSAL_CODE}
_SEED_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_WHOLE_SEED_REFUSAL_CODE}
_SECTOR_LIFECYCLE_REFUSALS = _MUTATION_REFUSALS | {PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE}
_SHAPES: dict[str, ProrrataOperationContract] = {
    operation_requests.PRORRATA_LIST_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="list",
        request_type=operation_requests.ProrrataListRequest,
        projection_type=ProrrataListProjection,
        mutation=False,
        refusal_codes=frozenset(),
    ),
    operation_requests.PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="declare_sector",
        request_type=operation_requests.ProrrataDeclareSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_MUTATION_REFUSALS,
    ),
    operation_requests.PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="elect_especial",
        request_type=operation_requests.ProrrataElectEspecialRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    operation_requests.PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="elect_general",
        request_type=operation_requests.ProrrataElectGeneralRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    operation_requests.PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="revoke_especial",
        request_type=operation_requests.ProrrataRevokeEspecialRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    operation_requests.PRORRATA_SEED_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="seed",
        request_type=operation_requests.ProrrataSeedRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SEED_REFUSALS,
    ),
    operation_requests.PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="seed_sector",
        request_type=operation_requests.ProrrataSeedSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
    ),
    operation_requests.PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="settle_sector",
        request_type=operation_requests.ProrrataSettleSectorRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
    ),
    operation_requests.PRORRATA_DECLARE_GROSS_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="declare_gross",
        request_type=operation_requests.ProrrataDeclareGrossRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_MUTATION_REFUSALS,
    ),
    operation_requests.PRORRATA_REMOVE_GROSS_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="remove_gross",
        request_type=operation_requests.ProrrataRemoveGrossRequest,
        projection_type=ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_MUTATION_REFUSALS,
    ),
}


def prorrata_operation_contract(definition_id: str) -> ProrrataOperationContract | None:
    """Return the canonical closed contract for one registered operation."""
    return _SHAPES.get(definition_id)


__all__ = [
    "ProrrataOperationContract",
    "ProrrataOperationExecutionResult",
    "prorrata_operation_contract",
]
