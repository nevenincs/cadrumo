"""Read the IVA balance and record about it through the authenticated TUI runtime session.

Each call is a separately recorded worker operation, run to its terminal state
and released as its registered typed result. The session and profile captured
when the workbench opened must still own the connection, and every result must
name that profile (and, for a read, the year asked about) before anything
reaches the screen. A refusal is the refusal the operation recorded, changed
nothing, and is raised as such with its served words. Any other failure of a
recording leaves its effect unknown and is raised unchanged, never settled here
as a refusal.
"""

from __future__ import annotations

import asyncio
import time

from pydantic import BaseModel, ValidationError

from cadrumo.application.modelo.iva_wallet_balance_operation import (
    MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletBalanceProjection,
    ModeloIvaWalletBalanceRequest,
)
from cadrumo.application.modelo.iva_wallet_correction_operation import (
    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
    ModeloIvaWalletCorrectionProjection,
    ModeloIvaWalletCorrectionRequest,
)
from cadrumo.application.modelo.iva_wallet_override_operation import (
    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
    ModeloIvaWalletOverrideProjection,
    ModeloIvaWalletOverrideRequest,
)
from cadrumo.application.modelo.iva_wallet_seed_operation import (
    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
    ModeloIvaWalletSeedProjection,
    ModeloIvaWalletSeedRequest,
)
from cadrumo.application.operations.public_period import PublicPeriod
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.operations import (
    OperationEffect,
    OperationFrontendProjection,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.tui.modelo.wallet import (
    IvaWalletActionKind,
    IvaWalletEntryV1,
    IvaWalletNotSentError,
    IvaWalletReceiptV1,
    IvaWalletRefusedError,
)
from cadrumo.entrypoints.tui.refusal.served import served_refusal
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection

SETTLEMENT_SECONDS = 120.0


class RuntimeModeloIvaWallet:
    """Bind the IVA balance operations to one TUI runtime session and its profile."""

    def __init__(self, client: FrontendClient) -> None:
        """Pin the TUI session and the profile this workbench shows."""
        if client.frontend is not OperationFrontendProjection.TUI:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._client = client
        self._profile_id, self._session_id = client.profile_id, client.session_id

    def _require_session(self) -> None:
        if self._client.session_id != self._session_id or self._client.profile_id != self._profile_id:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def read_balance(self, as_of_year: int) -> ModeloIvaWalletBalanceProjection:
        """Read the balance facts released for the profile as of one year; a refusal raises its served words."""
        self._require_session()
        try:
            payload = ModeloIvaWalletBalanceRequest(profile_id=self._profile_id, as_of_year=as_of_year)
        except ValidationError:
            raise IvaWalletNotSentError from None
        projection = asyncio.run(
            self._settle(
                MODELO_IVA_WALLET_BALANCE_OPERATION_DEFINITION_ID,
                payload,
                ModeloIvaWalletBalanceProjection,
                effect=OperationEffect.NONE,
            )
        )
        if projection.profile_id != self._profile_id or projection.as_of_year != as_of_year:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._require_session()
        return projection

    def record(self, entry: IvaWalletEntryV1) -> IvaWalletReceiptV1:
        """Send one recording and return its receipt; the request is validated by the application's own model."""
        self._require_session()
        try:
            period = PublicPeriod(filing_year=entry.filing_year, code=entry.period_code)
            definition_id, payload, result_type = self._request(entry, period)
        except ValidationError:
            raise IvaWalletNotSentError from None
        receipt = asyncio.run(self._settle(definition_id, payload, result_type, effect=OperationEffect.UPDATED))
        if (
            not isinstance(
                receipt,
                ModeloIvaWalletSeedProjection | ModeloIvaWalletCorrectionProjection | ModeloIvaWalletOverrideProjection,
            )
            or receipt.profile_id != self._profile_id
            or receipt.period != period
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._require_session()
        return receipt

    def _request(self, entry: IvaWalletEntryV1, period: PublicPeriod) -> tuple[str, BaseModel, type[BaseModel]]:
        profile_id = self._profile_id
        match entry.kind:
            case IvaWalletActionKind.SEED:
                return (
                    MODELO_IVA_WALLET_SEED_OPERATION_DEFINITION_ID,
                    ModeloIvaWalletSeedRequest(profile_id=profile_id, period=period, amount=entry.amount),
                    ModeloIvaWalletSeedProjection,
                )
            case IvaWalletActionKind.CORRECT:
                return (
                    MODELO_IVA_WALLET_CORRECTION_OPERATION_DEFINITION_ID,
                    ModeloIvaWalletCorrectionRequest(
                        profile_id=profile_id, period=period, amount=entry.amount, reason=entry.reason
                    ),
                    ModeloIvaWalletCorrectionProjection,
                )
            case IvaWalletActionKind.OVERRIDE:
                return (
                    MODELO_IVA_WALLET_OVERRIDE_OPERATION_DEFINITION_ID,
                    ModeloIvaWalletOverrideRequest(
                        profile_id=profile_id,
                        period=period,
                        amount=entry.amount,
                        reason=entry.reason,
                        evidence_locator=entry.evidence_locator,
                    ),
                    ModeloIvaWalletOverrideProjection,
                )

    async def _settle[ResultT: BaseModel](
        self, definition_id: str, payload: BaseModel, result_type: type[ResultT], *, effect: OperationEffect
    ) -> ResultT:
        subject_ref = profile_operation_subject(str(self._profile_id))
        deadline = time.monotonic() + SETTLEMENT_SECONDS
        try:
            controller = await OperationController.submit(
                self._client,
                definition_id=definition_id,
                subject_ref=subject_ref,
                payload=payload,
                deadline=deadline,
                expected_session_id=self._session_id,
            )
        except FrontendRefusedError as refused:
            # Refused before anything was recorded: nothing changed.
            raise IvaWalletRefusedError(served_refusal(None, refusal_code=refused.reason)) from None
        await controller.start()
        terminal = await await_terminal_projection(
            controller,
            definition_id=definition_id,
            subject_ref=subject_ref,
            request_schema=OperationSchemaIdentityV1.from_model(
                schema_id=f"{definition_id}.request", schema_version=1, model_type=type(payload)
            ),
            deadline=deadline,
        )
        if terminal.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
            if (
                terminal.terminal_condition is OperationTerminalCondition.REFUSED
                and terminal.effect is OperationEffect.NONE
            ):
                detail = await controller.settled_error_detail(terminal)
                raise IvaWalletRefusedError(served_refusal(detail, refusal_code=terminal.refusal_ref))
            raise FrontendRefusedError(
                terminal.refusal_ref or terminal.failure_error_code or "operation_not_successful"
            )
        if terminal.effect is not effect:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return await controller.read_settled_result(terminal, result_type, result_version=1)


__all__ = ["RuntimeModeloIvaWallet"]
