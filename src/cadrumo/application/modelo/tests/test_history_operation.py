"""Registered history keeps exact profile, persisted period, and event identity."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.period import Period
from ....domain.buckets.event import (
    BucketEvent,
    BucketEventObjectType,
    BucketEventType,
    derive_bucket_event_id,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState, derive_work_unit_id
from ...bucket_event_projection import BucketEventProjection
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationRequest
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..history import WorkUnitHistory
from ..history_operation import (
    MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
    ModeloWorkHistoryProjection,
    ModeloWorkHistoryRequest,
    ModeloWorkHistorySnapshot,
    build_modelo_work_history_definition,
    build_modelo_work_history_registration,
)
from ..history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_NOW = datetime(2026, 3, 10, 12, tzinfo=UTC)


def _unit() -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=period, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=period,
        revision_id="2026-y-siguientes",
        name="First quarter",
        created_at=_NOW,
        updated_at=_NOW,
        state=WorkUnitState.BORRADOR,
    )


class _WorkRepository:
    def __init__(self, unit: WorkUnit, *, bucket_id: str = str(_PROFILE)) -> None:
        self.bucket_id = bucket_id
        self.unit = unit
        self.loads = 0

    def load(self) -> WorkUnitCatalogue:
        self.loads += 1
        return WorkUnitCatalogue(work_units={self.unit.work_unit_id: self.unit})


def _registration(repository: _WorkRepository, operation: PinnedAuthorityOperation, *, wrong: str | None = None):
    calls: list[str] = []

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloHistoryPorts:
        assert operation is pinned
        calls.append(bucket_id)

        def peer(name: str) -> SimpleNamespace:
            return SimpleNamespace(bucket_id=str(_OTHER) if wrong == name else str(_PROFILE))

        return cast(
            ModeloHistoryPorts,
            cast(
                object,
                SimpleNamespace(
                    work_unit_repository=repository,
                    calculation_repository=peer("calculation"),
                    verification_repository=peer("verification"),
                    filing_repository=peer("filing"),
                    bucket_event_repository=SimpleNamespace(),
                ),
            ),
        )

    pinned = operation
    typed_factory = cast(ModeloHistoryPortsFactory, factory)
    definition = build_modelo_work_history_definition(typed_factory)
    registration = build_modelo_work_history_registration(definition, typed_factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    return registry, registration, calls


def _request(
    unit: WorkUnit, *, profile_id: UUID = _PROFILE, subject_ref: str | None = None
) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref or unit.work_unit_id,
        payload=ModeloWorkHistoryRequest(profile_id=profile_id, work_unit_id=unit.work_unit_id),
    )


def _context(
    registration,
    operation: PinnedAuthorityOperation | None,
    *,
    profile_id: UUID = _PROFILE,
    action: AccessAction = AccessAction.SUBMIT,
    admitted: OperationAccessRequest | None = None,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=profile_id,
        destination_id=uuid4(),
        action=action,
        frontend=OperationFrontendProjection.CLI,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
        admitted_request=admitted,
        authority_operation=operation,
    )


def _event(*, bucket_id: UUID = _PROFILE, occurred_at: datetime = _NOW, object_id: str = "unit") -> BucketEvent:
    event_type = BucketEventType.MODELO_WORK_UNIT_CREATED
    object_type = BucketEventObjectType.WORK_UNIT
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=str(bucket_id),
            event_type=event_type,
            occurred_at=occurred_at,
            actor="operator",
            object_type=object_type,
            object_id=object_id,
            payload={},
        ),
        bucket_id=str(bucket_id),
        event_type=event_type,
        occurred_at=occurred_at,
        actor="operator",
        object_type=object_type,
        object_id=object_id,
        payload_version=1,
        payload={},
    )


def test_projection_preserves_canonical_event_and_rejects_foreign_duplicate_unordered() -> None:
    first = _event()
    later = _event(occurred_at=datetime(2026, 3, 10, 13, tzinfo=UTC))
    history = WorkUnitHistory(bucket_id=str(_PROFILE), work_unit_id=_unit().work_unit_id, events=(first, later))
    projection = ModeloWorkHistoryProjection(
        profile_id=_PROFILE, history=ModeloWorkHistorySnapshot.from_history(history)
    )
    assert ModeloWorkHistoryProjection.model_validate_json(projection.model_dump_json()) == projection
    assert projection.history.to_history() == history
    assert tuple(event.event_id for event in projection.history.events) == (first.event_id, later.event_id)
    for events in ((_event(bucket_id=_OTHER),), (first, first), (later, first)):
        with pytest.raises(ValidationError):
            ModeloWorkHistoryProjection(
                profile_id=_PROFILE,
                history=ModeloWorkHistorySnapshot(
                    bucket_id=str(_PROFILE),
                    work_unit_id=history.work_unit_id,
                    events=tuple(BucketEventProjection.from_event(event) for event in events),
                ),
            )
    with pytest.raises(ValidationError):
        ModeloWorkHistoryProjection(profile_id=_OTHER, history=ModeloWorkHistorySnapshot.from_history(history))


def test_profile_and_subject_refused_before_repositories(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration, calls = _registration(repository, authority_operation)
    for request, profile_id in (
        (_request(unit, profile_id=_OTHER), _PROFILE),
        (_request(unit), _OTHER),
        (_request(unit, subject_ref="different-subject"), _PROFILE),
    ):
        with pytest.raises(ProfileAccessRefusedError) as refused:
            resolve_operation_access(
                registry=registry,
                request=request,
                context=_context(registration, authority_operation, profile_id=profile_id),
            )
        assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert calls == [] and repository.loads == 0


@pytest.mark.parametrize("wrong", ["work", "calculation", "verification", "filing"])
def test_every_repository_must_match_exact_profile(authority_operation: PinnedAuthorityOperation, wrong: str) -> None:
    unit = _unit()
    repository = _WorkRepository(unit, bucket_id=str(_OTHER) if wrong == "work" else str(_PROFILE))
    registry, registration, _ = _registration(repository, authority_operation, wrong=wrong)
    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry,
            request=_request(unit),
            context=_context(registration, authority_operation),
        )
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert repository.loads == 0


def test_fresh_period_and_sealed_historical_scope_without_reload(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    unit = _unit()
    repository = _WorkRepository(unit)
    registry, registration, calls = _registration(repository, authority_operation)
    request = _request(unit)
    fresh = resolve_operation_access(
        registry=registry, request=request, context=_context(registration, authority_operation)
    )
    assert fresh.request.periods == frozenset({unit.period})
    assert AccessAction.COMMIT not in fresh.policy.actions
    assert repository.loads == 1 and calls == [str(_PROFILE)]
    admitted = OperationAccessRequest(
        profile_id=_PROFILE,
        definition_id=MODELO_WORK_HISTORY_OPERATION_DEFINITION_ID,
        action=AccessAction.SUBMIT,
        frontend=OperationFrontendProjection.CLI,
        periods=frozenset({unit.period}),
        period_independent=False,
        destination_id=uuid4(),
    )
    for action in (AccessAction.OBSERVE, AccessAction.RESULT):
        historical = resolve_operation_access(
            registry=registry,
            request=request,
            context=_context(registration, None, action=action, admitted=admitted),
        )
        assert historical.request.periods == admitted.periods
    assert repository.loads == 1 and calls == [str(_PROFILE)]
