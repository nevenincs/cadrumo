"""Exact-profile registered operations for the capital-goods IVA register."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
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
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationResultProjector,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .declare_command import (
    BienInversionDeclarationCommand,
    BienInversionDeclarationResultV1,
    BienInversionDisposalIncompleteError,
    build_bien_inversion_record,
    persist_bien_inversion_record,
)
from .ports import BienesInversionIvaRegisterRepositoryFactory
from .service import BienesInversionRegisterService

BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID = "ledger.bienes_inversion.list"
BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID = "ledger.bienes_inversion.declare"

BIENES_INVERSION_VALIDATION_REFUSAL_CODE = "REFUSED_PROFILE_BIENES_INVERSION_VALIDATION"
BIENES_INVERSION_DUPLICATE_REFUSAL_CODE = BIENES_INVERSION_VALIDATION_REFUSAL_CODE

type BienesInversionOperationId = Literal["list", "declare"]
type BienesInversionRefusalReason = Literal["validation", "disposal_incomplete", "duplicate_identifier"]


class _ProfileRequest(BaseModel):
    """Common private exact-profile binding for register operations."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID


class BienesInversionListRequest(_ProfileRequest):
    """Read the complete capital-goods register for one immutable profile."""


class BienesInversionDeclareRequest(_ProfileRequest):
    """Declare one capital good using the existing operator-owned facts."""

    identifier: str = Field(min_length=1)
    description: str = Field(min_length=1)
    acquisition_year: int = Field(ge=1, le=2099)
    acquisition_ledger_id: str = Field(min_length=1, max_length=128)
    cuota_soportada: PublicDecimal
    prorrata_inicial_pct: PublicDecimal
    kind: str = Field(min_length=1)
    art108_elegible: bool = True
    prorrata_sector_id: str | None = Field(default=None, min_length=1, max_length=64)
    disposal_year: int | None = Field(default=None, ge=1, le=2099)
    disposal_regime: str | None = Field(default=None, min_length=1)


class BienInversionDisposalProjection(BaseModel):
    """Complete public disposal facts retained on the canonical record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    year: int
    regime: Annotated[str, Field(min_length=1, max_length=96)]


class BienInversionRecordProjection(BaseModel):
    """Untruncated CLI record projection, including its derived acquisition deduction."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    identifier: str
    description: str
    acquisition_year: int
    cuota_soportada: PublicDecimal
    prorrata_inicial_pct: PublicDecimal
    kind: Annotated[str, Field(min_length=1, max_length=96)]
    art108_elegible: bool
    acquisition_ledger_id: str
    prorrata_sector_id: str | None
    disposal: BienInversionDisposalProjection | None
    deduccion_efectuada: PublicDecimal
    schema_version: str

    @classmethod
    def from_record(cls, record: BienInversionIvaRecord) -> BienInversionRecordProjection:
        """Project every operator-visible register field without dropping identity."""
        disposal = record.disposal
        return cls(
            identifier=record.identifier,
            description=record.description,
            acquisition_year=record.acquisition_year,
            cuota_soportada=PublicDecimal(decimal=str(record.cuota_soportada)),
            prorrata_inicial_pct=PublicDecimal(decimal=str(record.prorrata_inicial_pct)),
            kind=record.kind.value,
            art108_elegible=record.art108_elegible,
            acquisition_ledger_id=record.acquisition_ledger_id,
            prorrata_sector_id=record.prorrata_sector_id,
            disposal=(
                BienInversionDisposalProjection(year=disposal.year, regime=disposal.regime.value)
                if disposal is not None
                else None
            ),
            deduccion_efectuada=PublicDecimal(decimal=str(record.deduccion_efectuada)),
            schema_version=record.schema_version,
        )


class BienesInversionRefusalProjection(BaseModel):
    """Safe, closed refusal context for a known pre-write declaration refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    code: Literal["REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",]
    reason: BienesInversionRefusalReason
    missing: Literal["year", "regime"] | None = None
    identifier: str | None = None


class BienesInversionOperationExecutionResult(BaseModel):
    """Private result held in operation operand custody until projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    operation_id: BienesInversionOperationId
    outcome: Literal["success", "refused"]
    profile_id: UUID
    register_snapshot: BienesInversionIvaRegister | None = None
    record: BienInversionIvaRecord | None = None
    count: int | None = None
    refusal: BienesInversionRefusalProjection | None = None

    @model_validator(mode="after")
    def _execution_arm_is_closed(self) -> BienesInversionOperationExecutionResult:
        if self.outcome == "refused":
            if (
                self.operation_id != "declare"
                or any(value is not None for value in (self.register_snapshot, self.record, self.count))
                or self.refusal is None
            ):
                raise ValueError("capital-goods refusal result has an incompatible payload")
            return self
        if self.refusal is not None:
            raise ValueError("capital-goods success result contains a refusal")
        if self.operation_id == "list":
            if self.register_snapshot is None or self.record is not None or self.count is not None:
                raise ValueError("capital-goods list result arm is incomplete")
        elif self.register_snapshot is None or self.record is None or self.count is None:
            raise ValueError("capital-goods declaration result arm is incomplete")
        return self


class BienesInversionListProjection(BaseModel):
    """Complete result of reading the profile's capital-goods register."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    rows: tuple[BienInversionRecordProjection, ...]


class BienesInversionDeclareProjection(BaseModel):
    """Successful declaration projection or its registered typed refusal."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["declared", "refused"]
    profile_id: UUID
    record: BienInversionRecordProjection | None = None
    count: int | None = None
    refusal: BienesInversionRefusalProjection | None = None

    @model_validator(mode="after")
    def _projection_arm_is_closed(self) -> BienesInversionDeclareProjection:
        if self.outcome == "refused":
            if self.record is not None or self.count is not None or self.refusal is None:
                raise ValueError("capital-goods refusal projection has an incompatible payload")
        elif self.record is None or self.count is None or self.refusal is not None:
            raise ValueError("capital-goods declaration projection is incomplete")
        return self


@dataclass(frozen=True, slots=True)
class _OperationShape:
    request_type: type[BaseModel]
    projection_type: type[BaseModel]
    refusal_codes: frozenset[str]


_SHAPES: dict[str, _OperationShape] = {
    BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=BienesInversionListRequest,
        projection_type=BienesInversionListProjection,
        refusal_codes=frozenset(),
    ),
    BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID: _OperationShape(
        request_type=BienesInversionDeclareRequest,
        projection_type=BienesInversionDeclareProjection,
        refusal_codes=frozenset({BIENES_INVERSION_VALIDATION_REFUSAL_CODE}),
    ),
}


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
        shape = _SHAPES.get(self._definition_id)
        if shape is None or type(request.payload) is not shape.request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        if not isinstance(payload, _ProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        profile_id = payload.profile_id
        profile = str(profile_id)
        if (
            request.definition_id != self._definition_id
            or request.subject_ref != profile_operation_subject(profile)
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != request.subject_ref
            or require_active_bucket_id() != profile
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        await context.events.phase(self._definition_id)

        if self._definition_id == BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID:

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

        if not isinstance(payload, BienesInversionDeclareRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        declare_request = payload
        try:
            with validating_governed_facts(context.authority_operation):
                kind = require_bien_inversion_kind(declare_request.kind)
                disposal_regime = (
                    require_bien_inversion_disposal_regime(declare_request.disposal_regime)
                    if declare_request.disposal_regime is not None
                    else None
                )
                command = BienInversionDeclarationCommand(
                    identifier=declare_request.identifier,
                    description=declare_request.description,
                    acquisition_year=declare_request.acquisition_year,
                    acquisition_ledger_id=declare_request.acquisition_ledger_id,
                    cuota_soportada=Decimal(declare_request.cuota_soportada.decimal),
                    prorrata_inicial_pct=Decimal(declare_request.prorrata_inicial_pct.decimal),
                    kind=kind,
                    art108_elegible=declare_request.art108_elegible,
                    prorrata_sector_id=declare_request.prorrata_sector_id,
                    disposal_year=declare_request.disposal_year,
                    disposal_regime=disposal_regime,
                )
                record = build_bien_inversion_record(command)
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
        except BienInversionValidationError:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                refusal=BienesInversionRefusalProjection(
                    code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
                    reason="validation",
                ),
            )
        except RegistryValidationError:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                refusal=BienesInversionRefusalProjection(
                    code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
                    reason="validation",
                ),
            )
        except ValidationError:
            return await self._store_refusal(
                context,
                profile_id=profile_id,
                refusal=BienesInversionRefusalProjection(
                    code=BIENES_INVERSION_VALIDATION_REFUSAL_CODE,
                    reason="validation",
                ),
            )

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


def _profile_from_receipt(receipt: OperationTerminalReceipt, *, definition_id: str) -> UUID:
    if receipt.identity.definition_id != definition_id:
        raise ValueError("capital-goods result definition differs from its terminal receipt")
    subject = receipt.identity.subject_ref
    try:
        profile_id = UUID(subject.removeprefix("profile:"))
    except ValueError:
        raise ValueError("capital-goods result has an invalid profile subject") from None
    if subject != profile_operation_subject(str(profile_id)):
        raise ValueError("capital-goods result has an invalid profile subject")
    return profile_id


def _execution_result(result: BaseModel) -> BienesInversionOperationExecutionResult:
    if type(result) is not BienesInversionOperationExecutionResult:
        raise ValueError("capital-goods execution result has an incompatible type")
    return BienesInversionOperationExecutionResult.model_validate(result.model_dump(mode="python"), strict=True)


def _validate_refusal(
    *,
    result: BienesInversionOperationExecutionResult,
    receipt: OperationTerminalReceipt,
    profile_id: UUID,
) -> BienesInversionRefusalProjection:
    refusal = result.refusal
    if (
        result.operation_id != "declare"
        or result.outcome != "refused"
        or result.profile_id != profile_id
        or refusal is None
        or receipt.condition is not OperationTerminalCondition.REFUSED
        or receipt.effect is not OperationEffect.NONE
        or receipt.refusal_ref != refusal.code
        or receipt.refusal_detail_ref is None
        or receipt.result_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
        or receipt.identity.definition_id != BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID
        or refusal.code not in _SHAPES[BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID].refusal_codes
    ):
        raise ValueError("capital-goods refusal detail contradicts its terminal receipt")
    return refusal


def project_bienes_inversion_list_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BienesInversionListProjection:
    """Release the complete profile register only against a read-only receipt."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID)
    register = private.register_snapshot
    if (
        private.operation_id != "list"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or register is None
        or private.record is not None
        or private.refusal is not None
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("capital-goods list result contradicts its terminal receipt")
    return BienesInversionListProjection(
        profile_id=profile_id,
        rows=tuple(BienInversionRecordProjection.from_record(row) for row in register.records),
    )


def project_bienes_inversion_declare_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BienesInversionDeclareProjection:
    """Release one complete new record or its typed pre-write refusal."""
    private = _execution_result(result)
    profile_id = _profile_from_receipt(receipt, definition_id=BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID)
    if private.outcome == "refused":
        refusal = _validate_refusal(result=private, receipt=receipt, profile_id=profile_id)
        return BienesInversionDeclareProjection(outcome="refused", profile_id=profile_id, refusal=refusal)
    record = private.record
    if (
        private.operation_id != "declare"
        or private.outcome != "success"
        or private.profile_id != profile_id
        or record is None
        or private.register_snapshot is None
        or private.count != len(private.register_snapshot.records)
        or not any(row.identifier == record.identifier and row == record for row in private.register_snapshot.records)
        or private.refusal is not None
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.UPDATED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("capital-goods declaration result contradicts its terminal receipt")
    return BienesInversionDeclareProjection(
        outcome="declared",
        profile_id=profile_id,
        record=BienInversionRecordProjection.from_record(record),
        count=len(private.register_snapshot.records),
    )


def resolve_bienes_inversion_operation_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind list/declaration to the exact profile and all-period singleton scope."""
    shape = _SHAPES.get(request.definition_id)
    payload = request.payload
    if shape is None or type(payload) is not shape.request_type or not isinstance(payload, _ProfileRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())
    if request.definition_id != BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}},
    )
    return replace(resolved, policy=policy)


def _definition(
    definition_id: str,
    request_type: type[BaseModel],
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    shape = _SHAPES[definition_id]
    if shape.request_type is not request_type:
        raise ValueError("capital-goods operation request type does not match its registration")
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=BienesInversionOperationExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type,
            executor_type=BienesInversionOperationExecutor,
            build=lambda: BienesInversionOperationExecutor(repository_factory, definition_id=definition_id),
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP},
        ),
        refusal_detail_codes=shape.refusal_codes,
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    projection_type: type[BaseModel],
    projector: OperationResultProjector,
) -> OperationPublicDefinitionRegistrationV1:
    shape = _SHAPES[definition.definition_id]
    if shape.request_type is not request_type or shape.projection_type is not projection_type:
        raise ValueError("capital-goods registration does not match its closed schema")
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=projection_type,
        ),
        access_resolver=resolve_bienes_inversion_operation_access,
        result_projector=projector,
    )


def build_bienes_inversion_list_definition(
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the all-profile capital-goods list definition."""
    return _definition(BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID, BienesInversionListRequest, repository_factory)


def build_bienes_inversion_declare_definition(
    repository_factory: BienesInversionIvaRegisterRepositoryFactory,
) -> OperationDefinition:
    """Build the guarded capital-good declaration definition."""
    return _definition(
        BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID,
        BienesInversionDeclareRequest,
        repository_factory,
    )


def build_bienes_inversion_list_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the complete list projection to its current disclosure guard."""
    return _registration(
        definition,
        request_type=BienesInversionListRequest,
        projection_type=BienesInversionListProjection,
        projector=project_bienes_inversion_list_result,
    )


def build_bienes_inversion_declare_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the declaration projection and typed refusal contract."""
    return _registration(
        definition,
        request_type=BienesInversionDeclareRequest,
        projection_type=BienesInversionDeclareProjection,
        projector=project_bienes_inversion_declare_result,
    )


__all__ = [
    "BIENES_INVERSION_DECLARE_OPERATION_DEFINITION_ID",
    "BIENES_INVERSION_DUPLICATE_REFUSAL_CODE",
    "BIENES_INVERSION_LIST_OPERATION_DEFINITION_ID",
    "BIENES_INVERSION_VALIDATION_REFUSAL_CODE",
    "BienesInversionDeclareProjection",
    "BienesInversionDeclareRequest",
    "BienesInversionListProjection",
    "BienesInversionListRequest",
    "BienesInversionOperationExecutionResult",
    "BienesInversionOperationExecutor",
    "BienesInversionRefusalProjection",
    "build_bienes_inversion_declare_definition",
    "build_bienes_inversion_declare_registration",
    "build_bienes_inversion_list_definition",
    "build_bienes_inversion_list_registration",
    "project_bienes_inversion_declare_result",
    "project_bienes_inversion_list_result",
    "resolve_bienes_inversion_operation_access",
]
