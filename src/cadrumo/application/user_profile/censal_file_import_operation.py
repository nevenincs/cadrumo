"""Guarded enrollment of validated facts from a censal certificate file."""

from __future__ import annotations

import asyncio
import re
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.user_profile.values import UserProfileFact
from ..operations.access_resolution import (
    COMMITTING_OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
)
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from .access_contracts import AccessDenialCode, Availability
from .access_errors import ProfileAccessRefusedError
from .censal_access import bind_whole_profile_censal_access
from .cotejo_apply import apply_cotejo

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext

CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID = "user-profile.censo-file-import"
CENSAL_FILE_IMPORT_PHASE_APPLY = "user-profile.censo-file-import.apply"
CENSAL_FILE_IMPORT_PHASE_RESULT = "user-profile.censo-file-import.result"

_FILE_FACT_PATH_PATTERN = r"^(?:contact\.fiscal_address|activities(?:\.[1-9][0-9]*)?\.(?:description|iae_epigraph))$"
_CensalFileFactPath = Annotated[
    str,
    Field(min_length=3, max_length=160, pattern=_FILE_FACT_PATH_PATTERN),
]
_FILE_FACT_PATH_RE = re.compile(_FILE_FACT_PATH_PATTERN)
_ACTIVITY_FIELD_ORDERS = {"description": 0, "iae_epigraph": 1}


def _require_censal_file_fact(fact: CensalFileImportFact) -> None:
    if (
        _FILE_FACT_PATH_RE.fullmatch(fact.path) is None
        or fact.source is not CensalFileImportProvenance.ARTEFACT
        or not fact.value.strip()
    ):
        raise ValueError("censal file import facts must match the certified artefact contract")


def _activity_fact_order(path: str) -> tuple[int, int, str]:
    _, _, suffix = path.partition("activities.")
    row_token, _, suffix = suffix.partition(".")
    field_order = _ACTIVITY_FIELD_ORDERS.get(row_token)
    if field_order is not None:
        return 0, field_order, row_token
    row_index = int(row_token)
    return row_index, _ACTIVITY_FIELD_ORDERS.get(suffix, 1), suffix


def _require_complete_censal_facts(facts: tuple[CensalFileImportFact, ...]) -> tuple[str, ...]:
    if not facts:
        raise ValueError("censal file import requires at least one validated fact")
    paths = tuple(fact.path for fact in facts)
    if len(paths) != len(set(paths)):
        raise ValueError("censal file import facts must have unique paths")
    if paths.count("contact.fiscal_address") != 1:
        raise ValueError("censal file import must include its certified fiscal address")
    return paths


def _require_complete_activity_rows(activity_rows: dict[int, set[str]]) -> None:
    if any("description" not in row_paths for row_paths in activity_rows.values()):
        raise ValueError("each certified activity row must include its description")
    if activity_rows and set(activity_rows) != set(range(max(activity_rows) + 1)):
        raise ValueError("certified activity row indexes must be contiguous")


class CensalFileImportProvenance(StrEnum):
    """Only provenance tier a taxpayer-supplied file may claim."""

    ARTEFACT = PROVENANCE_SOURCE_CENSO_ARTEFACT


class CensalFileImportFact(BaseModel):
    """One certificate-derived profile fact in the secure operation input."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    path: _CensalFileFactPath
    value: str = Field(min_length=1)
    source: CensalFileImportProvenance


class CensalFileImportOperationRequest(BaseModel):
    """Secure input for one exact-profile certificate-fact enrollment."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_version: Literal[1] = 1
    profile_id: UUID
    facts: tuple[CensalFileImportFact, ...]

    @model_validator(mode="after")
    def _validate_file_facts(self) -> CensalFileImportOperationRequest:
        """Admit only the non-official fact shape the certificate adapter emits."""
        _require_complete_censal_facts(self.facts)
        activity_rows: dict[int, set[str]] = {}
        ordered_path_keys: list[tuple[int, int]] = []
        for fact in self.facts:
            _require_censal_file_fact(fact)
            if fact.path == "contact.fiscal_address":
                ordered_path_keys.append((-1, -1))
                continue
            row_index, field_order, suffix = _activity_fact_order(fact.path)
            row_paths = activity_rows.setdefault(row_index, set())
            row_paths.add(suffix)
            ordered_path_keys.append((row_index, field_order))

        if ordered_path_keys != sorted(ordered_path_keys):
            raise ValueError("censal file import facts must use canonical certificate order")
        _require_complete_activity_rows(activity_rows)
        return self


class CensalFileImportOperationResult(BaseModel):
    """Safe receipt naming the exact paths successfully enrolled."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    response_version: Literal[1] = 1
    profile_id: UUID
    applied: Literal[True] = True
    fact_paths: tuple[_CensalFileFactPath, ...]

    @model_validator(mode="after")
    def _validate_result_paths(self) -> CensalFileImportOperationResult:
        if not self.fact_paths or len(self.fact_paths) != len(set(self.fact_paths)):
            raise ValueError("censal file import result must identify unique applied facts")
        if self.fact_paths.count("contact.fiscal_address") != 1:
            raise ValueError("censal file import result must retain its certified fiscal address")
        return self


def _apply_censal_file_facts(
    *,
    profile_id: str,
    facts: tuple[CensalFileImportFact, ...],
    profile_decode_context: ProfileDecodeContext,
) -> CensalFileImportOperationResult:
    """Apply the complete file fact set through the one cotejo authority."""
    from ..workflow.persistence import workflow_state_repository

    if require_active_bucket_id() != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    repository = workflow_state_repository()
    state = repository.load()
    if state.active_profile_bucket_id() != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    domain_facts = tuple(UserProfileFact(path=fact.path, value=fact.value, source=fact.source) for fact in facts)
    updated_state = apply_cotejo(
        state,
        adopted=domain_facts,
        divergences=(),
        profile_decode_context=profile_decode_context,
    )
    repository.save(updated_state)
    return CensalFileImportOperationResult(
        profile_id=UUID(profile_id),
        fact_paths=tuple(fact.path for fact in facts),
    )


class CensalFileImportOperationExecutor:
    """Commit one exact-profile artefact enrollment under fresh COMMIT authority."""

    async def execute(
        self,
        request: OperationRequest[CensalFileImportOperationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Apply the validated facts and publish their non-sensitive receipt."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(CENSAL_FILE_IMPORT_PHASE_APPLY)
        profile_decode_context = context.authority_operation.profile_decode_context()

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(
                    _apply_censal_file_facts,
                    profile_id=profile_id,
                    facts=payload.facts,
                    profile_decode_context=profile_decode_context,
                )
                await context.events.effect(OperationEffect.UPDATED)
                await context.events.phase(CENSAL_FILE_IMPORT_PHASE_RESULT)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="censal-file-import-operation")


def resolve_censal_file_import_operation_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Resolve one whole-profile import with an explicit local COMMIT action."""
    _validated_censal_import_request(request, context)
    return bind_whole_profile_censal_access(
        request, context, actions=COMMITTING_OPERATION_LIFECYCLE_ACTIONS, provider=Availability.NOT_REQUIRED
    )


def _validated_censal_import_request(
    request: OperationRequest[BaseModel], context: OperationAccessContext
) -> CensalFileImportOperationRequest:
    payload = request.payload
    if request.definition_id != CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID or not isinstance(
        payload, CensalFileImportOperationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    profile_id = str(payload.profile_id)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def build_censal_file_import_operation_definition() -> OperationDefinition:
    """Declare a secure-input, exact-profile local mutation operation."""
    return OperationDefinition(
        definition_id=CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID,
        request_type=CensalFileImportOperationRequest,
        result_type=CensalFileImportOperationResult,
        executor_factory=OperationExecutorFactory(
            request_type=CensalFileImportOperationRequest,
            executor_type=CensalFileImportOperationExecutor,
            build=CensalFileImportOperationExecutor,
        ),
        phase_codes=(CENSAL_FILE_IMPORT_PHASE_APPLY, CENSAL_FILE_IMPORT_PHASE_RESULT),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def build_censal_file_import_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the validated file facts and safe exact-profile receipt schemas."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=CensalFileImportOperationResult,
        access_resolver=resolve_censal_file_import_operation_access,
    )


__all__ = [
    "CENSAL_FILE_IMPORT_OPERATION_DEFINITION_ID",
    "CensalFileImportFact",
    "CensalFileImportOperationExecutor",
    "CensalFileImportOperationRequest",
    "CensalFileImportOperationResult",
    "CensalFileImportProvenance",
    "build_censal_file_import_operation_definition",
    "build_censal_file_import_operation_registration",
    "resolve_censal_file_import_operation_access",
]
