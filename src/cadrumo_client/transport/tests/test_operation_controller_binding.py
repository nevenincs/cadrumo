"""A replaced TUI session cannot receive a reply from its old exchange."""

from __future__ import annotations

import asyncio
import time
from datetime import date
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.invoices.catalogue_add_contracts import INVOICE_ADD_OPERATION_DEFINITION_ID, InvoiceAddRequest
from cadrumo.application.invoices.catalogue_add_operation import build_invoice_add_definition, build_invoice_add_registration
from cadrumo.application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.public_scalar import PublicDecimal
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1, OperationRegistry
from cadrumo.core.operations import profile_operation_subject
from cadrumo.domain.iva.classification import InvoiceKind
from ...contracts.contracts import RefusalCode, RefusalError
from ...contracts.operation_access import OperationAcknowledged, OperationControl, OperationSubmit, OperationSubmitted
from ..frontend_client import FrontendClient
from ..operation_controller import OperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OPERATION_ID = "a" * 64


class _SessionChangingClient:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.session_id = uuid4()
        self.replacement_session_id = uuid4()
        self.reply: OperationAcknowledged | None = None

    def operation(self, request: OperationControl, *, deadline: float) -> OperationAcknowledged:
        del deadline
        assert request.session_id == self.session_id
        self.session_id = self.replacement_session_id
        self.reply = OperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            operation_id=_OPERATION_ID,
        )
        return self.reply


def test_exchange_discards_old_reply_when_session_changes_while_awaiting() -> None:
    client = _SessionChangingClient()
    original_session_id = client.session_id
    controller = OperationController(
        client=cast(FrontendClient, client),
        operation_id=_OPERATION_ID,
        session_id=original_session_id,
    )
    request = OperationControl(
        request_id=uuid4(),
        profile_id=uuid4(),
        session_id=original_session_id,
        action="operation_start",
        operation_id=_OPERATION_ID,
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(controller._exchange(request))

    assert client.reply is not None
    assert client.session_id == client.replacement_session_id
    assert raised.value.reason is RefusalCode.CONNECTION_CLOSED


class _RecordingClient:
    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.session_id = uuid4()
        self.profile_id = uuid4()
        self.contract_deadlines: list[float] = []
        self.operation_deadlines: list[float] = []
        factory = cast(CatalogueCreationPortsFactory, cast(object, lambda **_kwargs: None))
        definition = build_invoice_add_definition(factory)
        self.registry = OperationRegistry(
            definitions=(definition,), public_registrations=(build_invoice_add_registration(definition),)
        )

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        self.contract_deadlines.append(deadline)
        return self.registry.lookup_public_contract(definition_id)

    def operation(
        self, request: OperationSubmit | OperationControl, *, deadline: float
    ) -> OperationSubmitted | OperationAcknowledged:
        self.operation_deadlines.append(deadline)
        assert request.session_id == self.session_id
        assert request.profile_id == self.profile_id
        if isinstance(request, OperationSubmit):
            self.registry.lookup_public_contract(request.definition_id)
            payload = InvoiceAddRequest.model_validate_json(request.payload_json)
            assert payload.profile_id == self.profile_id
            assert request.subject_ref == profile_operation_subject(str(self.profile_id))
            return OperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=uuid4(),
                connection_id=uuid4(),
                receipt=OperationSubmissionReceiptV1(operation_id=_OPERATION_ID, secret_requirement=None),
            )
        return OperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=uuid4(),
            connection_id=uuid4(),
            operation_id=request.operation_id,
        )


def _submit(client: _RecordingClient, deadline: float | None) -> OperationController:
    payload = InvoiceAddRequest(
        profile_id=client.profile_id,
        kind=InvoiceKind.ISSUED,
        counterparty_name="Synthetic counterparty",
        counterparty_country="ES",
        invoice_number="SYNTHETIC-1",
        issued_at=date(2026, 1, 1),
        taxable_base=PublicDecimal(decimal="0"),
        currency="EUR",
    )
    return asyncio.run(
        OperationController.submit(
            cast(FrontendClient, client),
            definition_id=INVOICE_ADD_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            payload=payload,
            deadline=deadline,
        )
    )


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), float("-inf"), 99.0])
def test_submit_refuses_invalid_deadline_before_contract_or_operation_io(
    monkeypatch: pytest.MonkeyPatch, deadline: float
) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    client = _RecordingClient()

    with pytest.raises(RefusalError) as raised:
        _submit(client, deadline)

    assert raised.value.reason is RefusalCode.DEADLINE_EXCEEDED
    assert client.contract_deadlines == []
    assert client.operation_deadlines == []


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), float("-inf"), 99.0])
def test_retained_exchange_refuses_invalid_deadline_before_operation_io(
    monkeypatch: pytest.MonkeyPatch, deadline: float
) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    client = _RecordingClient()
    controller = OperationController(
        client=cast(FrontendClient, client),
        operation_id=_OPERATION_ID,
        session_id=client.session_id,
        deadline=deadline,
    )

    with pytest.raises(RefusalError) as raised:
        asyncio.run(controller.start())

    assert raised.value.reason is RefusalCode.DEADLINE_EXCEEDED
    assert client.contract_deadlines == []
    assert client.operation_deadlines == []


@pytest.mark.parametrize(("deadline", "expected"), [(110.0, 110.0), (200.0, 130.0), (None, 130.0)])
def test_submit_bounds_call_budget_and_retains_original_deadline(
    monkeypatch: pytest.MonkeyPatch, deadline: float | None, expected: float
) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    client = _RecordingClient()

    controller = _submit(client, deadline)

    assert client.contract_deadlines == [expected]
    assert client.operation_deadlines == [expected]
    assert controller.deadline == deadline
    assert controller.operation_id == _OPERATION_ID
    assert controller.session_id == client.session_id


@pytest.mark.parametrize(("deadline", "expected"), [(110.0, 110.0), (200.0, 130.0), (None, 130.0)])
def test_retained_exchange_bounds_call_budget_without_replacing_original_deadline(
    monkeypatch: pytest.MonkeyPatch, deadline: float | None, expected: float
) -> None:
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    client = _RecordingClient()
    controller = OperationController(
        client=cast(FrontendClient, client),
        operation_id=_OPERATION_ID,
        session_id=client.session_id,
        deadline=deadline,
    )

    assert asyncio.run(controller.start()) == _OPERATION_ID
    assert client.operation_deadlines == [expected]
    assert controller.deadline == deadline
