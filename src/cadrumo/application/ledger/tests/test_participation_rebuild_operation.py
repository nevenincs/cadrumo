"""The registered rebuild refuses a misbound replacement target before reading."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.participation_index import TransactionRevisionParticipationIndex
from ....domain.modelos.protocols import (
    CalculationRevisionCatalogueRepositoryProtocol,
    ModeloRecordCatalogueRepositoryProtocol,
)
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ...modelo.participation_index_rebuild_ports import (
    ParticipationIndexRebuildPorts,
    ParticipationRebuildSourceRevisions,
)
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
)
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..participation_rebuild_operation import (
    LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
    LedgerParticipationRebuildExecutor,
    LedgerParticipationRebuildRequest,
    build_ledger_participation_rebuild_definition,
    build_ledger_participation_rebuild_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER_PROFILE = UUID("6bb00000-0000-4000-8000-0000000000bb")


class _PoisonSourceRepositories:
    """Count and refuse reads, which must not begin for a misbound target."""

    def __init__(self, bucket_id: str) -> None:
        self.bucket_id = bucket_id
        self.read_count = 0

    def load(self, *args: object, **kwargs: object) -> BaseModel:
        self.read_count += 1
        raise AssertionError("a source catalogue was read before rejecting the target bucket")


class _MisboundIndexRepository:
    """Expose a foreign target and fail if replacement reaches the repository."""

    def __init__(self) -> None:
        self.bucket_id = str(_OTHER_PROFILE)
        self.replace_count = 0

    def replace_all(
        self,
        indexes: Iterable[TransactionRevisionParticipationIndex],
        *,
        source_revisions: ParticipationRebuildSourceRevisions,
    ) -> int:
        del indexes, source_revisions
        self.replace_count += 1
        raise AssertionError("replace_all ran against a foreign profile bucket")


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase_code: str) -> None:
        self.phases.append(phase_code)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Cancellation:
    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield


class _Operands:
    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        del value, written_at
        raise AssertionError("a refused rebuild cannot publish a result")


class _Context:
    def __init__(self, operation: PinnedAuthorityOperation, events: _Events) -> None:
        self.identity = OperationIdentity(
            operation_id=uuid4().hex * 2,
            definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(_PROFILE)),
        )
        self.authority_operation = operation
        self.events = events
        self.cancellation = _Cancellation()
        self.operands = _Operands()


def _unexpected_ports(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ParticipationIndexRebuildPorts:
    """Keep policy resolution independent from the encrypted repositories."""
    raise AssertionError(f"access resolution composed rebuild repositories for {bucket_id}")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    """Build the registered operation contract without composing worker ports."""
    definition = build_ledger_participation_rebuild_definition(_unexpected_ports)
    registration = build_ledger_participation_rebuild_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _access_request(
    *,
    payload_profile: UUID = _PROFILE,
    subject_profile: UUID | None = None,
) -> OperationRequest[BaseModel]:
    """Build a request with independent target and subject coordinates."""
    subject_id = payload_profile if subject_profile is None else subject_profile
    return OperationRequest[BaseModel](
        definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(subject_id)),
        payload=LedgerParticipationRebuildRequest(profile_id=payload_profile),
    )


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    action: AccessAction,
    profile_id: UUID = _PROFILE,
) -> OperationAccessContext:
    """Build trusted host facts for one registered access action."""
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=UUID("7cc00000-0000-4000-8000-0000000000cc"),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


@pytest.mark.parametrize(
    ("action", "expected_category"),
    [
        (AccessAction.OBSERVE, DisclosureCategory.OPERATION_METADATA),
        (AccessAction.RESULT, DisclosureCategory.TAX_VALUES),
        (AccessAction.CANCEL, DisclosureCategory.OPERATION_METADATA),
        (AccessAction.DETACH, DisclosureCategory.OPERATION_METADATA),
        (AccessAction.COMMIT, None),
    ],
)
def test_rebuild_access_preserves_full_profile_commit_and_typed_disclosures(
    action: AccessAction,
    expected_category: DisclosureCategory | None,
) -> None:
    registry, registration = _registry()
    request = _access_request()
    context = _access_context(registration, action=action)

    resolved = resolve_operation_access(registry=registry, request=request, context=context)

    assert resolved.request.profile_id == _PROFILE
    assert resolved.request.periods == frozenset()
    assert resolved.request.period_independent is True
    assert resolved.policy.requires_all_periods is True
    assert resolved.policy.allow_period_independent is True
    assert resolved.policy.actions == frozenset(
        {
            AccessAction.SUBMIT,
            AccessAction.START,
            AccessAction.RESUME,
            AccessAction.OBSERVE,
            AccessAction.RESULT,
            AccessAction.CANCEL,
            AccessAction.DETACH,
            AccessAction.COMMIT,
        }
    )
    if expected_category is None:
        assert resolved.policy.disclosures == frozenset()
    else:
        if action is AccessAction.RESULT:
            assert registration.contract.result_schema is not None
            projection_id = registration.contract.result_schema.schema_id
        else:
            projection_id = OPERATION_OBSERVATION_PROJECTION_ID
        expected = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=projection_id,
            category=expected_category,
        )
        assert resolved.policy.disclosures == frozenset({expected})
        assert all(type(disclosure) is DisclosurePermission for disclosure in resolved.policy.disclosures)
        with pytest.raises(TypeError):
            OperationAccessPolicy.model_validate(
                {
                    **resolved.policy.model_dump(),
                    "actions": resolved.policy.actions | {AccessAction.COMMIT},
                }
            )


@pytest.mark.parametrize(
    ("context_profile", "payload_profile", "subject_profile"),
    [
        (_OTHER_PROFILE, _PROFILE, _PROFILE),
        (_PROFILE, _OTHER_PROFILE, _OTHER_PROFILE),
        (_PROFILE, _PROFILE, _OTHER_PROFILE),
    ],
)
def test_rebuild_access_refuses_foreign_profile_or_subject(
    context_profile: UUID,
    payload_profile: UUID,
    subject_profile: UUID,
) -> None:
    registry, registration = _registry()
    request = _access_request(payload_profile=payload_profile, subject_profile=subject_profile)
    context = _access_context(registration, action=AccessAction.RESULT, profile_id=context_profile)

    with pytest.raises(ProfileAccessRefusedError) as error:
        resolve_operation_access(registry=registry, request=request, context=context)

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH


@pytest.mark.asyncio
async def test_rebuild_refuses_foreign_index_bucket_before_source_reads_or_replacement(
    operation: PinnedAuthorityOperation,
) -> None:
    """A misplaced target must not be mutated under the requested profile's COMMIT."""
    source = _PoisonSourceRepositories(str(_PROFILE))
    target = _MisboundIndexRepository()
    ports = ParticipationIndexRebuildPorts(
        calculation_repository=cast(CalculationRevisionCatalogueRepositoryProtocol, source),
        work_unit_repository=cast(WorkUnitCatalogueRepositoryProtocol, source),
        filing_repository=cast(ModeloRecordCatalogueRepositoryProtocol, source),
        participation_index_repository=target,
    )

    def ports_factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ParticipationIndexRebuildPorts:
        assert bucket_id == str(_PROFILE)
        return ports

    request = OperationRequest[LedgerParticipationRebuildRequest](
        definition_id=LEDGER_PARTICIPATION_REBUILD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerParticipationRebuildRequest(profile_id=_PROFILE),
    )
    events = _Events()
    context = _Context(operation, events)

    with pytest.raises(ProfileAccessRefusedError) as error:
        await LedgerParticipationRebuildExecutor(ports_factory).execute(
            request, cast(OperationExecutorContext, context)
        )

    assert error.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert source.read_count == 0
    assert target.replace_count == 0
    assert events.effects == [OperationEffect.UNKNOWN]
