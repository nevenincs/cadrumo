"""A scripted runtime boundary for the invoice, record and link TUI doors.

Each submission is answered by the next scripted terminal state, whose public
contract comes from the operation's real definition and registration builders,
so the door under test meets exactly the receipt shape the runtime publishes.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.application.invoices.catalogue_intake_operation import (
    build_invoice_import_definition,
    build_invoice_intake_registration,
    build_invoice_wizard_definition,
)
from cadrumo.application.invoices.catalogue_intake_operation_ports import InvoiceIntakePortsFactory
from cadrumo.application.invoices.catalogue_lifecycle_ports import CatalogueLifecyclePortsFactory
from cadrumo.application.invoices.catalogue_read_operation import (
    build_invoice_list_definition,
    build_invoice_list_registration,
    build_invoice_view_definition,
    build_invoice_view_registration,
)
from cadrumo.application.invoices.catalogue_remove_operation import (
    build_invoice_remove_definition,
    build_invoice_remove_registration,
)
from cadrumo.application.invoices.catalogue_update_operation import (
    build_invoice_update_definition,
    build_invoice_update_registration,
)
from cadrumo.application.invoices.inspection_read_ports import InvoiceInspectionReadPortsFactory
from cadrumo.application.ledger.action_ports import LedgerActionPortsFactory
from cadrumo.application.ledger.link_operation import build_ledger_link_definition, build_ledger_link_registration
from cadrumo.application.ledger.own_account_ports import OwnAccountRepositoryFactory
from cadrumo.application.ledger.update_operation import (
    build_ledger_update_definition,
    build_ledger_update_registration,
)
from cadrumo.application.ledger.view_operation import build_ledger_view_definition, build_ledger_view_registration
from cadrumo.application.operations.error_detail import OperationErrorDetailV1
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1, OperationPublicEventPageV1
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
    OperationRegistry,
)
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.account import AccountSessionExpiredError
from cadrumo.entrypoints.tui.ledger.tests.invoices_fixtures import INVOICES_PROFILE_ID
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_controller import OperationController

OTHER_PROFILE_ID = UUID("4ee00000-0000-4000-8000-0000000000ee")
SESSION_ID = UUID("6dd00000-0000-4000-8000-0000000000dd")
LAPSED_SESSION_ID = UUID("7dd00000-0000-4000-8000-0000000000dd")
PROFILE_LABEL = "Fixture profile"
_OPERATION_ID = "d" * 64
_NOW = datetime(2026, 10, 22, tzinfo=UTC)


def _unused[T](kind: type[T]) -> T:
    """A port factory the contract builders hold but these tests never call."""
    del kind
    return cast("T", cast(object, lambda **_kwargs: None))


def _registry() -> OperationRegistry:
    read_ports = _unused(InvoiceInspectionReadPortsFactory)
    lifecycle_ports = _unused(CatalogueLifecyclePortsFactory)
    intake_ports = _unused(InvoiceIntakePortsFactory)
    ledger_ports = _unused(LedgerActionPortsFactory)
    pairs = []
    for definition, register in (
        (build_invoice_list_definition(read_ports), build_invoice_list_registration),
        (build_invoice_view_definition(read_ports), build_invoice_view_registration),
        (build_invoice_update_definition(lifecycle_ports), build_invoice_update_registration),
        (build_invoice_remove_definition(lifecycle_ports), build_invoice_remove_registration),
        (build_invoice_import_definition(intake_ports), build_invoice_intake_registration),
        (build_invoice_wizard_definition(intake_ports), build_invoice_intake_registration),
        (build_ledger_view_definition(ledger_ports), build_ledger_view_registration),
        (
            build_ledger_update_definition(ledger_ports, _unused(OwnAccountRepositoryFactory)),
            build_ledger_update_registration,
        ),
        (build_ledger_link_definition(ledger_ports), build_ledger_link_registration),
    ):
        pairs.append((definition, register(definition)))
    pairs.sort(key=lambda pair: pair[0].definition_id)
    return OperationRegistry(
        definitions=tuple(definition for definition, _registration in pairs),
        public_registrations=tuple(registration for _definition, registration in pairs),
    )


REGISTRY = _registry()


@dataclass(frozen=True)
class Settled:
    """One scripted terminal state and the result the runtime would release for it."""

    definition_id: str
    result: BaseModel | None
    effect: OperationEffect = OperationEffect.NONE
    condition: OperationTerminalCondition = OperationTerminalCondition.SUCCEEDED
    refusal_ref: str | None = None
    detail: OperationErrorDetailV1 | None = None

    @property
    def contract(self) -> OperationPublicDefinitionContractV1:
        """The operation's public contract, as its real definition and registration declare it."""
        return REGISTRY.lookup_public_contract(self.definition_id)

    def observation(self) -> OperationObservationSuccessV1:
        contract = self.contract
        succeeded = self.condition is OperationTerminalCondition.SUCCEEDED
        state = OperationPublicProjectionV1(
            operation_id=_OPERATION_ID,
            definition_id=self.definition_id,
            subject_ref=profile_operation_subject(str(INVOICES_PROFILE_ID)),
            revision=1,
            anchor_cursor=0,
            definition_contract=contract,
            contract_set_digest=REGISTRY.public_contract_set.contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=self.condition,
            effect=self.effect,
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
            result_ref="f" * 64 if succeeded else None,
            refusal_ref=self.refusal_ref,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        return OperationObservationSuccessV1(
            projection=state,
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


class FakeClient:
    """The admitted TUI client the doors pin; changing its session lapses it."""

    frontend = OperationFrontendProjection.TUI

    def __init__(self) -> None:
        self.profile_id = INVOICES_PROFILE_ID
        self.session_id = SESSION_ID


@dataclass
class _Controller:
    operation_id = _OPERATION_ID
    client: FakeClient
    _settled: Settled
    _reads: list[tuple[type[BaseModel], bool]]
    deadline: float | None = None

    @property
    def definition_contract(self) -> OperationPublicDefinitionContractV1:
        return self._settled.contract

    async def start(self) -> str:
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int) -> OperationObservationSuccessV1:
        assert (after_cursor, page_limit) == (0, 1)
        return self._settled.observation()

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
        allow_refusal_detail: bool = False,
    ) -> BaseModel:
        assert projection.operation_id == self.operation_id
        assert result_version == 1
        self._reads.append((result_type, allow_refusal_detail))
        assert self._settled.result is not None
        assert isinstance(self._settled.result, result_type)
        return self._settled.result

    async def settled_error_detail(self, projection: OperationPublicProjectionV1) -> OperationErrorDetailV1 | None:
        assert projection.operation_id == self.operation_id
        return self._settled.detail


@dataclass
class Boundary:
    """What reached the scripted runtime: each submission's keyword arguments and each result read."""

    client: FakeClient
    script: list[Settled]
    submissions: list[dict[str, object]] = field(default_factory=list)
    reads: list[tuple[type[BaseModel], bool]] = field(default_factory=list)
    session_read_threads: list[int] = field(default_factory=list)
    """The thread of each blocking session read: at composition, then around each operation."""

    @property
    def payloads(self) -> list[object]:
        return [submission["payload"] for submission in self.submissions]

    @property
    def definitions(self) -> list[object]:
        return [submission["definition_id"] for submission in self.submissions]


def install(monkeypatch: pytest.MonkeyPatch, *script: Settled) -> Boundary:
    """Answer each submission with the next scripted state, refusing any the script did not expect."""
    from ....frontend.tui.operations import runtime_profile_session as bridge

    boundary = Boundary(client=FakeClient(), script=list(script))

    def read_session(_client: FrontendClient, *, profile_id: UUID, session_id: UUID, profile_label: str) -> object:
        assert profile_label == PROFILE_LABEL
        boundary.session_read_threads.append(threading.get_ident())
        if boundary.client.profile_id != profile_id or boundary.client.session_id != session_id:
            raise AccountSessionExpiredError()
        return object()

    monkeypatch.setattr(bridge, "read_runtime_account_session", read_session)

    async def submit(
        _controller_type: type[OperationController], received: FrontendClient, **kwargs: object
    ) -> _Controller:
        assert received is boundary.client
        settled = boundary.script.pop(0)
        assert kwargs["definition_id"] == settled.definition_id
        assert kwargs["expected_session_id"] == SESSION_ID
        boundary.submissions.append(kwargs)
        return _Controller(boundary.client, settled, boundary.reads)

    monkeypatch.setattr(OperationController, "submit", classmethod(submit))
    return boundary


def client_of(boundary: Boundary) -> FrontendClient:
    return cast(FrontendClient, boundary.client)


__all__ = [
    "LAPSED_SESSION_ID",
    "OTHER_PROFILE_ID",
    "PROFILE_LABEL",
    "REGISTRY",
    "SESSION_ID",
    "Boundary",
    "FakeClient",
    "Settled",
    "client_of",
    "install",
]
