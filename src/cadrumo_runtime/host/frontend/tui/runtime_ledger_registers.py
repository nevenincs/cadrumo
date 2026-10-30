"""The prorrata, capital-goods and inventory registers through the installed TUI's retained runtime session.

Each door submits the exact request the screen reviewed to its own registered
operation for the admitted profile and session, then refuses any result its
settled terminal receipt does not support. A registered refusal arrives as the
operation's own typed refusal projection, correlated with its refused receipt.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo.application.bienes_inversion.registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
)
from cadrumo.application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from cadrumo.application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
)
from cadrumo.application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryListProjection,
    InventoryMovementAddProjection,
    InventoryValuationOperationProjection,
)
from cadrumo.application.inventory.registered_requests import (
    INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryLedgerChangeRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.prorrata_register.operation_requests import (
    PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID,
    PRORRATA_LIST_OPERATION_DEFINITION_ID,
    PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_OPERATION_DEFINITION_ID,
    PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID,
    PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID,
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataOperationId,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from cadrumo.application.prorrata_register.projection_contracts import (
    ProrrataListProjection,
    ProrrataMutationProjection,
)
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from cadrumo.domain.contribuyente.inventory.records import InventoryAcquisitionCost
from cadrumo.entrypoints.tui.ledger.registers_capital_goods import LedgerCapitalGoodsDoorV1, capital_goods_tool
from cadrumo.entrypoints.tui.ledger.registers_inventory import LedgerInventoryDoorV1, inventory_tool
from cadrumo.entrypoints.tui.ledger.registers_prorrata import (
    LedgerProrrataRegisterDoorV1,
    ProrrataMutationRequestV1,
    prorrata_register_tool,
)
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession

type _Correlation[ResultT] = Callable[[ResultT, OperationTerminalCondition, OperationPublicProjectionV1], bool]

_PRORRATA_MUTATIONS: dict[type[BaseModel], tuple[str, ProrrataOperationId]] = {
    ProrrataDeclareSectorRequest: (PRORRATA_DECLARE_SECTOR_OPERATION_DEFINITION_ID, "declare_sector"),
    ProrrataElectGeneralRequest: (PRORRATA_ELECT_GENERAL_OPERATION_DEFINITION_ID, "elect_general"),
    ProrrataElectEspecialRequest: (PRORRATA_ELECT_ESPECIAL_OPERATION_DEFINITION_ID, "elect_especial"),
    ProrrataRevokeEspecialRequest: (PRORRATA_REVOKE_ESPECIAL_OPERATION_DEFINITION_ID, "revoke_especial"),
    ProrrataSeedRequest: (PRORRATA_SEED_OPERATION_DEFINITION_ID, "seed"),
    ProrrataSeedSectorRequest: (PRORRATA_SEED_SECTOR_OPERATION_DEFINITION_ID, "seed_sector"),
    ProrrataSettleSectorRequest: (PRORRATA_SETTLE_SECTOR_OPERATION_DEFINITION_ID, "settle_sector"),
}


def _read_matches(condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1) -> bool:
    """A register read settles successfully, refuses nothing and changes nothing."""
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is OperationEffect.NONE
    )


def _outcome_matches(
    *,
    refusal_code: str | None,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
    success_effect: OperationEffect,
) -> bool:
    """A typed refusal needs its own refused, effect-free receipt; a success needs the effect it reports."""
    if refusal_code is not None:
        return (
            condition is OperationTerminalCondition.REFUSED
            and terminal.effect is OperationEffect.NONE
            and terminal.refusal_ref == refusal_code
        )
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.effect is success_effect
    )


class _RegisterSession:
    """Run register operations for the exact profile and session one door was built for."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        self._session = RuntimeProfileSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        return self._session.profile_id

    async def run[ResultT: BaseModel](
        self,
        request: BaseModel,
        *,
        definition_id: str,
        result_type: type[ResultT],
        matches: _Correlation[ResultT],
        refusal_detail: bool,
    ) -> ResultT:
        def settle(
            result: ResultT,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not matches(result, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=definition_id,
            result_type=result_type,
            settle=settle,
            allow_refusal_detail=refusal_detail,
            explain_failure=True,
        )


class RuntimeProrrataRegisterTuiDoorV1:
    """Submit prorrata register requests for the exact TUI profile and session this door was built for."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = _RegisterSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def read_register(self, request: ProrrataListRequest) -> ProrrataListProjection:
        """Read the complete register and refuse a result its receipt does not support."""
        return await self._session.run(
            request,
            definition_id=PRORRATA_LIST_OPERATION_DEFINITION_ID,
            result_type=ProrrataListProjection,
            matches=lambda result, condition, terminal: (
                result.profile_id == request.profile_id and _read_matches(condition, terminal)
            ),
            refusal_detail=False,
        )

    async def apply(self, request: ProrrataMutationRequestV1) -> ProrrataMutationProjection:
        """Submit one register change to its own operation and correlate the entry it names."""
        definition_id, operation_id = _PRORRATA_MUTATIONS[type(request)]

        def matches(
            result: ProrrataMutationProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            return (
                result.profile_id == request.profile_id
                and result.operation_id == operation_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.UPDATED,
                )
                and _prorrata_names_request(result, request)
            )

        return await self._session.run(
            request,
            definition_id=definition_id,
            result_type=ProrrataMutationProjection,
            matches=matches,
            refusal_detail=True,
        )


def _prorrata_names_request(result: ProrrataMutationProjection, request: ProrrataMutationRequestV1) -> bool:
    """A change answers the exercise and sector, or the sector definition, its request named."""
    if result.outcome == "refused":
        return True
    if isinstance(request, ProrrataDeclareSectorRequest):
        return result.sector_definition is not None and result.sector_definition.sector_id == request.sector_id
    entry = result.entry
    if entry is None or entry.ejercicio != request.ejercicio:
        return False
    if isinstance(request, ProrrataSeedRequest):
        return True
    return entry.sector_id == request.sector_id


class RuntimeCapitalGoodsTuiDoorV1:
    """Submit capital-goods register requests for the exact TUI profile and session this door was built for."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = _RegisterSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def read_register(self, request: BienesInversionListRequest) -> BienesInversionListProjection:
        """Read the complete register and refuse a result its receipt does not support."""
        return await self._session.run(
            request,
            definition_id=BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
            result_type=BienesInversionListProjection,
            matches=lambda result, condition, terminal: (
                result.profile_id == request.profile_id and _read_matches(condition, terminal)
            ),
            refusal_detail=False,
        )

    async def declare(self, request: BienesInversionDeclareRequest) -> BienesInversionDeclareProjection:
        """Declare one capital good and correlate the record it names."""

        def matches(
            result: BienesInversionDeclareProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            return (
                result.profile_id == request.profile_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.UPDATED,
                )
                and (result.record is None or result.record.identifier == request.identifier)
            )

        return await self._session.run(
            request,
            definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
            result_type=BienesInversionDeclareProjection,
            matches=matches,
            refusal_detail=True,
        )


def _ledger_scope_matches(
    ledger_actividad: str,
    ledger_year: int,
    request: InventoryCreateRequest
    | InventoryMovementAddRequest
    | InventoryValuationPreviewRequest
    | InventoryInspectRequest
    | InventoryLedgerChangeRequest,
) -> bool:
    return ledger_actividad == request.actividad_id and ledger_year == request.year


_LEDGER_CHANGE_DEFINITION_IDS: dict[type[InventoryLedgerChangeRequest], str] = {
    InventoryDescribeRequest: INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    InventoryCorrectRequest: INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    InventoryMovementCorrectRequest: INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    InventoryMovementReverseRequest: INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    InventoryRetireRequest: INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    InventoryRestoreRequest: INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
}


class RuntimeInventoryTuiDoorV1:
    """Submit inventory requests for the exact TUI profile and session this door was built for."""

    def __init__(self, client: FrontendClient, *, profile_label: str) -> None:
        """Pin the admitted profile and session for every request."""
        self._session = _RegisterSession(client, profile_label=profile_label)

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    async def read_register(self, request: InventoryListRequest) -> InventoryListProjection:
        """Read every activity inventory and refuse a result its receipt does not support."""
        return await self._session.run(
            request,
            definition_id=INVENTORY_LIST_OPERATION_DEFINITION_ID,
            result_type=InventoryListProjection,
            matches=lambda result, condition, terminal: (
                result.profile_id == request.profile_id and _read_matches(condition, terminal)
            ),
            refusal_detail=False,
        )

    async def inspect(self, request: InventoryInspectRequest) -> InventoryInspectProjection:
        """Read one inventory with its history and correlate the inventory it names."""

        def matches(
            result: InventoryInspectProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            ledger = result.ledger
            return (
                result.profile_id == request.profile_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.NONE,
                )
                and (ledger is None or _ledger_scope_matches(ledger.actividad_id, ledger.year, request))
            )

        return await self._session.run(
            request,
            definition_id=INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
            result_type=InventoryInspectProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def apply_change(self, request: InventoryLedgerChangeRequest) -> InventoryLedgerChangeProjection:
        """Run one edit, rectification, retirement or restoration and correlate its inventory."""

        def matches(
            result: InventoryLedgerChangeProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            ledger = result.ledger
            return (
                result.profile_id == request.profile_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.UPDATED if result.outcome == "applied" else OperationEffect.NONE,
                )
                and (ledger is None or _ledger_scope_matches(ledger.actividad_id, ledger.year, request))
            )

        return await self._session.run(
            request,
            definition_id=_LEDGER_CHANGE_DEFINITION_IDS[type(request)],
            result_type=InventoryLedgerChangeProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def create(self, request: InventoryCreateRequest) -> InventoryCreateProjection:
        """Create one activity inventory and correlate the inventory it names."""

        def matches(
            result: InventoryCreateProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            ledger = result.ledger
            return (
                result.profile_id == request.profile_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.UPDATED,
                )
                and (ledger is None or _ledger_scope_matches(ledger.actividad_id, ledger.year, request))
            )

        return await self._session.run(
            request,
            definition_id=INVENTORY_CREATE_OPERATION_DEFINITION_ID,
            result_type=InventoryCreateProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def add_movement(self, request: InventoryMovementAddRequest) -> InventoryMovementAddProjection:
        """Append one movement and correlate the inventory and movement it names."""

        def matches(
            result: InventoryMovementAddProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            ledger = result.ledger
            return (
                result.profile_id == request.profile_id
                and _outcome_matches(
                    refusal_code=None if refusal is None else refusal.code,
                    condition=condition,
                    terminal=terminal,
                    success_effect=OperationEffect.UPDATED,
                )
                and (
                    ledger is None
                    or (
                        _ledger_scope_matches(ledger.actividad_id, ledger.year, request)
                        and any(item.movement_id == request.movement_id for item in ledger.period_movements)
                    )
                )
            )

        return await self._session.run(
            request,
            definition_id=INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
            result_type=InventoryMovementAddProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def preview_valuation(
        self, request: InventoryValuationPreviewRequest
    ) -> InventoryValuationOperationProjection:
        """Run one recorded valuation preview and correlate the inventory it names."""

        def matches(
            result: InventoryValuationOperationProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            preview = result.preview
            # The preview records an audit event, so a settled preview reports that effect.
            return _outcome_matches(
                refusal_code=None if refusal is None else refusal.code,
                condition=condition,
                terminal=terminal,
                success_effect=OperationEffect.UPDATED,
            ) and (
                preview is None
                or (
                    preview.profile_id == request.profile_id
                    and _ledger_scope_matches(preview.actividad_id, preview.year, request)
                )
            )

        return await self._session.run(
            request,
            definition_id=INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
            result_type=InventoryValuationOperationProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def record_closing_authority(
        self, request: InventoryClosingAuthorityRecordRequest
    ) -> InventoryClosingAuthorityOperationProjection:
        """Record one closing authority and correlate the inventory it names."""
        return await self._submit_closing(
            request, definition_id=INVENTORY_CLOSING_AUTHORITY_RECORD_OPERATION_DEFINITION_ID
        )

    async def record_closing_value(
        self, request: InventoryClosingValueRecordRequest
    ) -> InventoryClosingAuthorityOperationProjection:
        """Record one closing value from plain facts and correlate the inventory it names."""
        return await self._submit_closing(request, definition_id=INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID)

    async def _submit_closing(
        self,
        request: InventoryClosingAuthorityRecordRequest | InventoryClosingValueRecordRequest,
        *,
        definition_id: str,
    ) -> InventoryClosingAuthorityOperationProjection:
        def matches(
            result: InventoryClosingAuthorityOperationProjection,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
        ) -> bool:
            refusal = result.refusal
            record = result.record
            # Recording the same authority again changes nothing, and its receipt says so.
            effect = OperationEffect.UPDATED if record is not None and record.changed else OperationEffect.NONE
            return _outcome_matches(
                refusal_code=None if refusal is None else refusal.code,
                condition=condition,
                terminal=terminal,
                success_effect=effect,
            ) and (
                record is None
                or (
                    record.profile_id == request.profile_id
                    and record.actividad_id == request.actividad_id
                    and record.year == request.year
                )
            )

        return await self._session.run(
            request,
            definition_id=definition_id,
            result_type=InventoryClosingAuthorityOperationProjection,
            matches=matches,
            refusal_detail=True,
        )

    async def read_acquisition_cost(self, path: str) -> InventoryAcquisitionCostRequest:
        """Read one typed purchase-cost file off the event loop and validate it as the command line does."""
        return await asyncio.to_thread(_read_acquisition_cost, path)

    async def read_closing_value_facts(self, path: str) -> InventoryClosingValueFactsInput:
        """Read one typed file of closing-value facts off the event loop and validate it as the command line does."""
        return await asyncio.to_thread(_read_closing_value_facts, path)

    async def read_closing_authority(self, path: str) -> InventoryClosingAuthorityRecordInput:
        """Read one typed closing-authority file off the event loop and validate it as the command line does."""
        return await asyncio.to_thread(_read_closing_authority, path)


def _read_typed_file[ModelT: BaseModel](path: str, model: type[ModelT]) -> ModelT:
    """Validate one operator-named JSON file against its canonical model; its content is never echoed."""
    try:
        return model.model_validate_json(Path(path).expanduser().read_text(encoding=UTF_8_ENCODING))
    except OSError:
        raise ValueError(tr("tui.ledger.registers.inventory.source_unreadable", path=path)) from None
    except ValidationError as error:
        raise ValueError(
            tr("tui.ledger.registers.inventory.source_invalid", path=path, count=error.error_count())
        ) from None


def _read_closing_value_facts(path: str) -> InventoryClosingValueFactsInput:
    return _read_typed_file(path, InventoryClosingValueFactsInput)


def _read_acquisition_cost(path: str) -> InventoryAcquisitionCostRequest:
    return InventoryAcquisitionCostRequest.from_domain(_read_typed_file(path, InventoryAcquisitionCost))


def _read_closing_authority(path: str) -> InventoryClosingAuthorityRecordInput:
    return InventoryClosingAuthorityRecordInput.from_domain(_read_typed_file(path, InventoryClosingAuthorityRecord))


def compose_registers_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """Offer the prorrata, capital-goods and inventory registers, each bound to the workbench's session."""
    prorrata: LedgerProrrataRegisterDoorV1 = RuntimeProrrataRegisterTuiDoorV1(client, profile_label=profile_label)
    capital_goods: LedgerCapitalGoodsDoorV1 = RuntimeCapitalGoodsTuiDoorV1(client, profile_label=profile_label)
    inventory: LedgerInventoryDoorV1 = RuntimeInventoryTuiDoorV1(client, profile_label=profile_label)
    return (prorrata_register_tool(prorrata), capital_goods_tool(capital_goods), inventory_tool(inventory))


__all__ = [
    "RuntimeCapitalGoodsTuiDoorV1",
    "RuntimeInventoryTuiDoorV1",
    "RuntimeProrrataRegisterTuiDoorV1",
    "compose_registers_tools",
]
