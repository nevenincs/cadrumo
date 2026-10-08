"""Canonical private result and public projection schemas for prorrata operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, NonNegativeInt, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from . import operation_requests as _requests
from .projection_contracts import (
    PRORRATA_ELECTION_REFUSAL_CODE as _PRORRATA_ELECTION_REFUSAL_CODE,
)
from .projection_contracts import (
    PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE as _PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
)
from .projection_contracts import (
    PRORRATA_VALIDATION_REFUSAL_CODE as _PRORRATA_VALIDATION_REFUSAL_CODE,
)
from .projection_contracts import (
    PRORRATA_WHOLE_SEED_REFUSAL_CODE as _PRORRATA_WHOLE_SEED_REFUSAL_CODE,
)
from .projection_contracts import (
    ProrrataFindingProjection as _ProrrataFindingProjection,
)
from .projection_contracts import (
    ProrrataListProjection as _ProrrataListProjection,
)
from .projection_contracts import (
    ProrrataMutationProjection as _ProrrataMutationProjection,
)
from .projection_contracts import (
    ProrrataRefusalProjection as _ProrrataRefusalProjection,
)
from .projection_contracts import (
    ProrrataSeedSourceProjection as _ProrrataSeedSourceProjection,
)


class ProrrataOperationExecutionResult(BaseModel):
    """Private complete outcome retained under secure operation custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: _requests.ProrrataOperationId
    profile_id: UUID
    outcome: Literal["success", "refused"]
    register_snapshot: ProrrataRegister | None = None
    entry: ProrrataRegisterEntry | None = None
    sector_definition: SectorDefinition | None = None
    seed_source: _ProrrataSeedSourceProjection | None = None
    findings: tuple[_ProrrataFindingProjection, ...] = ()
    prior_ejercicio: int | None = None
    count: NonNegativeInt | None = None
    refusal: _ProrrataRefusalProjection | None = None

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
    if result.operation_id == "list":
        _validate_list_execution_result(result)
    elif result.operation_id == "declare_sector":
        _validate_sector_declaration_execution_result(result)
    else:
        _validate_entry_execution_result(result)


def _validate_list_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if any(value is not None for value in (result.entry, result.sector_definition, result.seed_source)):
        raise ValueError("prorrata list result contains mutation details")


def _validate_sector_declaration_execution_result(result: ProrrataOperationExecutionResult) -> None:
    if result.sector_definition is None or any(
        value is not None for value in (result.entry, result.seed_source, result.prior_ejercicio)
    ):
        raise ValueError("prorrata sector declaration result is incomplete")


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

    operation_id: _requests.ProrrataOperationId
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    mutation: bool
    refusal_codes: frozenset[str]


_MUTATION_REFUSALS = frozenset({_PRORRATA_VALIDATION_REFUSAL_CODE})
_ELECTION_REFUSALS = _MUTATION_REFUSALS | {_PRORRATA_ELECTION_REFUSAL_CODE}
_SEED_REFUSALS = _MUTATION_REFUSALS | {_PRORRATA_WHOLE_SEED_REFUSAL_CODE}
_SECTOR_LIFECYCLE_REFUSALS = _MUTATION_REFUSALS | {_PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE}
_SHAPES: dict[str, ProrrataOperationContract] = {
    _requests.PRORRATA_LIST_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="list",
        request_type=_requests.ProrrataListRequest,
        projection_type=_ProrrataListProjection,
        mutation=False,
        refusal_codes=frozenset(),
    ),
    _requests.PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="declare_sector",
        request_type=_requests.ProrrataDeclareSectorRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_MUTATION_REFUSALS,
    ),
    _requests.PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="elect_especial",
        request_type=_requests.ProrrataElectEspecialRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    _requests.PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="elect_general",
        request_type=_requests.ProrrataElectGeneralRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    _requests.PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="revoke_especial",
        request_type=_requests.ProrrataRevokeEspecialRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_ELECTION_REFUSALS,
    ),
    _requests.PRORRATA_SEED_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="seed",
        request_type=_requests.ProrrataSeedRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SEED_REFUSALS,
    ),
    _requests.PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="seed_sector",
        request_type=_requests.ProrrataSeedSectorRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
    ),
    _requests.PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID: ProrrataOperationContract(
        operation_id="settle_sector",
        request_type=_requests.ProrrataSettleSectorRequest,
        projection_type=_ProrrataMutationProjection,
        mutation=True,
        refusal_codes=_SECTOR_LIFECYCLE_REFUSALS,
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
