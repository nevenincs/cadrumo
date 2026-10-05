"""Terminal observation keeps polling one exact operation and refuses any foreign projection."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.invoices.catalogue_add_contracts import (
    INVOICE_ADD_OPERATION_DEFINITION_ID,
    InvoiceAddRequest,
)
from cadrumo.application.invoices.catalogue_add_operation import (
    build_invoice_add_definition,
    build_invoice_add_registration,
)
from cadrumo.application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.operations.runtime_controller import (
    RuntimeOperationController,
    await_terminal_projection,
)

from .....application.operations.schema_identity import OperationSchemaIdentityV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "b" * 64
_SUBJECT = profile_operation_subject(str(UUID("5aa00000-0000-4000-8000-0000000000aa")))
_NOW = datetime(2026, 9, 29, tzinfo=UTC)
_REQUEST_SCHEMA = OperationSchemaIdentityV1.from_model(
    schema_id=f"{INVOICE_ADD_OPERATION_DEFINITION_ID}.request", schema_version=1, model_type=InvoiceAddRequest
)


def _projection(*, terminal: bool) -> OperationPublicProjectionV1:
    factory = cast(CatalogueCreationPortsFactory, cast(object, lambda **_kwargs: None))
    definition = build_invoice_add_definition(factory)
    registry = OperationRegistry(
        definitions=(definition,), public_registrations=(build_invoice_add_registration(definition),)
    )
    contract = registry.lookup_public_contract(INVOICE_ADD_OPERATION_DEFINITION_ID)
    return OperationPublicProjectionV1(
        operation_id=_OPERATION_ID,
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=_SUBJECT,
        revision=2 if terminal else 1,
        anchor_cursor=0,
        definition_contract=contract,
        contract_set_digest=registry.public_contract_set.contract_set_digest,
        lifecycle=OperationLifecycle.TERMINAL if terminal else OperationLifecycle.RUNNING,
        terminal_condition=OperationTerminalCondition.SUCCEEDED if terminal else None,
        effect=OperationEffect.UPDATED if terminal else OperationEffect.NONE,
        phase_code=None,
        started_at=_NOW,
        updated_at=_NOW,
        progress=None,
        close_policy=contract.close_policy,
        cancellation=contract.cancellation,
        cancellable_now=False,
        cancellation_requested=False,
        cancellation_acknowledged=False,
        execution_deadline_at=None,
        cleanup_deadline_at=None,
        pending_interaction=OperationNoPendingInteractionV1(),
        result_ref="f" * 64 if terminal else None,
        refusal_ref=None,
        failure_error_code=None,
        diagnostic_ref=None,
    )


def _observed(projection: OperationPublicProjectionV1) -> OperationObservationSuccessV1:
    return OperationObservationSuccessV1(
        projection=projection,
        event_page=OperationPublicEventPageV1(
            operation_id=_OPERATION_ID,
            anchor_cursor=0,
            requested_cursor=0,
            status=OperationReplayStatus.CAUGHT_UP,
            events=(),
            next_cursor=0,
            restart_cursor=None,
        ),
    )


class _Controller:
    def __init__(self, *observations: OperationObservationResultV1) -> None:
        self.operation_id = _OPERATION_ID
        self._observations = list(observations)
        self.requests: list[tuple[int, int]] = []

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationResultV1:
        self.requests.append((after_cursor, page_limit))
        return self._observations.pop(0)


async def _await(controller: _Controller, *, deadline: float | None = None) -> OperationPublicProjectionV1:
    return await await_terminal_projection(
        cast(RuntimeOperationController, controller),
        definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
        subject_ref=_SUBJECT,
        request_schema=_REQUEST_SCHEMA,
        deadline=time.monotonic() + 30 if deadline is None else deadline,
        poll_seconds=0.001,
    )


@pytest.mark.asyncio
async def test_polls_the_latest_projection_until_terminal() -> None:
    terminal = _projection(terminal=True)
    controller = _Controller(_observed(_projection(terminal=False)), _observed(terminal))

    assert await _await(controller) == terminal
    assert controller.requests == [(0, 1), (0, 1)]


@pytest.mark.asyncio
async def test_a_projection_for_another_request_schema_is_an_invalid_frame() -> None:
    contract = _projection(terminal=True).definition_contract
    foreign_schema = _REQUEST_SCHEMA.model_copy(update={"schema_version": 2})
    foreign = _projection(terminal=True).model_copy(
        update={"definition_contract": contract.model_copy(update={"request_schema": foreign_schema})}
    )

    with pytest.raises(RuntimeRefusalError) as refused:
        await _await(_Controller(_observed(foreign)))
    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_an_observation_refusal_keeps_its_code() -> None:
    refusal = OperationObservationRefusalV1(
        code=OperationObservationRefusalCode.UNKNOWN_OPERATION, requested_version=None, diagnostic_ref=None
    )

    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        await _await(_Controller(refusal))
    assert refused.value.reason == OperationObservationRefusalCode.UNKNOWN_OPERATION.value


@pytest.mark.asyncio
async def test_an_expired_deadline_refuses_before_observing() -> None:
    controller = _Controller(_observed(_projection(terminal=True)))

    with pytest.raises(RuntimeRefusalError) as refused:
        await _await(controller, deadline=time.monotonic() - 1)
    assert refused.value.reason is RuntimeRefusalCode.DEADLINE_EXCEEDED
    assert controller.requests == []
