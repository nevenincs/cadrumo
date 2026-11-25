"""The related-party operations destination's operations through the installed TUI's retained runtime session.

The destination is admitted only when the runtime describes every one of its
operations under this session with the exact request and result schemas this
door reads and submits. Each change's form is built from the request schema
and contract the runtime served, never from a schema this process composes.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.m232_related_party.contracts import M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID
from cadrumo.application.m232_related_party.requests import (
    Modelo232NoneStateRequest,
    Modelo232NoneWithdrawRequest,
    Modelo232OperationStateRequest,
    Modelo232OperationWithdrawRequest,
    Modelo232RelatedPartyListRequest,
    Modelo232TurnoverStateRequest,
    Modelo232TurnoverWithdrawRequest,
)
from cadrumo.application.m232_related_party.results import (
    Modelo232RelatedPartyListProjection,
    Modelo232RelatedPartyMutationProjection,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.registry import OperationPublicDefinitionContractV1
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.operations import OperationEffect, OperationFrontendProjection, OperationTerminalCondition
from cadrumo.entrypoints.tui.operaciones_vinculadas.screen import OperacionesVinculadasMutation
from cadrumo.entrypoints.tui.operations.catalogue import OperationCatalogueEntryV1, served_operation_entry
from cadrumo.entrypoints.tui.operations.run_screen import OperationRunScreen
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .operations.runtime_profile_session import RuntimeProfileSession

_CONTRACT_SECONDS: Final = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS

OPERACIONES_VINCULADAS_OPERATION_SHAPES: Final[Mapping[str, tuple[type[BaseModel], type[BaseModel]]]] = {
    M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID: (
        Modelo232RelatedPartyListRequest,
        Modelo232RelatedPartyListProjection,
    ),
    OperacionesVinculadasMutation.STATE_OPERATION.value: (
        Modelo232OperationStateRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
    OperacionesVinculadasMutation.WITHDRAW_OPERATION.value: (
        Modelo232OperationWithdrawRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
    OperacionesVinculadasMutation.STATE_NONE.value: (
        Modelo232NoneStateRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
    OperacionesVinculadasMutation.WITHDRAW_NONE.value: (
        Modelo232NoneWithdrawRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
    OperacionesVinculadasMutation.STATE_TURNOVER.value: (
        Modelo232TurnoverStateRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
    OperacionesVinculadasMutation.WITHDRAW_TURNOVER.value: (
        Modelo232TurnoverWithdrawRequest,
        Modelo232RelatedPartyMutationProjection,
    ),
}
"""Every operation the destination needs: its request model and the public result it reads."""


def _schema(definition_id: str, kind: str, model_type: type[BaseModel]) -> OperationSchemaIdentityV1:
    return OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.{kind}", schema_version=1, model_type=model_type
    )


def operaciones_vinculadas_contract_matches(contract: OperationPublicDefinitionContractV1, definition_id: str) -> bool:
    """Whether ``contract`` is exactly the operation this door submits and reads under ``definition_id``."""
    request_type, result_type = OPERACIONES_VINCULADAS_OPERATION_SHAPES[definition_id]
    return (
        contract.definition_id == definition_id
        and contract.request_schema == _schema(definition_id, "request", request_type)
        and contract.result_schema == _schema(definition_id, "result", result_type)
    )


def _read_settled(
    profile_id: UUID,
    ejercicio: int,
    result: Modelo232RelatedPartyListProjection,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """Whether a listing answers exactly the profile and ejercicio asked, under a read-only receipt."""
    return (
        result.profile_id == profile_id
        and result.ejercicio == ejercicio
        and condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is OperationEffect.NONE
    )


class RuntimeOperacionesVinculadasTuiDoorV1:
    """Read and change one admitted profile's Modelo 232 related-party records through its pinned session."""

    def __init__(
        self,
        client: FrontendClient,
        *,
        profile_label: str,
        forms: Mapping[OperacionesVinculadasMutation, OperationCatalogueEntryV1],
    ) -> None:
        """Pin the admitted profile and session, and the served form of every change."""
        if frozenset(forms) != frozenset(OperacionesVinculadasMutation):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._session = RuntimeProfileSession(client, profile_label=profile_label)
        self._forms = dict(forms)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request names."""
        return self._session.profile_id

    async def year(self, ejercicio: int) -> Modelo232RelatedPartyListProjection:
        """Read the listing of ``ejercicio`` and refuse a result its receipt does not support."""
        request = Modelo232RelatedPartyListRequest(profile_id=self.profile_id, ejercicio=ejercicio)

        def settle(
            result: Modelo232RelatedPartyListProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not _read_settled(request.profile_id, ejercicio, result, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=M232_RELATED_PARTY_LIST_OPERATION_DEFINITION_ID,
            result_type=Modelo232RelatedPartyListProjection,
            settle=settle,
            explain_failure=True,
        )

    def mutation_form(
        self, mutation: OperacionesVinculadasMutation, prefill: Mapping[str, object]
    ) -> OperationRunScreen:
        """Return the served request form of ``mutation`` for this session, filled from ``prefill``."""
        self._session.require_binding()
        return OperationRunScreen(self._client, self._forms[mutation], initial=prefill)


def compose_runtime_operaciones_vinculadas_door(
    client: FrontendClient, *, profile_label: str
) -> RuntimeOperacionesVinculadasTuiDoorV1 | None:
    """Admit the destination when the runtime serves every operation it needs under this session.

    Each operation is described by the runtime under the client's live scope.
    A refused description, or one whose contract is not exactly the shape this
    door reads and submits, leaves the destination unavailable: ``None``.
    """
    if client.frontend is not OperationFrontendProjection.TUI:
        return None
    forms: dict[OperacionesVinculadasMutation, OperationCatalogueEntryV1] = {}
    for definition_id, (request_type, result_type) in OPERACIONES_VINCULADAS_OPERATION_SHAPES.items():
        try:
            description = client.describe(definition_id, deadline=time.monotonic() + _CONTRACT_SECONDS)
        except (FrontendRefusedError, RefusalError):
            return None
        if not operaciones_vinculadas_contract_matches(description.contract, definition_id):
            return None
        if definition_id in OperacionesVinculadasMutation:
            forms[OperacionesVinculadasMutation(definition_id)] = served_operation_entry(
                description.contract,
                description.request_json_schema,
                request_type=request_type,
                result_type=result_type,
            )
    try:
        return RuntimeOperacionesVinculadasTuiDoorV1(client, profile_label=profile_label, forms=forms)
    except (FrontendRefusedError, RefusalError):
        return None


__all__ = [
    "OPERACIONES_VINCULADAS_OPERATION_SHAPES",
    "RuntimeOperacionesVinculadasTuiDoorV1",
    "compose_runtime_operaciones_vinculadas_door",
    "operaciones_vinculadas_contract_matches",
]
