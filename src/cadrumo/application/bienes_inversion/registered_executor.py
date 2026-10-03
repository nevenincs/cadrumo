"""Profile-scoped executor for capital-goods register operations."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionRecordError,
    BienInversionValidationError,
)
from ...domain.calculations.registry.bienes_inversion_catalogue import (
    require_bien_inversion_disposal_regime,
    require_bien_inversion_kind,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .declare_command import (
    BienInversionDeclarationCommand,
    BienInversionDeclarationResultV1,
    BienInversionDisposalIncompleteError,
    build_bien_inversion_record,
    persist_bien_inversion_record,
)
from .ports import BienesInversionIvaRegisterRepositoryFactory
from .registered_contracts import (
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_DUPLICATE_REFUSAL_CODE,
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID,
    BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
)
from .registered_execution_result import BienesInversionOperationExecutionResult
from .registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
    BienesInversionProfileRequest,
)
from .registered_result_contracts import BienesInversionRefusalProjection
from .service import BienesInversionRegisterService


def _missing_disposal_part(error: BienInversionDisposalIncompleteError) -> Literal["year", "regime"]:
    if error.missing == "year":
        return "year"
    if error.missing == "regime":
        return "regime"
    raise RuntimeError("capital-goods disposal refusal named an unsupported missing field")


class BienesInversionOperationExecutor:
    """Run the canonical register service under exact-profile worker custody."""

    def __init__(
        self,
        repository_factory: BienesInversionIvaRegisterRepositoryFactory,
        *,
        definition_id: str,
    ) -> None:
        """Bind the repository capability and exact public operation ID."""
        self._repository_factory = repository_factory
        self._definition_id = definition_id

    def _service(self, profile_id: UUID) -> BienesInversionRegisterService:
        return BienesInversionRegisterService(repository=self._repository_factory(bucket_id=str(profile_id)))

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one read or declaration and retain its receipt-correlated outcome."""
        payload = self._validate_request(request, context)
        profile_id = payload.profile_id
        await context.events.phase(self._definition_id)

        if self._definition_id == BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID:
            return await self._read_register(context, profile_id)
        if not isinstance(payload, BienesInversionDeclareRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self._declare_record(context, profile_id, payload)

    def _validate_request(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> BienesInversionProfileRequest:
        if self._definition_id == BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID:
            request_type = BienesInversionListRequest
        elif self._definition_id == BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID:
            request_type = BienesInversionDeclareRequest
        else:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if type(request.payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        if not isinstance(payload, BienesInversionProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        profile_id = payload.profile_id
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, profile_id)
        return payload

    async def _read_register(self, context: OperationExecutorContext, profile_id: UUID) -> str:
        async def read() -> str:
            def work() -> BienesInversionIvaRegister:
                with validating_governed_facts(context.authority_operation):
                    return self._service(profile_id).list_all()

            register = await asyncio.to_thread(work)
            result = BienesInversionOperationExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=profile_id,
                register_snapshot=register,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="bienes-inversion-list")

    async def _declare_record(
        self,
        context: OperationExecutorContext,
        profile_id: UUID,
        request: BienesInversionDeclareRequest,
    ) -> str | OperationRefusalEvidence:
        prepared = await self._prepare_declaration(context, profile_id, request)
        if isinstance(prepared, OperationRefusalEvidence):
            return prepared
        command, record = prepared
        return await self._commit_declaration(context, profile_id, command, record)

    async def _prepare_declaration(
        self,
        context: OperationExecutorContext,
        profile_id: UUID,
        request: BienesInversionDeclareRequest,
    ) -> tuple[BienInversionDeclarationCommand, BienInversionIvaRecord] | OperationRefusalEvidence:
        try:
            return self._build_declaration(context, request)
        except BienInversionDisposalIncompleteError as exc:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                refusal=BienesInversionRefusalProjection(
                    code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
                    reason="disposal_incomplete",
                    missing=_missing_disposal_part(exc),
                ),
            )
        except (BienInversionValidationError, RegistryValidationError, ValidationError):
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                refusal=BienesInversionRefusalProjection(
                    code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
                    reason="validation",
                ),
            )

    def _build_declaration(
        self,
        context: OperationExecutorContext,
        request: BienesInversionDeclareRequest,
    ) -> tuple[BienInversionDeclarationCommand, BienInversionIvaRecord]:
        with validating_governed_facts(context.authority_operation):
            kind = require_bien_inversion_kind(request.kind)
            disposal_regime = (
                require_bien_inversion_disposal_regime(request.disposal_regime)
                if request.disposal_regime is not None
                else None
            )
            command = BienInversionDeclarationCommand(
                identifier=request.identifier,
                description=request.description,
                acquisition_year=request.acquisition_year,
                acquisition_ledger_id=request.acquisition_ledger_id,
                cuota_soportada=Decimal(request.cuota_soportada.decimal),
                prorrata_inicial_pct=Decimal(request.prorrata_inicial_pct.decimal),
                kind=kind,
                art108_elegible=request.art108_elegible,
                prorrata_sector_id=request.prorrata_sector_id,
                disposal_year=request.disposal_year,
                disposal_regime=disposal_regime,
            )
            return command, build_bien_inversion_record(command)

    async def _commit_declaration(
        self,
        context: OperationExecutorContext,
        profile_id: UUID,
        command: BienInversionDeclarationCommand,
        record: BienInversionIvaRecord,
    ) -> str | OperationRefusalEvidence:
        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def work() -> BienInversionDeclarationResultV1:
                    with validating_governed_facts(context.authority_operation):
                        return persist_bien_inversion_record(record, service=self._service(profile_id))

                try:
                    outcome = await asyncio.to_thread(work)
                except BienInversionRecordError as exc:
                    if exc.translated_message != (
                        "adapters.persistence.profile.bienes_inversion.errors.record_already_exists"
                    ):
                        raise
                    return await self._persist_refusal(
                        context,
                        profile_id=profile_id,
                        refusal=BienesInversionRefusalProjection(
                            code=BIENES_INVERSION_DUPLICATE_REFUSAL_CODE,
                            reason="duplicate_identifier",
                            identifier=command.identifier,
                        ),
                    )
                result = BienesInversionOperationExecutionResult(
                    operation_id="declare",
                    outcome="success",
                    profile_id=profile_id,
                    record=outcome.record,
                    register_snapshot=outcome.updated_register,
                    count=len(outcome.updated_register.records),
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="bienes-inversion-declare")

    async def _store_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        refusal: BienesInversionRefusalProjection,
    ) -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            return await self._persist_refusal(context, profile_id=profile_id, refusal=refusal)

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        refusal: BienesInversionRefusalProjection,
    ) -> OperationRefusalEvidence:
        result = BienesInversionOperationExecutionResult(
            operation_id="declare",
            outcome="refused",
            profile_id=profile_id,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)
