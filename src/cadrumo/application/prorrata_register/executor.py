"""Exact-profile registered operations for the IVA prorrata register."""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.prorrata_register.register import (
    ProrrataRegister,
    ProrrataRegisterValidationError,
)
from ..modelo.calculation_action_ports import CalculationActionPortsFactory
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from . import operation_requests as _requests
from . import result_contracts as _result_contracts
from .mutation_steps import (
    CommittedProrrataMutation as _CommittedProrrataMutation,
)
from .mutation_steps import (
    ProrrataPreflightRefusalError as ProrrataPreflightRefusalError,
)
from .mutation_steps import (
    ProrrataPreflightRefusalError as _ProrrataPreflightRefusalError,
)
from .mutation_steps import (
    build_prorrata_refusal_projection as _build_prorrata_refusal_projection,
)
from .mutation_steps import (
    build_prorrata_refusal_projection as build_prorrata_refusal_projection,
)
from .mutation_steps import (
    perform_prorrata_mutation as _perform_prorrata_mutation,
)
from .mutation_steps import (
    perform_prorrata_mutation as perform_prorrata_mutation,
)
from .mutation_steps import (
    preflight_prorrata_operation as _preflight_prorrata_operation,
)
from .mutation_steps import (
    preflight_prorrata_operation as preflight_prorrata_operation,
)
from .mutation_steps import (
    whole_seed_refusal_reason as _whole_seed_refusal_reason,
)
from .mutation_steps import (
    whole_seed_refusal_reason as whole_seed_refusal_reason,
)
from .ports import ProrrataRegisterRepositoryFactory
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
    ProrrataRefusalProjection as _ProrrataRefusalProjection,
)
from .projection_contracts import (
    ProrrataRefusalReason as _ProrrataRefusalReason,
)
from .projection_contracts import (
    ProrrataSeedSourceProjection as _ProrrataSeedSourceProjection,
)
from .sector_lifecycle import ProrrataSectorLifecycleUnavailableError
from .service import (
    ProrrataRegisterService,
    ProrrataWholeSeedUnavailableError,
)


class ProrrataOperationExecutor:
    """Run one canonical prorrata service call under exact-profile worker custody."""

    def __init__(
        self,
        repository_factory: ProrrataRegisterRepositoryFactory,
        *,
        definition_id: str,
        calculation_action_ports_factory: CalculationActionPortsFactory | None = None,
    ) -> None:
        """Bind canonical bucket repository factories for this operation."""
        self._repository_factory = repository_factory
        self._definition_id = definition_id
        self._calculation_action_ports_factory = calculation_action_ports_factory

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Execute one exact-profile request with a truthful terminal effect."""
        return await _execute_prorrata_operation(
            self._definition_id,
            self._repository_factory,
            self._calculation_action_ports_factory,
            request,
            context,
        )


async def _store_prorrata_refusal(
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: _requests.ProrrataOperationId,
    refusal: _ProrrataRefusalProjection,
) -> OperationRefusalEvidence:
    async with context.cancellation.irreversible_section():
        return await _persist_prorrata_refusal(
            context,
            profile_id=profile_id,
            operation_id=operation_id,
            refusal=refusal,
        )


async def _persist_prorrata_refusal(
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: _requests.ProrrataOperationId,
    refusal: _ProrrataRefusalProjection,
) -> OperationRefusalEvidence:
    result = _result_contracts.ProrrataOperationExecutionResult(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="refused",
        refusal=refusal,
    )
    detail_ref = await context.operands.put(result, written_at=now())
    await context.events.effect(OperationEffect.NONE)
    return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)


async def _execute_prorrata_operation(
    definition_id: str,
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    request: OperationRequest[BaseModel],
    context: OperationExecutorContext,
) -> str | OperationRefusalEvidence:
    shape, payload = _require_profile_operation_request(definition_id, request, context)
    await context.events.phase(definition_id)
    if definition_id == _requests.PRORRATA_LIST_OPERATION_DEFINITION_ID:
        return await _read_prorrata_list(repository_factory, payload, context)
    return await _execute_prorrata_mutation(
        repository_factory,
        calculation_action_ports_factory,
        shape.operation_id,
        payload,
        context,
    )


def _require_profile_operation_request(
    definition_id: str,
    request: OperationRequest[BaseModel],
    context: OperationExecutorContext,
) -> tuple[_result_contracts.ProrrataOperationContract, _requests.ProrrataProfileRequest]:
    shape = _result_contracts.prorrata_operation_contract(definition_id)
    if shape is None or type(request.payload) is not shape.request_type:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if not isinstance(payload, _requests.ProrrataProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile = str(payload.profile_id)
    if (
        request.definition_id != definition_id
        or request.subject_ref != profile_operation_subject(profile)
        or context.identity.definition_id != request.definition_id
        or context.identity.subject_ref != request.subject_ref
        or require_active_bucket_id() != profile
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return shape, payload


async def _read_prorrata_list(
    repository_factory: ProrrataRegisterRepositoryFactory,
    payload: _requests.ProrrataProfileRequest,
    context: OperationExecutorContext,
) -> str | OperationRefusalEvidence:
    async def read() -> str:
        register = await asyncio.to_thread(_load_prorrata_list, repository_factory, payload, context)
        result = _result_contracts.ProrrataOperationExecutionResult(
            operation_id="list",
            profile_id=payload.profile_id,
            outcome="success",
            register_snapshot=register,
            count=len(register.entries),
        )
        reference = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return reference

    return await await_cancellation_complete(read(), task_name="prorrata-list")


def _load_prorrata_list(
    repository_factory: ProrrataRegisterRepositoryFactory,
    payload: _requests.ProrrataProfileRequest,
    context: OperationExecutorContext,
) -> ProrrataRegister:
    with validating_governed_facts(context.authority_operation):
        return _prorrata_service(repository_factory, payload.profile_id, context.authority_operation).list_all()


def _prorrata_service(
    repository_factory: ProrrataRegisterRepositoryFactory,
    profile_id: UUID,
    authority: PinnedAuthorityOperation,
) -> ProrrataRegisterService:
    return ProrrataRegisterService(repository=repository_factory(bucket_id=str(profile_id)), operation=authority)


async def _execute_prorrata_mutation(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    context: OperationExecutorContext,
) -> str | OperationRefusalEvidence:
    try:
        with validating_governed_facts(context.authority_operation):
            prepared = _preflight_prorrata_operation(
                operation_id,
                payload,
                context,
                calculation_action_ports_factory,
            )
    except _ProrrataPreflightRefusalError as exc:
        return await _store_prorrata_refusal(
            context,
            profile_id=payload.profile_id,
            operation_id=operation_id,
            refusal=_preflight_refusal_projection(operation_id, payload, exc),
        )
    except (ProrrataRegisterValidationError, ValidationError) as exc:
        return await _store_prorrata_refusal(
            context,
            profile_id=payload.profile_id,
            operation_id=operation_id,
            refusal=_validation_refusal_projection(payload, str(exc)),
        )
    return await _commit_prorrata_mutation(
        repository_factory,
        calculation_action_ports_factory,
        operation_id,
        payload,
        prepared,
        context,
    )


def _preflight_refusal_projection(
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    error: _ProrrataPreflightRefusalError,
) -> _ProrrataRefusalProjection:
    election_refusal = operation_id in {"elect_especial", "elect_general", "revoke_especial"} and error.reason in {
        "provenance_not_electable",
        "reference_required",
        "reference_not_permitted",
    }
    code = _PRORRATA_ELECTION_REFUSAL_CODE if election_refusal else _PRORRATA_VALIDATION_REFUSAL_CODE
    return _build_prorrata_refusal_projection(
        reason=error.reason,
        detail=error.detail,
        ejercicio=getattr(payload, "ejercicio", None),
        sector_id=getattr(payload, "sector_id", None),
        code=code,
        accepted_provenances=error.accepted_provenances,
    )


def _validation_refusal_projection(
    payload: _requests.ProrrataProfileRequest,
    detail: str,
) -> _ProrrataRefusalProjection:
    return _build_prorrata_refusal_projection(
        reason="validation",
        detail=detail,
        ejercicio=getattr(payload, "ejercicio", None),
        sector_id=getattr(payload, "sector_id", None),
    )


async def _commit_prorrata_mutation(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    prepared: object,
    context: OperationExecutorContext,
) -> str | OperationRefusalEvidence:
    async def commit() -> str | OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            try:
                committed = await asyncio.to_thread(
                    _perform_committed_mutation,
                    repository_factory,
                    calculation_action_ports_factory,
                    operation_id,
                    payload,
                    prepared,
                    context,
                )
            except (
                ProrrataWholeSeedUnavailableError,
                ProrrataSectorLifecycleUnavailableError,
                ProrrataRegisterValidationError,
            ) as exc:
                return await _persist_prorrata_refusal(
                    context,
                    profile_id=payload.profile_id,
                    operation_id=operation_id,
                    refusal=_committed_mutation_refusal_projection(operation_id, payload, exc),
                )
            return await _persist_prorrata_mutation_success(operation_id, payload.profile_id, committed, context)

    return await await_cancellation_complete(commit(), task_name=f"prorrata-{operation_id}")


def _perform_committed_mutation(
    repository_factory: ProrrataRegisterRepositoryFactory,
    calculation_action_ports_factory: CalculationActionPortsFactory | None,
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    prepared: object,
    context: OperationExecutorContext,
) -> _CommittedProrrataMutation:
    with validating_governed_facts(context.authority_operation):
        service = _prorrata_service(repository_factory, payload.profile_id, context.authority_operation)
        return _perform_prorrata_mutation(
            operation_id,
            payload,
            prepared,
            service,
            context,
            calculation_action_ports_factory,
        )


def _committed_mutation_refusal_projection(
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    error: Exception,
) -> _ProrrataRefusalProjection:
    if isinstance(error, ProrrataWholeSeedUnavailableError):
        return _whole_seed_refusal_projection(payload, error)
    if isinstance(error, ProrrataSectorLifecycleUnavailableError):
        return _sector_lifecycle_refusal_projection(operation_id, payload, error)
    # Repository singleton validation runs while rebuilding the latest candidate,
    # before its revision-guarded write.
    return _validation_refusal_projection(payload, str(error))


def _whole_seed_refusal_projection(
    payload: _requests.ProrrataProfileRequest,
    error: ProrrataWholeSeedUnavailableError,
) -> _ProrrataRefusalProjection:
    return _build_prorrata_refusal_projection(
        reason=_whole_seed_refusal_reason(error.reason),
        detail=str(error),
        ejercicio=getattr(payload, "ejercicio", None),
        sector_id=getattr(payload, "sector_id", None),
        findings=error.findings,
        existing_provenance=(error.existing_provenance.value if error.existing_provenance is not None else None),
        code=_PRORRATA_WHOLE_SEED_REFUSAL_CODE,
    )


def _sector_lifecycle_refusal_projection(
    operation_id: _requests.ProrrataOperationId,
    payload: _requests.ProrrataProfileRequest,
    error: ProrrataSectorLifecycleUnavailableError,
) -> _ProrrataRefusalProjection:
    reason: _ProrrataRefusalReason = (
        "sector_prior_definitive_absent" if operation_id == "seed_sector" else "sector_settlement_entry_absent"
    )
    return _build_prorrata_refusal_projection(
        reason=reason,
        detail=str(error),
        ejercicio=getattr(payload, "ejercicio", None),
        sector_id=getattr(payload, "sector_id", None),
        code=_PRORRATA_SECTOR_LIFECYCLE_REFUSAL_CODE,
    )


async def _persist_prorrata_mutation_success(
    operation_id: _requests.ProrrataOperationId,
    profile_id: UUID,
    committed: _CommittedProrrataMutation,
    context: OperationExecutorContext,
) -> str:
    result = _result_contracts.ProrrataOperationExecutionResult(
        operation_id=operation_id,
        profile_id=profile_id,
        outcome="success",
        register_snapshot=committed.register,
        entry=committed.entry,
        sector_definition=committed.sector_definition,
        seed_source=(_ProrrataSeedSourceProjection.from_seed(committed.seed) if committed.seed is not None else None),
        findings=tuple(_ProrrataFindingProjection.from_finding(item) for item in committed.findings),
        prior_ejercicio=committed.prior_ejercicio,
        count=(
            len(committed.register.sector_definitions)
            if operation_id == "declare_sector"
            else len(committed.register.entries)
        ),
    )
    reference = await context.operands.put(result, written_at=now())
    await context.events.effect(OperationEffect.UPDATED)
    return reference
