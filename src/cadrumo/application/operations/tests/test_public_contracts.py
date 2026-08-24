"""Conformance tests for the renderer-neutral public operation DTO family."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

import cadrumo.application.operations as public_operations
from cadrumo.application.operations import (
    OperationBaselinePolicy,
    OperationCancellation,
    OperationCancellationRefusalCode,
    OperationCancellationRefusalV1,
    OperationCancellationVersionHeader,
    OperationCapabilities,
    OperationClosePolicy,
    OperationConflictScope,
    OperationDeadline,
    OperationDefinition,
    OperationDetachRefusalCode,
    OperationDetachRefusalV1,
    OperationDetachVersionHeader,
    OperationDurability,
    OperationEffect,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationNoPendingInteractionV1,
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
    OperationPublicContractSetV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressV1,
    OperationPublicProjectionV1,
    OperationReconciliationPolicy,
    OperationRegistry,
    OperationReplayPolicy,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationResponseControlRefusalCode,
    OperationResponseControlRefusalV1,
    OperationResponseControlVersionHeader,
    OperationReviewProjectionReferenceV1,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionResultV1,
    OperationReviewProjectionSuccessV1,
    OperationReviewProjectionVersionHeader,
    OperationSchemaBindingV1,
    OperationSchemaIdentityV1,
    OperationSensitiveInputPolicy,
    OperationTerminalCondition,
    OperationUnsupportedInteractionV1,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetResultV1,
    OperationWorkspaceRefreshTargetSuccessV1,
    OperationWorkspaceRefreshTargetVersionHeader,
)
from cadrumo.application.operations._executor import OperationExecutorContext
from cadrumo.application.operations._model_contract import require_strict_frozen_operation_model_graph
from cadrumo.core import OperationEventKind, OperationInteractionKind, OperationLifecycle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)
_OPERATION_ID = "1" * 64
_INTERACTION_ID = "2" * 64
_DIGEST = "3" * 64
_SCHEMA = OperationSchemaIdentityV1(
    schema_id="profile.sync.review",
    schema_version=1,
    schema_fingerprint=_DIGEST,
)


class SafeProjection(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
    code: Annotated[str, Field(min_length=1)]


class ProjectionContractExecutor:
    """Executable no-effect operation used to exercise the real registry contract path."""

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | None:
        del context
        return request.subject_ref


def _projection_contract_set(
    *,
    interaction_kinds: frozenset[OperationInteractionKind] = frozenset(),
    cancellation: OperationCancellation = OperationCancellation.UNSUPPORTED,
) -> OperationPublicContractSetV1:
    definition = OperationDefinition(
        definition_id="operations.public.projection",
        request_type=SafeProjection,
        result_type=SafeProjection,
        executor_factory=OperationExecutorFactory(
            request_type=SafeProjection,
            executor_type=ProjectionContractExecutor,
            build=ProjectionContractExecutor,
        ),
        phase_codes=("operations.public.running",),
        interaction_kinds=interaction_kinds,
        capabilities=OperationCapabilities(
            durability=OperationDurability.EPHEMERAL,
            cancellation=cancellation,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.NONE,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.NONE,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.TUI}),
    )
    registration = public_operations.OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.public.projection.request",
            schema_version=1,
            model_type=SafeProjection,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="operations.public.projection.result",
            schema_version=1,
            model_type=SafeProjection,
        ),
    )
    return OperationRegistry(
        definitions=(definition,),
        public_registrations=(registration,),
    ).public_contract_set


def _projection(
    *,
    contract_set: OperationPublicContractSetV1 | None = None,
    **changes: object,
) -> OperationPublicProjectionV1:
    contract_set = _projection_contract_set() if contract_set is None else contract_set
    contract = contract_set.definitions[0]
    values: dict[str, object] = {
        "operation_id": _OPERATION_ID,
        "definition_id": contract.definition_id,
        "subject_ref": "profile:active",
        "revision": 4,
        "anchor_cursor": 0,
        "definition_contract": contract,
        "contract_set_digest": contract_set.contract_set_digest,
        "lifecycle": OperationLifecycle.RUNNING,
        "terminal_condition": None,
        "effect": OperationEffect.NONE,
        "phase_code": "operations.public.running",
        "started_at": _NOW,
        "updated_at": _NOW,
        "progress": None,
        "close_policy": contract.close_policy,
        "cancellation": contract.cancellation,
        "cancellable_now": False,
        "cancellation_requested": False,
        "cancellation_acknowledged": False,
        "execution_deadline_at": None,
        "cleanup_deadline_at": None,
        "pending_interaction": OperationNoPendingInteractionV1(),
        "result_ref": None,
        "refusal_ref": None,
        "diagnostic_ref": None,
    }
    values.update(changes)
    return OperationPublicProjectionV1.model_validate(values)


def test_public_endpoint_versions_are_independent_strict_axes() -> None:
    observation = OperationObservationRequestV1(
        operation_id=_OPERATION_ID,
        after_cursor=0,
        page_limit=20,
    )
    refresh = OperationWorkspaceRefreshTargetRequestV1(
        operation_id=_OPERATION_ID,
        terminal_revision=4,
        definition_contract_digest=_DIGEST,
        target_schema=_SCHEMA,
    )

    assert observation.observation_version == 1
    assert refresh.refresh_target_version == 1
    assert "version" not in observation.__class__.model_fields
    assert "version" not in refresh.__class__.model_fields
    assert "result_ref" not in refresh.__class__.model_fields
    headers = (
        OperationObservationVersionHeader(observation_version=2),
        OperationReviewProjectionVersionHeader(review_projection_version=2),
        OperationResponseControlVersionHeader(response_control_version=2),
        OperationCancellationVersionHeader(cancellation_version=2),
        OperationDetachVersionHeader(detach_version=2),
        OperationWorkspaceRefreshTargetVersionHeader(refresh_target_version=2),
    )
    assert tuple(next(iter(header.model_dump().values())) for header in headers) == (2,) * 6
    with pytest.raises(ValidationError):
        OperationObservationRequestV1.model_validate(
            {
                "observation_version": "1",
                "operation_id": _OPERATION_ID,
                "after_cursor": 0,
                "page_limit": 20,
            }
        )
    with pytest.raises(ValidationError):
        OperationObservationRequestV1(
            operation_id=_OPERATION_ID,
            after_cursor=0,
            page_limit=20,
            unknown=True,
        )


def test_observation_result_is_a_closed_discriminated_union() -> None:
    adapter = TypeAdapter(OperationObservationResultV1)

    assert isinstance(
        adapter.validate_python(
            OperationObservationRefusalV1(
                code=OperationObservationRefusalCode.UNKNOWN_OPERATION,
                requested_version=1,
                diagnostic_ref=None,
            )
        ),
        OperationObservationRefusalV1,
    )
    assert OperationObservationSuccessV1.model_fields["projection"].annotation is OperationPublicProjectionV1


def test_observation_success_requires_one_exact_projection_page_anchor() -> None:
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=0,
        requested_cursor=0,
        status="caught_up",
        events=(),
        next_cursor=0,
        restart_cursor=None,
    )

    assert OperationObservationSuccessV1(projection=_projection(), event_page=page).event_page == page
    with pytest.raises(ValidationError, match="share one anchor"):
        OperationObservationSuccessV1(
            projection=_projection(anchor_cursor=1),
            event_page=page,
        )


def test_observation_success_refuses_event_rows_newer_than_its_projection() -> None:
    event = OperationPublicPhaseEventV1(
        revision=5,
        sequence=1,
        timestamp=_NOW,
        code="operations.public.advanced",
        kind=OperationEventKind.PHASE,
        phase_code="operations.public.running",
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=1,
        requested_cursor=0,
        status="page",
        events=(event,),
        next_cursor=1,
        restart_cursor=None,
    )

    with pytest.raises(ValidationError, match="event row revision"):
        OperationObservationSuccessV1(projection=_projection(anchor_cursor=1), event_page=page)


def test_public_projection_refuses_terminal_pending_interaction_and_axis_drift() -> None:
    pending = OperationUnsupportedInteractionV1(
        interaction_kind=OperationInteractionKind.INPUT,
        interaction_id=_INTERACTION_ID,
        revision=4,
        presentation_code="operations.public.input",
        unsupported_code="operations.public.unsupported",
        expires_at=None,
    )

    with pytest.raises(ValidationError, match="cannot carry a pending interaction"):
        _projection(
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.FAILED,
            pending_interaction=pending,
        )
    with pytest.raises(ValidationError, match="terminal lifecycle"):
        _projection(terminal_condition=OperationTerminalCondition.FAILED)
    with pytest.raises(ValidationError, match="cancellation does not match"):
        _projection(cancellation=OperationCancellation.COOPERATIVE)


def test_public_projection_refuses_progress_phase_and_pending_interaction_drift() -> None:
    with pytest.raises(ValidationError, match="progress phase"):
        _projection(
            anchor_cursor=1,
            progress=OperationPublicProgressV1(
                completed=1,
                total=2,
                unit_code="operations.public.unit",
                phase_code="operations.public.previous-phase",
                event_sequence=1,
                revision=4,
            ),
        )

    declared_input_contracts = _projection_contract_set(
        interaction_kinds=frozenset({OperationInteractionKind.INPUT}),
    )
    current_input = OperationUnsupportedInteractionV1(
        interaction_kind=OperationInteractionKind.INPUT,
        interaction_id=_INTERACTION_ID,
        revision=4,
        presentation_code="operations.public.input",
        unsupported_code="operations.public.unsupported",
        expires_at=None,
    )
    with pytest.raises(ValidationError, match="current operation revision"):
        _projection(
            contract_set=declared_input_contracts,
            lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
            pending_interaction=current_input.model_copy(update={"revision": 3}),
        )
    with pytest.raises(ValidationError, match="declared by the definition contract"):
        _projection(
            lifecycle=OperationLifecycle.WAITING_FOR_INTERACTION,
            pending_interaction=current_input,
        )
    with pytest.raises(ValidationError, match="waiting-for-interaction lifecycle"):
        _projection(
            contract_set=declared_input_contracts,
            pending_interaction=current_input,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"started_at": _NOW + timedelta(seconds=1)},
        {"execution_deadline_at": _NOW - timedelta(seconds=1)},
        {"cleanup_deadline_at": _NOW + timedelta(seconds=1)},
    ],
)
def test_public_projection_refuses_deadline_and_timeline_drift(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match=r"start|deadline"):
        _projection(**changes)


def test_public_projection_refuses_cancellation_fact_drift() -> None:
    with pytest.raises(ValidationError, match="request or acknowledgement"):
        _projection(
            cancellation_requested=True,
            cleanup_deadline_at=_NOW + timedelta(seconds=1),
        )
    with pytest.raises(ValidationError, match="requires its declared request fact"):
        _projection(lifecycle=OperationLifecycle.CANCELLATION_REQUESTED)
    with pytest.raises(ValidationError, match="requires cancellation acknowledgement"):
        _projection(
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.CANCELLED,
        )


def test_public_projection_refuses_cancellation_availability_drift() -> None:
    cancellable_contracts = _projection_contract_set(cancellation=OperationCancellation.COOPERATIVE)

    assert _projection(contract_set=cancellable_contracts, cancellable_now=True).cancellable_now
    with pytest.raises(ValidationError, match="currently available after it is requested"):
        _projection(
            contract_set=cancellable_contracts,
            cancellable_now=True,
            cancellation_requested=True,
            cleanup_deadline_at=_NOW + timedelta(seconds=1),
        )
    with pytest.raises(ValidationError, match="while settlement is underway"):
        _projection(
            contract_set=cancellable_contracts,
            lifecycle=OperationLifecycle.SETTLING,
            cancellable_now=True,
        )


def test_public_event_page_enforces_contiguous_bounded_rows_and_resynchronization() -> None:
    first = OperationPublicPhaseEventV1(
        revision=2,
        sequence=1,
        timestamp=_NOW,
        code="phase.changed",
        kind=OperationEventKind.PHASE,
        phase_code="profile.sync",
    )
    page = OperationPublicEventPageV1(
        operation_id=_OPERATION_ID,
        anchor_cursor=1,
        requested_cursor=0,
        status="page",
        events=(first,),
        next_cursor=1,
        restart_cursor=None,
    )
    assert page.events == (first,)

    with pytest.raises(ValidationError, match="contiguous"):
        OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=2,
            requested_cursor=0,
            status="page",
            events=(first.model_copy(update={"sequence": 2}),),
            next_cursor=2,
            restart_cursor=None,
        )
    with pytest.raises(ValidationError, match="restart cursor"):
        OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=4,
            requested_cursor=1,
            status="compacted",
            events=(),
            next_cursor=1,
            restart_cursor=None,
        )
    with pytest.raises(ValidationError, match="equal its observation anchor cursor"):
        OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=2,
            requested_cursor=1,
            status="caught_up",
            events=(),
            next_cursor=1,
            restart_cursor=None,
        )


def test_review_reference_and_success_never_carry_response_authority() -> None:
    reference = OperationReviewProjectionReferenceV1(
        operation_id=_OPERATION_ID,
        interaction_id=_INTERACTION_ID,
        revision=4,
        review_projection_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        expires_at=_NOW,
    )
    success = OperationReviewProjectionSuccessV1[SafeProjection](
        projection_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        projection=SafeProjection(code="review.ready"),
    )
    adapter = TypeAdapter(OperationReviewProjectionResultV1[SafeProjection])

    assert adapter.validate_python(success) == success
    forbidden = {"token", "bearer", "payload", "operand", "continuation", "baseline", "capability"}
    reference_fields = set(reference.__class__.model_fields)
    success_fields = set(success.__class__.model_fields)
    assert not any(part in field for field in reference_fields | success_fields for part in forbidden)
    with pytest.raises(ValidationError):
        OperationReviewProjectionSuccessV1[SafeProjection](
            projection_schema=_SCHEMA,
            definition_contract_digest=_DIGEST,
            projection={"code": 1},
        )


@pytest.mark.parametrize(
    ("model", "code"),
    [
        (OperationObservationRefusalV1, OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE),
        (OperationReviewProjectionRefusalV1, OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE),
        (OperationResponseControlRefusalV1, OperationResponseControlRefusalCode.RESPONSE_AUTHORITY_UNAVAILABLE),
        (OperationCancellationRefusalV1, OperationCancellationRefusalCode.CANCELLATION_UNAVAILABLE),
        (OperationDetachRefusalV1, OperationDetachRefusalCode.DETACH_NOT_ALLOWED),
        (
            OperationWorkspaceRefreshTargetRefusalV1,
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
        ),
    ],
)
def test_public_refusals_are_closed_renderer_neutral_records(
    model: type[BaseModel],
    code: StrEnum,
) -> None:
    refusal = model(code=code, requested_version=1, diagnostic_ref=None)
    assert refusal.outcome == "refused"
    assert set(refusal.model_dump()) <= {
        "outcome",
        "observation_version",
        "review_projection_version",
        "response_control_version",
        "cancellation_version",
        "detach_version",
        "refresh_target_version",
        "code",
        "requested_version",
        "supported_version",
        "diagnostic_ref",
    }


def test_refresh_result_is_exactly_specialized_and_exported_from_the_facade() -> None:
    success = OperationWorkspaceRefreshTargetSuccessV1[SafeProjection](
        target_schema=_SCHEMA,
        definition_contract_digest=_DIGEST,
        target=SafeProjection(code="workspace.refresh"),
    )
    adapter = TypeAdapter(OperationWorkspaceRefreshTargetResultV1[SafeProjection])

    assert adapter.validate_python(success) == success
    assert public_operations.OperationWorkspaceRefreshTargetRequestV1 is (OperationWorkspaceRefreshTargetRequestV1)
    assert public_operations.OperationPublicProjectionV1 is OperationPublicProjectionV1


def _exported_public_model_types() -> tuple[type[BaseModel], ...]:
    models: list[type[BaseModel]] = []
    for name in public_operations.__all__:
        candidate = getattr(public_operations, name)
        if not isinstance(candidate, type) or not issubclass(candidate, BaseModel):
            continue
        if candidate.__module__ != "cadrumo.application.operations._public":
            continue
        if candidate is OperationReviewProjectionSuccessV1:
            candidate = OperationReviewProjectionSuccessV1[SafeProjection]
        elif candidate is OperationWorkspaceRefreshTargetSuccessV1:
            candidate = OperationWorkspaceRefreshTargetSuccessV1[SafeProjection]
        models.append(candidate)
    return tuple(models)


@pytest.mark.parametrize("model_type", _exported_public_model_types())
def test_every_exported_public_model_graph_is_strict_frozen_and_closed(model_type: type[BaseModel]) -> None:
    require_strict_frozen_operation_model_graph(model_type, path="public DTO")
    OperationSchemaIdentityV1.from_model(
        schema_id="operations.public.contract",
        schema_version=1,
        model_type=model_type,
    )
