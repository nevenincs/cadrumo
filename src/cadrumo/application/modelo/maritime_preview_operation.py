"""Exact-profile operation custody for the canonical maritime exemption preview."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_id import CasillaId
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.errors.error_codes import get_registered_error_code
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import FormulaId, LegalRefId, SourceRefId
from ..operations.access_resolution import (
    OBSERVATION_DISCLOSING_ACTIONS,
    OPERATION_LIFECYCLE_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access,
    operation_disclosures,
)
from ..operations.capabilities import RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .maritime_preview import ModeloMaritimeExemptionPreview

MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID = "modelo.work.preview_maritime_exemption"
_Text = Annotated[str, Field(max_length=4096)]


class ModeloMaritimePreviewRequest(BaseModel):
    """Original optional inputs, held in encrypted operation operand custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    annual_salary: _Text | None = None
    qualifying_days: Annotated[int, Field(ge=1, le=365)] | None = None
    gross_navigation_income: _Text | None = None

    @model_validator(mode="after")
    def _amount_grammar(self) -> Self:
        for value in (self.annual_salary, self.gross_navigation_income):
            if value is not None and try_parse_canonical_decimal(value, max_fraction_digits=2) is None:
                raise ValueError("maritime preview amount must use the canonical euro grammar")
        return self


class MaritimePreviewObservation(BaseModel):
    """Complete canonical observation, retaining ordered legal and source grounding."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    value: _Text
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


class MaritimePreviewCasillaValue(BaseModel):
    """The existing derived flat view, encoded with a closed row schema."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    casilla_id: CasillaId
    value: _Text


class MaritimePreviewRetmarWarning(BaseModel):
    """Registered nonblocking warning and its sole canonical interpolation fact."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    code: Literal["ERROR_RENTA_PROFILE_COMPLETENESS_WARNING"]
    legal_ref: LegalRefId


class ModeloMaritimePreviewProjection(BaseModel):
    """Complete current human preview facts, without raw exception messages."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    worker_class: _Text | None
    vessel_flag: _Text | None
    waters_type: _Text | None
    vessel_registry: _Text | None
    retmar_registered: bool
    retmar_mandatory_filing: bool
    retmar_warning: MaritimePreviewRetmarWarning | None
    observations: Annotated[tuple[MaritimePreviewObservation, ...], Field(max_length=1024)]
    casilla_values: Annotated[tuple[MaritimePreviewCasillaValue, ...], Field(max_length=1024)]


class MaritimePreviewPort(Protocol):
    """Invoke the existing service with its exact retained authority operation."""

    def __call__(
        self, *, annual_salary: Decimal | None, qualifying_days: int | None, gross_navigation_income: Decimal | None
    ) -> ModeloMaritimeExemptionPreview:
        """Resolve the canonical preview from the supplied optional amounts."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloMaritimePreviewPorts:
    """The worker's immutable profile and authority identities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    preview: MaritimePreviewPort


class ModeloMaritimePreviewPortsFactory(Protocol):
    """Compose the service without reading another frontend's active profile."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloMaritimePreviewPorts:
        """Bind the service to the worker's profile and retained authority."""
        ...


def _projection(profile_id: UUID, preview: ModeloMaritimeExemptionPreview) -> ModeloMaritimePreviewProjection:
    warning = None
    error = preview.retmar_warning_error
    if error is not None:
        code = get_registered_error_code(error).code
        if code != "ERROR_RENTA_PROFILE_COMPLETENESS_WARNING" or error.context is None:
            raise ValueError("maritime preview warning lacks its canonical identity")
        warning = MaritimePreviewRetmarWarning.model_validate({"code": code, **error.context}, strict=True)
    facts = preview.facts
    return ModeloMaritimePreviewProjection(
        profile_id=profile_id,
        worker_class=facts.worker_class,
        vessel_flag=facts.vessel_flag,
        waters_type=facts.waters_type,
        vessel_registry=facts.vessel_registry,
        retmar_registered=facts.retmar_registered,
        retmar_mandatory_filing=preview.retmar_mandatory_filing,
        retmar_warning=warning,
        observations=tuple(
            MaritimePreviewObservation(
                casilla_id=row.casilla_id,
                value=str(row.value),
                formula_id=row.formula_id,
                legal_refs=tuple(row.legal_refs),
                source_refs=tuple(row.source_refs),
            )
            for row in preview.result.observations
        ),
        casilla_values=tuple(
            MaritimePreviewCasillaValue(casilla_id=key, value=str(value))
            for key, value in preview.result.casilla_values.items()
        ),
    )


def _request(request: OperationRequest[BaseModel], *, profile_id: UUID) -> ModeloMaritimePreviewRequest:
    payload = request.payload
    if (
        request.definition_id != MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID
        or type(payload) is not ModeloMaritimePreviewRequest
        or not isinstance(payload, ModeloMaritimePreviewRequest)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != profile_id or request.subject_ref != profile_operation_subject(str(profile_id)):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


class ModeloMaritimePreviewExecutor:
    """Delegate all legal resolution and RETMAR retry to the existing service."""

    def __init__(self, factory: ModeloMaritimePreviewPortsFactory) -> None:
        """Retain the factory for the authenticated worker's service ports."""
        self._factory = factory

    async def execute(self, request: OperationRequest[BaseModel], context: OperationExecutorContext) -> str:
        """Return a private read projection; this operation has no external effect."""
        if not isinstance(request.payload, ModeloMaritimePreviewRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = _request(request, profile_id=request.payload.profile_id)
        require_operation_profile(request, context, payload.profile_id)

        async def run() -> str:
            await context.events.phase(MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID)
            await context.events.effect(OperationEffect.NONE)
            operation = context.authority_operation
            ports = self._factory(profile_id=payload.profile_id, operation=operation)
            if ports.profile_id != payload.profile_id or ports.operation is not operation:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

            def preview() -> ModeloMaritimeExemptionPreview:
                if require_active_bucket_id() != str(payload.profile_id):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                return ports.preview(
                    annual_salary=try_parse_canonical_decimal(payload.annual_salary, max_fraction_digits=2)
                    if payload.annual_salary is not None
                    else None,
                    qualifying_days=payload.qualifying_days,
                    gross_navigation_income=try_parse_canonical_decimal(
                        payload.gross_navigation_income, max_fraction_digits=2
                    )
                    if payload.gross_navigation_income is not None
                    else None,
                )

            result = _projection(payload.profile_id, await asyncio.to_thread(preview))
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            if len(canonical_json_bytes(result.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(run(), task_name=MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID)


def build_modelo_maritime_preview_definition(factory: ModeloMaritimePreviewPortsFactory) -> OperationDefinition:
    """Enroll the existing private CLI calculation without additional frontends."""
    return OperationDefinition(
        definition_id=MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,
        request_type=ModeloMaritimePreviewRequest,
        result_type=ModeloMaritimePreviewProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloMaritimePreviewRequest,
            executor_type=ModeloMaritimePreviewExecutor,
            build=lambda: ModeloMaritimePreviewExecutor(factory),
        ),
        phase_codes=(MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI}),
    )


def resolve_modelo_maritime_preview_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Scope only period-independent profile facts and authorized tax-value output."""
    _request(request, profile_id=context.profile_id)
    if context.authority_operation is None or context.contract.definition_id != request.definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    admitted = context.admitted_request
    if admitted is not None and (
        admitted.profile_id != context.profile_id
        or admitted.definition_id != request.definition_id
        or admitted.action is not AccessAction.SUBMIT
        or admitted.periods
        or not admitted.period_independent
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    disclosures = operation_disclosures(
        context,
        observed_by=OBSERVATION_DISCLOSING_ACTIONS,
        result_categories=frozenset({DisclosureCategory.TAX_VALUES}),
        result_schema_id=None,
    )
    return bind_operation_access(
        context,
        profile_id=context.profile_id,
        definition_id=request.definition_id,
        actions=OPERATION_LIFECYCLE_ACTIONS,
        disclosures=disclosures,
        periods=frozenset(),
        period_independent=True,
        requires_all_periods=False,
        requires_human=False,
        provider=Availability.NOT_REQUIRED,
    )


def build_modelo_maritime_preview_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Compile the closed secure-request and complete human-preview schemas."""
    if (
        definition.definition_id != MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID
        or definition.request_type is not ModeloMaritimePreviewRequest
        or definition.result_type is not ModeloMaritimePreviewProjection
    ):
        raise ValueError("invalid maritime preview definition contract")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloMaritimePreviewProjection,
        access_resolver=resolve_modelo_maritime_preview_access,
    )


__all__ = [
    "MODELO_MARITIME_PREVIEW_OPERATION_DEFINITION_ID",
    "MaritimePreviewCasillaValue",
    "MaritimePreviewObservation",
    "MaritimePreviewPort",
    "MaritimePreviewRetmarWarning",
    "ModeloMaritimePreviewExecutor",
    "ModeloMaritimePreviewPorts",
    "ModeloMaritimePreviewPortsFactory",
    "ModeloMaritimePreviewProjection",
    "ModeloMaritimePreviewRequest",
    "build_modelo_maritime_preview_definition",
    "build_modelo_maritime_preview_registration",
    "resolve_modelo_maritime_preview_access",
]
