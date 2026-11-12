"""The census declarations destination's operations through the installed TUI's retained runtime session.

The destination is admitted only when the runtime describes the read and the
record operation under this session with the exact request and result schemas
and the profile subject this door reads and submits. The record form is built
from the request schema and contract the runtime served, never from a schema
this process composes. A read result must name the profile and the selection
asked, under a receipt that changed nothing, before anything reaches the screen.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.modelo.m036_operation import (
    M036_READ_OPERATION_DEFINITION_ID,
    M036_RECORD_OPERATION_DEFINITION_ID,
    M036ReadProjection,
    M036ReadRequest,
    M036RecordProjection,
    M036RecordRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.application.operations.subject_reference import OperationSubjectReferenceV1
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.entrypoints.tui.operations.catalogue import OperationCatalogueEntryV1, served_operation_entry
from cadrumo.entrypoints.tui.operations.run_screen import OperationRunScreen
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ..operations.runtime_profile_session import RuntimeProfileSession

_CONTRACT_SECONDS: Final = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS

CENSO_OPERATION_SHAPES: Final[Mapping[str, tuple[type[BaseModel], type[BaseModel]]]] = {
    M036_READ_OPERATION_DEFINITION_ID: (M036ReadRequest, M036ReadProjection),
    M036_RECORD_OPERATION_DEFINITION_ID: (M036RecordRequest, M036RecordProjection),
}
"""Every operation the destination needs: its request model and the public result it reads."""


def _schema(definition_id: str, kind: str, model_type: type[BaseModel]) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.{kind}", schema_version=1, model_type=model_type
    )


def censo_contract_matches(contract: OperationPublicDefinitionContractV1, definition_id: str) -> bool:
    """Whether ``contract`` is exactly the profile-subject operation this door submits under ``definition_id``."""
    request_type, result_type = CENSO_OPERATION_SHAPES[definition_id]
    return (
        contract.definition_id == definition_id
        and contract.subject_reference == OperationSubjectReferenceV1.profile()
        and contract.request_schema == _schema(definition_id, "request", request_type)
        and contract.result_schema == _schema(definition_id, "result", result_type)
    )


def _read_settled(
    profile_id: UUID,
    kind: str,
    declaration_id: str | None,
    result: M036ReadProjection,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether a read result answers exactly the profile and selection asked, under a receipt that changed nothing."""
    selected = declaration_id is None or (
        len(result.declarations) == 1 and result.declarations[0].declaration_id.startswith(declaration_id)
    )
    return (
        result.profile_id == profile_id
        and result.kind == kind
        and selected
        and condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is OperationEffect.NONE
    )


class RuntimeCensoTuiDoorV1:
    """Read and record one admitted profile's census declarations through its pinned session."""

    def __init__(self, client: FrontendClient, *, profile_label: str, record_form: OperationCatalogueEntryV1) -> None:
        """Pin the admitted profile and session, and the served form of the one change."""
        self._client = client
        self._session = RuntimeProfileSession(client, profile_label=profile_label)
        self._record_entry = record_form

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request names."""
        return self._session.profile_id

    async def declarations(self) -> M036ReadProjection:
        """Read every declaration the profile holds and refuse a result its receipt does not support."""
        return await self._read(M036ReadRequest(profile_id=self.profile_id, kind="list"), None)

    async def declaration(self, declaration_id: str) -> M036ReadProjection:
        """Read the one declaration ``declaration_id`` names and refuse a result that is not that record."""
        request = M036ReadRequest(profile_id=self.profile_id, kind="view", declaration_id=declaration_id)
        return await self._read(request, declaration_id)

    async def _read(self, request: M036ReadRequest, declaration_id: str | None) -> M036ReadProjection:
        def settle(
            result: M036ReadProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not _read_settled(request.profile_id, request.kind, declaration_id, result, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=M036_READ_OPERATION_DEFINITION_ID,
            result_type=M036ReadProjection,
            settle=settle,
            explain_failure=True,
        )

    def record_form(self, prefill: Mapping[str, object]) -> OperationRunScreen:
        """Return the served request form of the record, for this session, filled from ``prefill``."""
        self._session.require_binding()
        return OperationRunScreen(self._client, self._record_entry, initial=prefill)


def compose_runtime_censo_door(client: FrontendClient, *, profile_label: str) -> RuntimeCensoTuiDoorV1 | None:
    """Admit the destination when the runtime serves both operations it needs under this session.

    Each operation is described by the runtime under the client's live scope.
    A refused description, or one whose contract is not exactly the shape this
    door reads and submits, leaves the destination unavailable: ``None``.
    """
    if client.frontend is not OperationFrontendProjection.TUI:
        return None
    record_form: OperationCatalogueEntryV1 | None = None
    for definition_id, (request_type, result_type) in CENSO_OPERATION_SHAPES.items():
        try:
            description = client.describe(definition_id, deadline=time.monotonic() + _CONTRACT_SECONDS)
        except (FrontendRefusedError, RefusalError):
            return None
        if not censo_contract_matches(description.contract, definition_id):
            return None
        if definition_id == M036_RECORD_OPERATION_DEFINITION_ID:
            record_form = served_operation_entry(
                description.contract,
                description.request_json_schema,
                request_type=request_type,
                result_type=result_type,
            )
    if record_form is None:
        return None
    try:
        return RuntimeCensoTuiDoorV1(client, profile_label=profile_label, record_form=record_form)
    except (FrontendRefusedError, RefusalError):
        return None


__all__ = [
    "CENSO_OPERATION_SHAPES",
    "RuntimeCensoTuiDoorV1",
    "censo_contract_matches",
    "compose_runtime_censo_door",
]
