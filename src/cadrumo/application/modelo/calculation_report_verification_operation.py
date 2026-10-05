"""Registered exact-profile verification of a local calculation summary PDF."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_resolution import (
    LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..runtime.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .calculation_report_verification import (
    CalculationSummaryCheckName,
    CalculationSummaryStoreContext,
    CalculationSummaryVerification,
    CalculationSummaryVerificationCheck,
    CalculationSummaryVerificationLayer,
    CalculationSummaryVerificationOutcome,
    CalculationSummaryVerificationReason,
    verify_calculation_summary,
)
from .calculation_summary_pdf_ports import CalculationSummaryPdfReader

MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID = "modelo.work.report_verify"


class ModeloCalculationReportVerificationRequest(BaseModel):
    """Bind the local source bytes and optional trusted key to one profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    source_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    source_sha256: Hex64Str
    trusted_public_key_hex: Hex64Str | None = None

    @model_validator(mode="after")
    def _absolute_source(self) -> Self:
        if not Path(self.source_path).is_absolute():
            raise ValueError("calculation summary source path must be absolute")
        return self


class ModeloCalculationReportVerificationCheck(BaseModel):
    """One complete canonical check with a bounded diagnostic detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    check: CalculationSummaryCheckName
    layer: CalculationSummaryVerificationLayer
    reason: CalculationSummaryVerificationReason | None = None
    detail: Annotated[str, Field(max_length=PROJECTION_DOCUMENT_MAX_BYTES)] | None = None


class ModeloCalculationReportVerificationResult(BaseModel):
    """Closed wire form of every canonical verification field."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: CalculationSummaryVerificationOutcome
    checks: Annotated[
        tuple[ModeloCalculationReportVerificationCheck, ...], Field(max_length=PROJECTION_DOCUMENT_MAX_BYTES)
    ]
    store_checked: bool
    signing_key_fingerprint: Hex64Str | None = None
    calculation_revision_id: Hex64Str | None = None
    report_sha256: Hex64Str | None = None
    statement_sha256: Hex64Str | None = None

    @classmethod
    def from_verification(cls, verification: CalculationSummaryVerification) -> Self:
        """Preserve the check sequence, absence, and all identifiers."""
        return cls(
            outcome=verification.outcome,
            checks=tuple(
                ModeloCalculationReportVerificationCheck(
                    check=row.check, layer=row.layer, reason=row.reason, detail=row.detail
                )
                for row in verification.checks
            ),
            store_checked=verification.store_checked,
            signing_key_fingerprint=verification.signing_key_fingerprint,
            calculation_revision_id=verification.calculation_revision_id,
            report_sha256=verification.report_sha256,
            statement_sha256=verification.statement_sha256,
        )

    def to_verification(self) -> CalculationSummaryVerification:
        """Restore the canonical verdict for the existing presentation boundary."""
        return CalculationSummaryVerification(
            outcome=self.outcome,
            checks=tuple(
                CalculationSummaryVerificationCheck(
                    check=row.check, layer=row.layer, reason=row.reason, detail=row.detail
                )
                for row in self.checks
            ),
            store_checked=self.store_checked,
            signing_key_fingerprint=self.signing_key_fingerprint,
            calculation_revision_id=self.calculation_revision_id,
            report_sha256=self.report_sha256,
            statement_sha256=self.statement_sha256,
        )


class ModeloCalculationReportVerificationProjection(BaseModel):
    """Encrypted result bound to the requested profile and exact PDF bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    profile_id: UUID
    source_sha256: Hex64Str
    verification: ModeloCalculationReportVerificationResult


@dataclass(frozen=True, slots=True)
class ModeloCalculationReportVerificationPorts:
    """The existing verifier's reader and exact-profile store context."""

    profile_id: UUID
    reader: CalculationSummaryPdfReader
    store: CalculationSummaryStoreContext


class ModeloCalculationReportVerificationPortsFactory(Protocol):
    """Compose verification reads under the worker's retained authority pin."""

    def __call__(
        self, *, profile_id: UUID, operation: PinnedAuthorityOperation
    ) -> ModeloCalculationReportVerificationPorts:
        """Return the ports for exactly the admitted profile."""
        ...


class ModeloCalculationReportVerificationExecutor:
    """Check source custody before reading the profile or invoking the verifier."""

    def __init__(
        self,
        factory: ModeloCalculationReportVerificationPortsFactory,
        *,
        source_reader: Callable[[Path], bytes],
    ) -> None:
        """Capture source reading and exact-profile composition capabilities."""
        self._factory = factory
        self._source_reader = source_reader

    async def execute(
        self,
        request: OperationRequest[ModeloCalculationReportVerificationRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Verify unchanged source bytes through the canonical application service."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID)

        def verify() -> ModeloCalculationReportVerificationProjection:
            try:
                source = self._source_reader(Path(payload.source_path))
            except OSError as error:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED) from error
            if sha256_hex(source) != payload.source_sha256:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            with validating_governed_facts(context.authority_operation):
                ports = self._factory(profile_id=payload.profile_id, operation=context.authority_operation)
                if (
                    ports.profile_id != payload.profile_id
                    or ports.store.active_bucket_id != profile_id
                    or ports.store.operation is not context.authority_operation
                ):
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                verification = verify_calculation_summary(
                    source,
                    reader=ports.reader,
                    trusted_public_key_hex=payload.trusted_public_key_hex,
                    store=ports.store,
                )
            return ModeloCalculationReportVerificationProjection(
                profile_id=payload.profile_id,
                source_sha256=payload.source_sha256,
                verification=ModeloCalculationReportVerificationResult.from_verification(verification),
            )

        async def capture() -> str:
            projection = await asyncio.to_thread(verify)
            if len(canonical_json_bytes(projection.model_dump(mode="json"))) > PROJECTION_DOCUMENT_MAX_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            reference = await context.operands.put(projection, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="modelo-calculation-report-verify")


def build_modelo_calculation_report_verify_definition(
    factory: ModeloCalculationReportVerificationPortsFactory,
    *,
    source_reader: Callable[[Path], bytes] = Path.read_bytes,
) -> OperationDefinition:
    """Declare a local-only verification with secure request and result custody."""
    return build_single_phase_definition(
        definition_id=MODELO_CALCULATION_REPORT_VERIFY_OPERATION_DEFINITION_ID,
        request_type=ModeloCalculationReportVerificationRequest,
        result_type=ModeloCalculationReportVerificationProjection,
        executor_type=ModeloCalculationReportVerificationExecutor,
        build=lambda: ModeloCalculationReportVerificationExecutor(factory, source_reader=source_reader),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_calculation_report_verify_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Require whole-profile read authority without reading the requested file."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        require_access_request_profile_payload(
            request,
            definition_id=definition.definition_id,
            payload_type=ModeloCalculationReportVerificationRequest,
            access_profile_id=context.profile_id,
        )
        if context.authority_operation is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return bind_operation_access_profile(
            context,
            LIFECYCLE_WHOLE_PROFILE_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=frozenset(),
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloCalculationReportVerificationProjection,
        access_resolver=resolve,
    )
