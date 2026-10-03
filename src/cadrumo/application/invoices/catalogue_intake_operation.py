"""Canonical wizard and bulk invoice import under exact-profile worker authority."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.aggregation import IntracomOperationType
from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.classification import InvoiceKind
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from .catalogue_intake_operation_ports import InvoiceIntakeCommitConflictError, InvoiceIntakePortsFactory
from .catalogue_intake_refusal import (
    INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
    InvoiceWizardFieldsValidationError,
    InvoiceWizardValidationRefusalProjection,
)
from .catalogue_read_projection import CatalogueInvoiceSnapshot
from .creation_wizard import create_invoice_via_wizard
from .source_resolver import iva_category_for_operation_type

INVOICE_IMPORT_OPERATION_DEFINITION_ID = "ledger.invoice.import"
INVOICE_WIZARD_OPERATION_DEFINITION_ID = "ledger.invoice.wizard"
_Text = Annotated[str, Field(max_length=16384)]


class InvoiceImportRequest(BaseModel):
    """Secure reference to the original file, checked before parsing or mapping."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind
    source_path: Annotated[str, Field(min_length=1, max_length=4096)]
    source_sha256: Hex64Str
    country: _Text | None = None

    @model_validator(mode="after")
    def _absolute_reference(self) -> Self:
        if not Path(self.source_path).is_absolute():
            raise ValueError("invoice import source must be an absolute reference")
        return self


class InvoiceWizardRequest(BaseModel):
    """Original raw fields; the owning wizard accumulates all grammar refusals."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    kind: InvoiceKind
    counterparty_nif: _Text
    counterparty_name: _Text
    invoice_number: _Text
    invoice_date: _Text
    taxable_base: _Text
    iva_rate: _Text | None
    currency: _Text
    country_code: _Text
    operation_date: _Text | None = None
    notes: _Text = ""
    iva_category: _Text | None = None
    operation_type: IntracomOperationType | None = None
    retention_rate: _Text | None = None
    retention_amount: _Text | None = None
    invoice_class: _Text | None = None
    series: _Text | None = None
    rectifies_invoice_number: _Text | None = None
    recargo_amount: _Text | None = None


class InvoiceImportRowFailure(BaseModel):
    """Every canonical row refusal, retaining its original attribution."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    row_number: Annotated[int, Field(ge=1)]
    field: _Text
    reason: _Text


class InvoiceImportProjection(BaseModel):
    """The whole current import outcome and human mapping disclosures."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    rows: Annotated[int, Field(ge=0)]
    created: Annotated[int, Field(ge=0)]
    skipped_duplicate: Annotated[int, Field(ge=0)]
    refused: tuple[InvoiceImportRowFailure, ...]
    created_invoice_ids: tuple[Hex64Str, ...]
    unmapped_column_headers: tuple[_Text, ...]
    mapping_reasons: tuple[_Text, ...]

    @model_validator(mode="after")
    def _complete_rows(self) -> Self:
        if (
            self.rows != self.created + self.skipped_duplicate + len(self.refused)
            or self.created != len(self.created_invoice_ids)
            or len(set(self.created_invoice_ids)) != self.created
        ):
            raise ValueError("invoice import outcome does not account for every row")
        return self


class InvoiceWizardProjection(BaseModel):
    """Complete canonical invoice readback and guarded no-op notice fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    invoice: CatalogueInvoiceSnapshot
    already_existed: bool
    euro_value_pending: bool

    @model_validator(mode="after")
    def _owning_profile(self) -> Self:
        if str(self.invoice.bucket_id) != str(self.profile_id):
            raise ValueError("wizard invoice belongs to another profile")
        return self


class InvoiceWizardOutcome(BaseModel):
    """Closed success or ordered canonical field refusal for one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    outcome: Literal["succeeded", "refused"]
    result: InvoiceWizardProjection | None = None
    refusal: InvoiceWizardValidationRefusalProjection | None = None

    @model_validator(mode="after")
    def _complete_owning_outcome(self) -> Self:
        if self.outcome == "succeeded":
            if self.result is None or self.refusal is not None or self.result.profile_id != self.profile_id:
                raise ValueError("wizard success requires its owning result")
        elif self.refusal is None or self.result is not None or self.refusal.profile_id != self.profile_id:
            raise ValueError("wizard refusal requires its owning field errors")
        return self


class InvoiceIntakeExecutionResult(BaseModel):
    """Private outcome correlated with the operation's actual mutation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    projection: InvoiceImportProjection | InvoiceWizardOutcome
    effect: Literal["none", "updated", "partial"]


_REQUESTS = {
    INVOICE_IMPORT_OPERATION_DEFINITION_ID: InvoiceImportRequest,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID: InvoiceWizardRequest,
}
_PROJECTIONS = {
    INVOICE_IMPORT_OPERATION_DEFINITION_ID: InvoiceImportProjection,
    INVOICE_WIZARD_OPERATION_DEFINITION_ID: InvoiceWizardOutcome,
}


def project_invoice_intake_result(
    value: BaseModel, receipt: OperationTerminalReceipt, /
) -> InvoiceImportProjection | InvoiceWizardOutcome:
    """Release complete facts only with matching terminal effect and authority."""
    if type(value) is not InvoiceIntakeExecutionResult or not isinstance(value, InvoiceIntakeExecutionResult):
        raise ValueError("invalid invoice intake result")
    private = InvoiceIntakeExecutionResult.model_validate(value.model_dump(mode="python"), strict=True)
    projection = private.projection
    if (
        type(projection) is not _PROJECTIONS.get(receipt.identity.definition_id)
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.effect.value != private.effect
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice intake outcome differs from its terminal receipt")
    if isinstance(projection, InvoiceWizardOutcome) and projection.outcome == "refused":
        if (
            receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.effect is not OperationEffect.NONE
            or receipt.refusal_ref != INVOICE_WIZARD_VALIDATION_REFUSAL_CODE
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
        ):
            raise ValueError("invoice intake refusal differs from its terminal receipt")
        return projection
    if (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
    ):
        raise ValueError("invoice intake outcome differs from its terminal receipt")
    if isinstance(projection, InvoiceWizardOutcome):
        if projection.result is None:
            raise ValueError("invoice intake success has no wizard result")
        expected = OperationEffect.NONE if projection.result.already_existed else OperationEffect.UPDATED
    else:
        expected = (
            OperationEffect.NONE
            if projection.created == 0
            else OperationEffect.PARTIAL
            if projection.refused
            else OperationEffect.UPDATED
        )
    if receipt.effect is not expected:
        raise ValueError("invoice intake row facts differ from its mutation effect")
    return projection


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> InvoiceImportRequest | InvoiceWizardRequest:
    payload = request.payload
    if type(payload) is not _REQUESTS.get(request.definition_id) or not isinstance(
        payload, (InvoiceImportRequest, InvoiceWizardRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    require_operation_profile(request, context, payload.profile_id)
    return payload


class InvoiceIntakeExecutor:
    """Keep canonical validation/FX outside the actual invoice-and-event fence."""

    def __init__(self, factory: InvoiceIntakePortsFactory) -> None:
        """Bind canonical capabilities for the worker's exact profile and pin."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> OperationExecutorResult:
        """Run canonical intake and retain a receipt-correlated private outcome."""
        payload = _require_profile(request, context)
        await context.events.phase(request.definition_id)
        await context.events.effect(OperationEffect.NONE)
        loop = asyncio.get_running_loop()
        committed = 0
        uncertain = False
        completed_effect: OperationEffect | None = None

        async def authorize_provider() -> None:
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)

        def admit_provider() -> None:
            asyncio.run_coroutine_threadsafe(authorize_provider(), loop).result()

        async def commit_prepared(save: Callable[[], None]) -> None:
            nonlocal committed, uncertain
            async with context.cancellation.irreversible_section():
                _require_profile(request, context)
                uncertain = True
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    await asyncio.to_thread(save)
                except InvoiceIntakeCommitConflictError:
                    uncertain = False
                    await context.events.effect(OperationEffect.PARTIAL if committed else OperationEffect.NONE)
                    raise
                committed += 1
                uncertain = False
                await context.events.effect(OperationEffect.PARTIAL)

        def commit(save: Callable[[], None]) -> None:
            asyncio.run_coroutine_threadsafe(commit_prepared(save), loop).result()

        def run_canonical() -> InvoiceImportProjection | InvoiceWizardProjection:
            _require_profile(request, context)
            operation = context.authority_operation
            ports = self._factory(
                profile_id=payload.profile_id, operation=operation, commit=commit, admit_provider=admit_provider
            )
            if ports.profile_id != payload.profile_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            with validating_governed_facts(operation):
                if isinstance(payload, InvoiceImportRequest):
                    source = read_bulk_invoice_import_source(
                        Path(payload.source_path), mapper=ports.mapper, expected_sha256=payload.source_sha256
                    )
                    outcome = import_invoices_from_rows(
                        source,
                        bucket_id=str(payload.profile_id),
                        kind=payload.kind,
                        declared_country=payload.country.strip().upper() if payload.country else None,
                        ports=ports.creation(),
                        operation=operation,
                    )
                    return InvoiceImportProjection(
                        profile_id=payload.profile_id,
                        rows=outcome.rows,
                        created=outcome.created,
                        skipped_duplicate=outcome.skipped_duplicate,
                        refused=tuple(
                            InvoiceImportRowFailure.model_validate(row.model_dump(mode="python"), strict=True)
                            for row in outcome.refused
                        ),
                        created_invoice_ids=outcome.created_invoice_ids,
                        unmapped_column_headers=tuple(column.header for column in source.resolution.unmapped_columns),
                        mapping_reasons=ports.mapping_reasons(),
                    )
                category = None
                if payload.iva_category is not None:
                    catalogue = resolve_iva_category_catalogue(authority=operation)
                    category = next(
                        (token for token in catalogue.all_categories if str(token) == payload.iva_category.strip()),
                        None,
                    )
                    if category is None:
                        raise InvoiceValidationError("IVA category is not declared by the active registry")
                category = category or iva_category_for_operation_type(payload.operation_type)
                outcome = create_invoice_via_wizard(
                    bucket_id=str(payload.profile_id),
                    kind=payload.kind,
                    counterparty_nif=payload.counterparty_nif,
                    counterparty_name=payload.counterparty_name,
                    invoice_number=payload.invoice_number,
                    invoice_date=payload.invoice_date,
                    taxable_base=payload.taxable_base,
                    iva_rate=payload.iva_rate,
                    currency=payload.currency,
                    country_code=payload.country_code,
                    operation_date=payload.operation_date,
                    notes=payload.notes,
                    iva_category=category,
                    operation_type=payload.operation_type,
                    retention_rate=payload.retention_rate,
                    retention_amount=payload.retention_amount,
                    invoice_class=payload.invoice_class,
                    series=payload.series,
                    rectifies_invoice_number=payload.rectifies_invoice_number,
                    recargo_amount=payload.recargo_amount,
                    ports=ports.creation(),
                    operation=operation,
                )
                return InvoiceWizardProjection(
                    profile_id=payload.profile_id,
                    invoice=CatalogueInvoiceSnapshot.from_invoice(outcome.invoice),
                    already_existed=outcome.already_existed,
                    euro_value_pending=outcome.invoice.euro_value_pending,
                )

        async def run() -> OperationExecutorResult:
            nonlocal completed_effect
            try:
                try:
                    projection = await asyncio.to_thread(run_canonical)
                except InvoiceWizardFieldsValidationError as error:
                    if type(error) is not InvoiceWizardFieldsValidationError or not isinstance(
                        payload, InvoiceWizardRequest
                    ):
                        raise
                    _require_profile(request, context)
                    if committed or uncertain:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
                    refusal = InvoiceWizardValidationRefusalProjection.from_error(error, profile_id=payload.profile_id)
                    outcome = InvoiceWizardOutcome(profile_id=payload.profile_id, outcome="refused", refusal=refusal)
                    private = InvoiceIntakeExecutionResult(projection=outcome, effect="none")
                    if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
                    completed_effect = OperationEffect.NONE
                    await context.events.effect(OperationEffect.NONE)
                    detail_ref = await context.operands.put(private, written_at=now())
                    return OperationRefusalEvidence(
                        refusal_code=INVOICE_WIZARD_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref
                    )
                _require_profile(request, context)
                expected_commits = (
                    projection.created
                    if isinstance(projection, InvoiceImportProjection)
                    else int(not projection.already_existed)
                )
                if committed != expected_commits:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                effect = (
                    OperationEffect.NONE
                    if committed == 0
                    else OperationEffect.PARTIAL
                    if isinstance(projection, InvoiceImportProjection) and projection.refused
                    else OperationEffect.UPDATED
                )
                completed_effect = effect
                public = (
                    InvoiceWizardOutcome(profile_id=projection.profile_id, outcome="succeeded", result=projection)
                    if isinstance(projection, InvoiceWizardProjection)
                    else projection
                )
                private = InvoiceIntakeExecutionResult(projection=public, effect=effect.value)
                if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                await context.events.effect(effect)
                return await context.operands.put(private, written_at=now())
            except BaseException:
                await context.events.effect(
                    OperationEffect.UNKNOWN
                    if uncertain
                    else completed_effect
                    if completed_effect is not None
                    else OperationEffect.PARTIAL
                    if committed
                    else OperationEffect.NONE
                )
                raise

        return await await_cancellation_complete(run(), task_name=request.definition_id)


def _definition(definition_id: str, factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    request_type = _REQUESTS[definition_id]
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=InvoiceIntakeExecutionResult,
        executor_factory=OperationExecutorFactory(
            request_type=request_type, executor_type=InvoiceIntakeExecutor, build=lambda: InvoiceIntakeExecutor(factory)
        ),
        phase_codes=(definition_id,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
        refusal_detail_codes=(
            frozenset({INVOICE_WIZARD_VALIDATION_REFUSAL_CODE})
            if definition_id == INVOICE_WIZARD_OPERATION_DEFINITION_ID
            else frozenset()
        ),
    )


def build_invoice_import_definition(factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    """Enroll the existing human invoice-book import."""
    return _definition(INVOICE_IMPORT_OPERATION_DEFINITION_ID, factory)


def build_invoice_wizard_definition(factory: InvoiceIntakePortsFactory) -> OperationDefinition:
    """Enroll the existing all-fields human wizard without substituting add."""
    return _definition(INVOICE_WIZARD_OPERATION_DEFINITION_ID, factory)


def resolve_invoice_intake_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """The existing catalogue reads require whole-profile rights and actual COMMIT."""
    if type(request.payload) is not _REQUESTS.get(request.definition_id) or not isinstance(
        request.payload, (InvoiceImportRequest, InvoiceWizardRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    resolved = resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())
    return replace(
        resolved,
        policy=OperationAccessPolicy.model_validate(
            {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
        ),
    )


def build_invoice_intake_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Compile both closed schemas and bind truthful receipt disclosure."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=_PROJECTIONS[definition.definition_id],
        result_projector=project_invoice_intake_result,
        access_resolver=resolve_invoice_intake_access,
    )


__all__ = [
    "INVOICE_IMPORT_OPERATION_DEFINITION_ID",
    "INVOICE_WIZARD_OPERATION_DEFINITION_ID",
    "InvoiceImportProjection",
    "InvoiceImportRequest",
    "InvoiceImportRowFailure",
    "InvoiceIntakeExecutionResult",
    "InvoiceIntakeExecutor",
    "InvoiceWizardOutcome",
    "InvoiceWizardProjection",
    "InvoiceWizardRequest",
    "build_invoice_import_definition",
    "build_invoice_intake_registration",
    "build_invoice_wizard_definition",
    "project_invoice_intake_result",
    "resolve_invoice_intake_access",
]
