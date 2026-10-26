"""Project secured prorrata operation results against their terminal receipts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.prorrata_register.register import ProrrataRegister
from ..operations.models import OperationTerminalReceipt
from . import operation_requests as _requests
from . import result_contracts as _contracts
from .projection_contracts import (
    ProrrataEntryProjection as _ProrrataEntryProjection,
)
from .projection_contracts import (
    ProrrataListProjection as _ProrrataListProjection,
)
from .projection_contracts import (
    ProrrataMutationProjection as _ProrrataMutationProjection,
)
from .projection_contracts import (
    ProrrataSectorDefinitionProjection as _ProrrataSectorDefinitionProjection,
)


def _copy_private_result(result: BaseModel) -> _contracts.ProrrataOperationExecutionResult:
    if type(result) is not _contracts.ProrrataOperationExecutionResult:
        raise ValueError("prorrata execution result has an incompatible type")
    return _contracts.ProrrataOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def _profile_id_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("prorrata result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("prorrata result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("prorrata result has an invalid profile subject")
    return profile_id


def _receipt_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    outcome: Literal["success", "refused"],
    operation_id: _requests.ProrrataOperationId,
    refusal_code: str | None = None,
) -> None:
    refused = outcome == "refused"
    expected_effect = OperationEffect.NONE if refused or operation_id == "list" else OperationEffect.UPDATED
    expected_condition = OperationTerminalCondition.REFUSED if refused else OperationTerminalCondition.SUCCEEDED
    expected_refusal = refusal_code if refused else None
    if not _receipt_identity_matches(receipt, definition_id=definition_id, profile_id=profile_id):
        raise ValueError("prorrata projection differs from its terminal receipt")
    if not _receipt_outcome_matches(
        receipt,
        expected_condition=expected_condition,
        expected_effect=expected_effect,
        expected_refusal=expected_refusal,
        refused=refused,
    ):
        raise ValueError("prorrata projection differs from its terminal receipt")


def _receipt_identity_matches(
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
) -> bool:
    return (
        receipt.identity.definition_id == definition_id
        and receipt.identity.subject_ref == profile_operation_subject(str(profile_id))
    )


def _receipt_outcome_matches(
    receipt: OperationTerminalReceipt,
    *,
    expected_condition: OperationTerminalCondition,
    expected_effect: OperationEffect,
    expected_refusal: str | None,
    refused: bool,
) -> bool:
    return (
        receipt.condition is expected_condition
        and receipt.effect is expected_effect
        and receipt.refusal_ref == expected_refusal
        and (receipt.refusal_detail_ref is not None) == refused
        and (receipt.result_ref is not None) != refused
        and receipt.failure_error_code is None
        and receipt.diagnostic_ref is None
    )


def _require_list_result(
    private: _contracts.ProrrataOperationExecutionResult,
    *,
    profile_id: UUID,
) -> None:
    if not _list_result_identity_matches(private, profile_id) or not _list_result_payload_is_closed(private):
        raise ValueError("prorrata list result has an incompatible payload")


def _list_result_identity_matches(
    private: _contracts.ProrrataOperationExecutionResult,
    profile_id: UUID,
) -> bool:
    return private.operation_id == "list" and private.profile_id == profile_id and private.outcome == "success"


def _list_result_payload_is_closed(private: _contracts.ProrrataOperationExecutionResult) -> bool:
    register = private.register_snapshot
    return (
        register is not None
        and private.count == len(register.entries)
        and private.entry is None
        and private.sector_definition is None
        and private.seed_source is None
        and not private.findings
        and private.refusal is None
    )


def project_prorrata_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> _ProrrataListProjection:
    """Project every persisted entry and sector from an exact-profile list result."""
    private = _copy_private_result(result)
    profile_id = _profile_id_from_receipt(receipt, definition_id=_requests.PRORRATA_LIST_OPERATION_DEFINITION_ID)
    _require_list_result(private, profile_id=profile_id)
    _receipt_matches(
        receipt,
        definition_id=_requests.PRORRATA_LIST_OPERATION_DEFINITION_ID,
        profile_id=profile_id,
        outcome="success",
        operation_id="list",
    )
    register = private.register_snapshot
    if register is None:
        raise ValueError("prorrata list result has an incompatible payload")
    return _ProrrataListProjection(
        profile_id=profile_id,
        entries=tuple(_ProrrataEntryProjection.from_entry(entry) for entry in register.entries),
        sectors=tuple(
            _ProrrataSectorDefinitionProjection.from_definition(sector) for sector in register.sector_definitions
        ),
        count=len(register.entries),
    )


def _mutation_identity(
    private: _contracts.ProrrataOperationExecutionResult,
    receipt: OperationTerminalReceipt,
) -> tuple[str, UUID, _requests.ProrrataOperationId]:
    definition_id = receipt.identity.definition_id
    contract = _contracts.prorrata_operation_contract(definition_id)
    if contract is None or contract.operation_id == "list":
        raise ValueError("prorrata mutation result has an unknown operation definition")
    operation_id = contract.operation_id
    profile_id = _profile_id_from_receipt(receipt, definition_id=definition_id)
    if private.operation_id != operation_id or private.profile_id != profile_id:
        raise ValueError("prorrata mutation result crossed its profile or operation identity")
    return definition_id, profile_id, operation_id


def _refused_mutation_projection(
    private: _contracts.ProrrataOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    operation_id: _requests.ProrrataOperationId,
) -> _ProrrataMutationProjection:
    refusal = private.refusal
    contract = _contracts.prorrata_operation_contract(definition_id)
    if contract is None or refusal is None or refusal.code not in contract.refusal_codes:
        raise ValueError("prorrata refusal result has an unregistered code")
    _receipt_matches(
        receipt,
        definition_id=definition_id,
        profile_id=profile_id,
        outcome="refused",
        operation_id=operation_id,
        refusal_code=refusal.code,
    )
    return _ProrrataMutationProjection(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="refused",
        refusal=refusal,
    )


def _require_success_mutation_result(
    private: _contracts.ProrrataOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    *,
    definition_id: str,
    profile_id: UUID,
    operation_id: _requests.ProrrataOperationId,
) -> tuple[ProrrataRegister, int]:
    _receipt_matches(
        receipt,
        definition_id=definition_id,
        profile_id=profile_id,
        outcome=private.outcome,
        operation_id=operation_id,
    )
    if private.register_snapshot is None or private.count is None:
        raise ValueError("prorrata success result omitted its committed register")
    return private.register_snapshot, private.count


def _project_sector_declaration_result(
    private: _contracts.ProrrataOperationExecutionResult,
    *,
    profile_id: UUID,
    register: ProrrataRegister,
    count: int,
) -> _ProrrataMutationProjection:
    sector = private.sector_definition
    if (
        sector is None
        or private.entry is not None
        or count != len(register.sector_definitions)
        or not any(row == sector for row in register.sector_definitions)
    ):
        raise ValueError("prorrata sector result contradicts the committed register")
    return _ProrrataMutationProjection(
        operation_id="declare_sector",
        profile_id=profile_id,
        outcome="success",
        sector_definition=_ProrrataSectorDefinitionProjection.from_definition(sector),
        count=count,
    )


def _project_entry_mutation_result(
    private: _contracts.ProrrataOperationExecutionResult,
    *,
    profile_id: UUID,
    operation_id: _requests.ProrrataOperationId,
    register: ProrrataRegister,
    count: int,
) -> _ProrrataMutationProjection:
    entry = private.entry
    if (
        entry is None
        or count != len(register.entries)
        or not any(row == entry for row in register.entries)
        or private.sector_definition is not None
    ):
        raise ValueError("prorrata entry result contradicts the committed register")
    if operation_id == "seed" and private.seed_source is None:
        raise ValueError("whole-entity prorrata seed omitted source identity")
    if operation_id != "seed" and private.seed_source is not None:
        raise ValueError("non-seed prorrata result contains source identity")
    return _ProrrataMutationProjection(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="success",
        entry=_ProrrataEntryProjection.from_entry(entry),
        seed_source=private.seed_source,
        findings=private.findings,
        prior_ejercicio=private.prior_ejercicio,
        count=count,
    )


def project_prorrata_mutation_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> _ProrrataMutationProjection:
    """Project one complete mutation result or its accurate NONE-effect refusal."""
    private = _copy_private_result(result)
    definition_id, profile_id, operation_id = _mutation_identity(private, receipt)
    if private.outcome == "refused":
        return _refused_mutation_projection(
            private,
            receipt,
            definition_id=definition_id,
            profile_id=profile_id,
            operation_id=operation_id,
        )
    register, count = _require_success_mutation_result(
        private,
        receipt,
        definition_id=definition_id,
        profile_id=profile_id,
        operation_id=operation_id,
    )
    if operation_id == "declare_sector":
        return _project_sector_declaration_result(
            private,
            profile_id=profile_id,
            register=register,
            count=count,
        )
    return _project_entry_mutation_result(
        private,
        profile_id=profile_id,
        operation_id=operation_id,
        register=register,
        count=count,
    )


__all__ = ["project_prorrata_list_result", "project_prorrata_mutation_result"]
