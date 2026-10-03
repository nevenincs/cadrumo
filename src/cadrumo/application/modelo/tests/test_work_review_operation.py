"""Compact work review schema and exact-profile admission remain canonical."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, ValidationError

from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, OperationAccessRequest
from ...user_profile.access_errors import ProfileAccessRefusedError
from ..history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory
from ..work_review_contracts import (
    MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
    ModeloWorkReviewFact,
    ModeloWorkReviewProgressSnapshot,
    ModeloWorkReviewProjection,
    ModeloWorkReviewRequest,
    ModeloWorkReviewSnapshot,
)
from ..work_review_operation import (
    ModeloWorkReviewExecutor,
    build_modelo_work_review_definition,
    build_modelo_work_review_registration,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_PERIOD = Period.from_year_and_code(2026, "1T")


class _GuardPhaseReachedError(Exception):
    pass


class _GuardEvents:
    def __init__(self) -> None:
        self.phases: list[str] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)
        raise _GuardPhaseReachedError(phase)


def _executor_request(unit: WorkUnit, *, subject_ref: str | None = None) -> OperationRequest[ModeloWorkReviewRequest]:
    return OperationRequest[ModeloWorkReviewRequest](
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref if subject_ref is not None else unit.work_unit_id,
        payload=ModeloWorkReviewRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id),
    )


def _executor_context(
    request: OperationRequest[ModeloWorkReviewRequest],
    *,
    definition_id: str | None = None,
    subject_ref: str | None = None,
) -> tuple[OperationExecutorContext, _GuardEvents]:
    events = _GuardEvents()
    context = cast(
        OperationExecutorContext,
        cast(
            object,
            SimpleNamespace(
                identity=OperationIdentity(
                    operation_id="a" * 64,
                    definition_id=definition_id if definition_id is not None else request.definition_id,
                    subject_ref=subject_ref if subject_ref is not None else request.subject_ref,
                ),
                events=events,
            ),
        ),
    )
    return context, events


def _unit() -> WorkUnit:
    instant = datetime(2026, 3, 10, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=str(_PROFILE), modelo="303", filing_year=2026, period=_PERIOD, revision_id="2026-y-siguientes"
        ),
        bucket_id=str(_PROFILE),
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="2026-y-siguientes",
        name="First quarter",
        created_at=instant,
        updated_at=instant,
    )


def _snapshot(unit: WorkUnit) -> ModeloWorkReviewSnapshot:
    return ModeloWorkReviewSnapshot(
        bucket_id=unit.bucket_id,
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period={"filing_year": unit.filing_year, "code": unit.period.registry_token},
        registry_revision_id=unit.revision_id,
        work_unit_id=unit.work_unit_id,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkReviewProgressSnapshot(state=ModeloWorkProgressState.UNDEFINED),
        casilla_count=0,
        findings=(),
        blockers=(),
        row_source_fingerprint_count=0,
    )


@pytest.mark.parametrize("failure", ["wrong_unit", "identity_definition", "identity_subject", "bucket"])
def test_work_review_executor_profile_guard_preserves_work_unit_subject(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    unit = _unit()
    request_subject = "another-work-unit" if failure == "wrong_unit" else unit.work_unit_id
    request = _executor_request(unit, subject_ref=request_subject)
    context, events = _executor_context(
        request,
        definition_id="modelo.work.other" if failure == "identity_definition" else None,
        subject_ref="another-work-unit" if failure == "identity_subject" else None,
    )
    active_bucket = str(_OTHER if failure == "bucket" else _PROFILE)
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: active_bucket)
    executor = ModeloWorkReviewExecutor(cast(ModeloHistoryPortsFactory, cast(object, lambda **_kwargs: None)))

    with pytest.raises(ProfileAccessRefusedError) as refused:
        asyncio.run(executor.execute(request, context))

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert events.phases == []


def test_work_review_executor_accepts_its_work_unit_subject_at_the_guard_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = _unit()
    request = _executor_request(unit)
    context, events = _executor_context(request)
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    executor = ModeloWorkReviewExecutor(cast(ModeloHistoryPortsFactory, cast(object, lambda **_kwargs: None)))

    with pytest.raises(_GuardPhaseReachedError) as reached:
        asyncio.run(executor.execute(request, context))

    assert str(reached.value) == MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID
    assert events.phases == [MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID]


def test_compact_projection_round_trips_and_refuses_foreign_profile() -> None:
    snapshot = _snapshot(_unit())
    projection = ModeloWorkReviewProjection(profile_id=_PROFILE, review=snapshot)
    assert ModeloWorkReviewProjection.model_validate_json(projection.model_dump_json()) == projection
    with pytest.raises(ValidationError):
        ModeloWorkReviewProjection(profile_id=_OTHER, review=snapshot)
    with pytest.raises(ValidationError):
        ModeloWorkReviewSnapshot.model_validate(snapshot.model_dump(mode="python") | {"filing_year": 2025})


@pytest.mark.parametrize("value", ["token", 17, True, Decimal("1.20"), None])
def test_review_fact_preserves_canonical_scalar_type(value: str | int | bool | Decimal | None) -> None:
    fact = ModeloWorkReviewFact.from_value("sample", value)
    encoded = ModeloWorkReviewFact.model_validate_json(fact.model_dump_json())
    assert encoded.to_value() == value
    assert type(encoded.to_value()) is type(value)


@pytest.mark.parametrize("kind,value", [("bool", "yes"), ("int", "01"), ("decimal", "NaN")])
def test_review_fact_rejects_ambiguous_encoded_values(kind: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ModeloWorkReviewFact.model_validate({"key": "sample", "kind": kind, "value": value})


def test_review_period_is_admitted_once_and_sealed_for_result(authority_operation: PinnedAuthorityOperation) -> None:
    unit = _unit()
    loads: list[str] = []

    class Repository:
        bucket_id = str(_PROFILE)

        def load(self) -> WorkUnitCatalogue:
            loads.append("load")
            return WorkUnitCatalogue(work_units={unit.work_unit_id: unit})

    def factory(*, bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloHistoryPorts:
        assert bucket_id == str(_PROFILE) and operation is authority_operation
        return cast(
            ModeloHistoryPorts,
            cast(
                object,
                SimpleNamespace(
                    work_unit_repository=Repository(),
                    calculation_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
                    verification_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
                    filing_repository=SimpleNamespace(bucket_id=str(_PROFILE)),
                ),
            ),
        )

    typed_factory = cast(ModeloHistoryPortsFactory, factory)
    definition = build_modelo_work_review_definition(typed_factory)
    registration = build_modelo_work_review_registration(definition, typed_factory)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = OperationRequest[BaseModel](
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        subject_ref=unit.work_unit_id,
        payload=ModeloWorkReviewRequest(profile_id=_PROFILE, work_unit_id=unit.work_unit_id),
    )

    def context(
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
            authority_operation=authority_operation if admitted is None else None,
        )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(registry=registry, request=request, context=context(profile_id=_OTHER))
    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH and loads == []
    fresh = resolve_operation_access(registry=registry, request=request, context=context())
    assert fresh.request.periods == frozenset({_PERIOD})
    assert AccessAction.COMMIT not in fresh.policy.actions
    assert loads == ["load"]
    historical = resolve_operation_access(
        registry=registry,
        request=request,
        context=context(action=AccessAction.RESULT, admitted=fresh.request),
    )
    assert historical.request.periods == fresh.request.periods
    assert loads == ["load"]
