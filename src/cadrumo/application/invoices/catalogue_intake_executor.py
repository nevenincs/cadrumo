"""Canonical wizard and bulk invoice import under exact-profile worker authority."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ...domain.invoices.errors import InvoiceValidationError
from ...domain.iva.schema import IvaCategory
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_payload, require_operation_profile
from ..operations.refusal_evidence import OperationExecutorResult, OperationRefusalEvidence
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .bulk_import import import_invoices_from_rows, read_bulk_invoice_import_source
from .catalogue_intake_contracts import (
    INVOICE_INTAKE_REQUEST_TYPES,
    InvoiceImportProjection,
    InvoiceImportRequest,
    InvoiceImportRowFailure,
    InvoiceIntakeExecutionResult,
    InvoiceWizardOutcome,
    InvoiceWizardProjection,
    InvoiceWizardRequest,
)
from .catalogue_intake_operation_ports import (
    InvoiceIntakeCommitConflictError,
    InvoiceIntakePorts,
    InvoiceIntakePortsFactory,
)
from .catalogue_intake_refusal import (
    INVOICE_WIZARD_VALIDATION_REFUSAL_CODE,
    InvoiceWizardFieldsValidationError,
    InvoiceWizardValidationRefusalProjection,
)
from .catalogue_read_projection import CatalogueInvoiceSnapshot
from .creation_wizard import create_invoice_via_wizard
from .source_resolver import iva_category_for_operation_type


def _require_profile(
    request: OperationRequest[BaseModel], context: OperationExecutorContext
) -> InvoiceImportRequest | InvoiceWizardRequest:
    request_type = INVOICE_INTAKE_REQUEST_TYPES.get(request.definition_id)
    if request_type is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = require_access_request_payload(request, definition_id=request.definition_id, payload_type=request_type)
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
        run = _InvoiceIntakeRun(
            factory=self._factory,
            request=request,
            payload=payload,
            context=context,
        )
        return await await_cancellation_complete(_run_invoice_intake(run), task_name=request.definition_id)


class _InvoiceIntakeRun:
    def __init__(
        self,
        *,
        factory: InvoiceIntakePortsFactory,
        request: OperationRequest[BaseModel],
        payload: InvoiceImportRequest | InvoiceWizardRequest,
        context: OperationExecutorContext,
    ) -> None:
        self.factory = factory
        self.request = request
        self.payload = payload
        self.context = context
        self.loop = asyncio.get_running_loop()
        self.committed = 0
        self.uncertain = False
        self.completed_effect: OperationEffect | None = None

    async def authorize_provider(self) -> None:
        async with self.context.cancellation.irreversible_section():
            _require_profile(self.request, self.context)

    def admit_provider(self) -> None:
        asyncio.run_coroutine_threadsafe(self.authorize_provider(), self.loop).result()

    async def commit_prepared(self, save: Callable[[], None]) -> None:
        async with self.context.cancellation.irreversible_section():
            _require_profile(self.request, self.context)
            self.uncertain = True
            await self.context.events.effect(OperationEffect.UNKNOWN)
            try:
                await asyncio.to_thread(save)
            except InvoiceIntakeCommitConflictError:
                self.uncertain = False
                await self.context.events.effect(OperationEffect.PARTIAL if self.committed else OperationEffect.NONE)
                raise
            self.committed += 1
            self.uncertain = False
            await self.context.events.effect(OperationEffect.PARTIAL)

    def commit(self, save: Callable[[], None]) -> None:
        asyncio.run_coroutine_threadsafe(self.commit_prepared(save), self.loop).result()

    def run_canonical(self) -> InvoiceImportProjection | InvoiceWizardProjection:
        _require_profile(self.request, self.context)
        operation = self.context.authority_operation
        ports = self.factory(
            profile_id=self.payload.profile_id,
            operation=operation,
            commit=self.commit,
            admit_provider=self.admit_provider,
        )
        if ports.profile_id != self.payload.profile_id or ports.operation is not operation:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        with validating_governed_facts(operation):
            if isinstance(self.payload, InvoiceImportRequest):
                return self._capture_import(ports, operation)
            return self._capture_wizard(ports, operation)

    def _capture_import(
        self,
        ports: InvoiceIntakePorts,
        operation: PinnedAuthorityOperation,
    ) -> InvoiceImportProjection:
        if not isinstance(self.payload, InvoiceImportRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        source = read_bulk_invoice_import_source(
            Path(self.payload.source_path), mapper=ports.mapper, expected_sha256=self.payload.source_sha256
        )
        outcome = import_invoices_from_rows(
            source,
            bucket_id=str(self.payload.profile_id),
            kind=self.payload.kind,
            declared_country=self.payload.country.strip().upper() if self.payload.country else None,
            ports=ports.creation(),
            operation=operation,
        )
        return InvoiceImportProjection(
            profile_id=self.payload.profile_id,
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

    def _capture_wizard(
        self,
        ports: InvoiceIntakePorts,
        operation: PinnedAuthorityOperation,
    ) -> InvoiceWizardProjection:
        if not isinstance(self.payload, InvoiceWizardRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        category = _resolve_wizard_category(self.payload, operation)
        category = category or iva_category_for_operation_type(self.payload.operation_type)
        outcome = create_invoice_via_wizard(
            bucket_id=str(self.payload.profile_id),
            kind=self.payload.kind,
            counterparty_nif=self.payload.counterparty_nif,
            counterparty_name=self.payload.counterparty_name,
            invoice_number=self.payload.invoice_number,
            invoice_date=self.payload.invoice_date,
            taxable_base=self.payload.taxable_base,
            iva_rate=self.payload.iva_rate,
            currency=self.payload.currency,
            country_code=self.payload.country_code,
            operation_date=self.payload.operation_date,
            notes=self.payload.notes,
            iva_category=category,
            operation_type=self.payload.operation_type,
            retention_rate=self.payload.retention_rate,
            retention_amount=self.payload.retention_amount,
            invoice_class=self.payload.invoice_class,
            series=self.payload.series,
            rectifies_invoice_number=self.payload.rectifies_invoice_number,
            recargo_amount=self.payload.recargo_amount,
            ports=ports.creation(),
            operation=operation,
        )
        return InvoiceWizardProjection(
            profile_id=self.payload.profile_id,
            invoice=CatalogueInvoiceSnapshot.from_invoice(outcome.invoice),
            already_existed=outcome.already_existed,
            euro_value_pending=outcome.invoice.euro_value_pending,
        )


def _resolve_wizard_category(
    payload: InvoiceWizardRequest,
    operation: PinnedAuthorityOperation,
) -> IvaCategory | None:
    if payload.iva_category is None:
        return None
    catalogue = resolve_iva_category_catalogue(authority=operation)
    category = next(
        (token for token in catalogue.all_categories if str(token) == payload.iva_category.strip()),
        None,
    )
    if category is None:
        raise InvoiceValidationError("IVA category is not declared by the active registry")
    return category


async def _run_invoice_intake(run: _InvoiceIntakeRun) -> OperationExecutorResult:
    try:
        try:
            projection = await asyncio.to_thread(run.run_canonical)
        except InvoiceWizardFieldsValidationError as error:
            if type(error) is not InvoiceWizardFieldsValidationError or not isinstance(
                run.payload,
                InvoiceWizardRequest,
            ):
                raise
            return await _record_wizard_validation_refusal(run, run.payload, error)
        return await _publish_invoice_intake_success(run, projection)
    except BaseException:
        await run.context.events.effect(_invoice_intake_failure_effect(run))
        raise


async def _record_wizard_validation_refusal(
    run: _InvoiceIntakeRun,
    payload: InvoiceWizardRequest,
    error: InvoiceWizardFieldsValidationError,
) -> OperationRefusalEvidence:
    _require_profile(run.request, run.context)
    if run.committed or run.uncertain:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
    refusal = InvoiceWizardValidationRefusalProjection.from_error(error, profile_id=payload.profile_id)
    outcome = InvoiceWizardOutcome(profile_id=payload.profile_id, outcome="refused", refusal=refusal)
    private = InvoiceIntakeExecutionResult(projection=outcome, effect="none")
    if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from None
    run.completed_effect = OperationEffect.NONE
    await run.context.events.effect(OperationEffect.NONE)
    detail_ref = await run.context.operands.put(private, written_at=now())
    return OperationRefusalEvidence(refusal_code=INVOICE_WIZARD_VALIDATION_REFUSAL_CODE, detail_ref=detail_ref)


async def _publish_invoice_intake_success(
    run: _InvoiceIntakeRun,
    projection: InvoiceImportProjection | InvoiceWizardProjection,
) -> str:
    _require_profile(run.request, run.context)
    if run.committed != _expected_invoice_intake_commits(projection):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    effect = _invoice_intake_success_effect(run.committed, projection)
    run.completed_effect = effect
    public = (
        InvoiceWizardOutcome(profile_id=projection.profile_id, outcome="succeeded", result=projection)
        if isinstance(projection, InvoiceWizardProjection)
        else projection
    )
    private = InvoiceIntakeExecutionResult(projection=public, effect=effect.value)
    if len(canonical_json_bytes(private.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    await run.context.events.effect(effect)
    return await run.context.operands.put(private, written_at=now())


def _expected_invoice_intake_commits(
    projection: InvoiceImportProjection | InvoiceWizardProjection,
) -> int:
    if isinstance(projection, InvoiceImportProjection):
        return projection.created
    return int(not projection.already_existed)


def _invoice_intake_success_effect(
    committed: int,
    projection: InvoiceImportProjection | InvoiceWizardProjection,
) -> Literal[OperationEffect.NONE, OperationEffect.PARTIAL, OperationEffect.UPDATED]:
    if committed == 0:
        return OperationEffect.NONE
    if isinstance(projection, InvoiceImportProjection) and projection.refused:
        return OperationEffect.PARTIAL
    return OperationEffect.UPDATED


def _invoice_intake_failure_effect(run: _InvoiceIntakeRun) -> OperationEffect:
    if run.uncertain:
        return OperationEffect.UNKNOWN
    if run.completed_effect is not None:
        return run.completed_effect
    if run.committed:
        return OperationEffect.PARTIAL
    return OperationEffect.NONE


__all__ = ["InvoiceIntakeExecutor"]
