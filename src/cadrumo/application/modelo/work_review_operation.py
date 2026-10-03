"""Registered exact-profile capture of the compact canonical work review."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.casilla_id import CasillaId
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.modelo_work_progress_state import ModeloWorkProgressState
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...core.operator_action_enums import OperatorActionAxis
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import LegalRefId, RevisionId, SourceRefId, VerificationExpectationId
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
)
from ...domain.modelos.work_unit import WorkUnit
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
    OperationAccessContext,
    ResolvedOperationAccess,
    bind_operation_access_profile,
    require_single_period_admission,
)
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.read_capture import capture_read_result
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .history_ports import ModeloHistoryPorts, ModeloHistoryPortsFactory
from .work_review import BlockerRef, ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review

MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID = "modelo.work.review"


class ModeloWorkReviewRequest(CredentialFreeOperationRequest):
    """Identify a work unit without placing its private metadata in the journal."""

    profile_id: UUID
    work_unit_id: WorkUnitId


class ModeloWorkReviewProgressSnapshot(BaseModel):
    """Schema-safe representation of canonical measured progress."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    state: ModeloWorkProgressState
    materialised_count: int | None = Field(default=None, ge=0)
    target_count: int | None = Field(default=None, gt=0)
    denominator_kind: Literal["calculation_completeness_manifest"] | None = None
    denominator_revision_id: RevisionId | None = None
    denominator_source_ref: SourceRefId | None = None

    @classmethod
    def from_progress(cls, progress: ModeloWorkProgress) -> Self:
        """Copy canonical progress into a schema-safe snapshot."""
        denominator = progress.denominator
        return cls(
            state=progress.state,
            materialised_count=progress.materialised_count,
            target_count=progress.target_count,
            denominator_kind=denominator.kind if denominator else None,
            denominator_revision_id=denominator.registry_revision_id if denominator else None,
            denominator_source_ref=denominator.source_ref if denominator else None,
        )

    def to_progress(self) -> ModeloWorkProgress:
        """Revalidate the complete canonical progress invariant."""
        from .work_review import ModeloWorkProgressDenominator

        fields = (self.denominator_kind, self.denominator_revision_id, self.denominator_source_ref)
        if any(value is not None for value in fields) and not all(value is not None for value in fields):
            raise ValueError("work review progress denominator is incomplete")
        denominator = None
        if (
            self.denominator_kind is not None
            and self.denominator_revision_id is not None
            and self.denominator_source_ref is not None
        ):
            denominator = ModeloWorkProgressDenominator(
                kind=self.denominator_kind,
                registry_revision_id=self.denominator_revision_id,
                source_ref=self.denominator_source_ref,
            )
        return ModeloWorkProgress(
            state=self.state,
            materialised_count=self.materialised_count,
            target_count=self.target_count,
            denominator=denominator,
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_progress()
        return self


class ModeloWorkReviewFact(BaseModel):
    """One tagged factual scalar in a schema-visible immutable sequence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: str = Field(min_length=1, max_length=128)
    kind: Literal["str", "int", "bool", "decimal", "none"]
    value: str | None = Field(max_length=4096)

    @classmethod
    def from_value(cls, key: str, value: str | int | bool | Decimal | None) -> Self:
        """Preserve the precise canonical scalar type in an explicit tag."""
        if value is None:
            return cls(key=key, kind="none", value=None)
        if isinstance(value, bool):
            return cls(key=key, kind="bool", value="true" if value else "false")
        if isinstance(value, int):
            return cls(key=key, kind="int", value=str(value))
        if isinstance(value, Decimal):
            if not value.is_finite():
                raise ValueError("review decimal fact must be finite")
            return cls(key=key, kind="decimal", value=str(value))
        return cls(key=key, kind="str", value=value)

    def to_value(self) -> str | int | bool | Decimal | None:
        """Decode one exact factual scalar without a generic object payload."""
        if self.kind == "none":
            return None
        if self.value is None:
            raise ValueError("review fact value is missing")
        if self.kind == "bool":
            return self.value == "true"
        if self.kind == "int":
            return int(self.value)
        if self.kind == "decimal":
            return Decimal(self.value)
        return self.value

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if self.kind == "none":
            if self.value is not None:
                raise ValueError("none review fact must have no value")
        elif self.value is None:
            raise ValueError("review fact value is required")
        elif self.kind == "bool" and self.value not in {"true", "false"}:
            raise ValueError("review boolean fact must be canonical")
        elif self.kind == "int" and str(int(self.value)) != self.value:
            raise ValueError("review integer fact must be canonical")
        elif self.kind == "decimal":
            decimal = Decimal(self.value)
            if not decimal.is_finite() or str(decimal) != self.value:
                raise ValueError("review decimal fact must be finite and canonical")
        return self


class ModeloWorkReviewFindingSnapshot(BaseModel):
    """Validated locale-neutral finding with bounded factual values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    message_locale_key: str = Field(min_length=1, max_length=200)
    message_facts: tuple[ModeloWorkReviewFact, ...] = ()
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = ()

    @classmethod
    def from_finding(cls, finding: ModeloVerificationFinding) -> Self:
        """Copy a domain finding without its custom serializer."""
        return cls.model_validate(
            finding.model_dump(mode="python")
            | {
                "message_facts": tuple(
                    ModeloWorkReviewFact.from_value(key, value) for key, value in finding.message_facts.items()
                )
            }
        )

    def to_finding(self) -> ModeloVerificationFinding:
        """Revalidate the finding's canonical locale and factual rules."""
        if len({fact.key for fact in self.message_facts}) != len(self.message_facts):
            raise ValueError("work review finding repeats a fact key")
        return ModeloVerificationFinding.model_validate(
            self.model_dump(mode="python")
            | {"message_facts": {fact.key: fact.to_value() for fact in self.message_facts}}
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_finding()
        return self


class ModeloWorkReviewBlockerSnapshot(BaseModel):
    """Canonical blocker code and factual tokens, without review casilla values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    axis: OperatorActionAxis
    native_code: str = Field(min_length=1, max_length=200)
    facts: tuple[ModeloWorkReviewFact, ...] = ()

    @classmethod
    def from_blocker(cls, blocker: BlockerRef) -> Self:
        """Copy one canonical blocker and its typed facts."""
        return cls.model_validate(
            blocker.model_dump(mode="python")
            | {"facts": tuple(ModeloWorkReviewFact.from_value(key, value) for key, value in blocker.facts.items())}
        )

    def to_blocker(self) -> BlockerRef:
        """Revalidate the canonical blocker."""
        if len({fact.key for fact in self.facts}) != len(self.facts):
            raise ValueError("work review blocker repeats a fact key")
        return BlockerRef.model_validate(
            self.model_dump(mode="python") | {"facts": {fact.key: fact.to_value() for fact in self.facts}}
        )

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        self.to_blocker()
        return self


class ModeloWorkReviewSnapshot(BaseModel):
    """The exact established compact CLI review, excluding detailed private rows."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    bucket_id: BucketId
    modelo: str = Field(min_length=3, max_length=3, pattern=r"^[0-9]{3}$")
    filing_year: FilingYear
    period: PublicPeriod
    registry_revision_id: RevisionId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId | None
    lifecycle_state: CalculationRevisionState | None
    verification_outcome: VerificationCompletenessStatus | None
    progress: ModeloWorkReviewProgressSnapshot
    casilla_count: int = Field(ge=0)
    findings: tuple[ModeloWorkReviewFindingSnapshot, ...]
    blockers: tuple[ModeloWorkReviewBlockerSnapshot, ...]
    row_source_fingerprint_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _canonical_coordinates(self) -> Self:
        if self.filing_year != self.period.filing_year:
            raise ValueError("work review year does not match its period")
        return self

    @classmethod
    def from_review(cls, review: ModeloWorkReview) -> Self:
        """Project only fields already emitted by the established CLI result."""
        return cls(
            bucket_id=review.bucket_id,
            modelo=str(review.modelo),
            filing_year=review.filing_year,
            period=PublicPeriod.from_period(review.period),
            registry_revision_id=review.registry_revision_id,
            work_unit_id=review.work_unit_id,
            calculation_revision_id=review.calculation_revision_id,
            lifecycle_state=review.lifecycle_state,
            verification_outcome=review.verification_outcome,
            progress=ModeloWorkReviewProgressSnapshot.from_progress(review.progress),
            casilla_count=len(review.casillas),
            findings=tuple(ModeloWorkReviewFindingSnapshot.from_finding(item) for item in review.findings),
            blockers=tuple(ModeloWorkReviewBlockerSnapshot.from_blocker(item) for item in review.blockers),
            row_source_fingerprint_count=len(review.row_source_fingerprints),
        )


class ModeloWorkReviewResult(BaseModel):
    """Encrypted worker operand, independently projected for frontend disclosure."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    review: ModeloWorkReviewSnapshot

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.review.bucket_id != str(self.profile_id):
            raise ValueError("work review belongs to another profile")
        return self


class ModeloWorkReviewProjection(BaseModel):
    """Closed public result; private operand fields cannot flow through inheritance."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    profile_id: UUID
    review: ModeloWorkReviewSnapshot

    @model_validator(mode="after")
    def _bound(self) -> Self:
        if self.review.bucket_id != str(self.profile_id):
            raise ValueError("work review belongs to another profile")
        return self


def project_modelo_work_review_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Explicitly disclose only the admitted review identity and compact fields."""
    if type(result) is not ModeloWorkReviewResult:
        raise ValueError("invalid work review result type")
    private = ModeloWorkReviewResult.model_validate(result.model_dump(mode="python"), strict=True)
    if (
        receipt.identity.definition_id != MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != private.review.work_unit_id
        or receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.effect is not OperationEffect.NONE
    ):
        raise ValueError("work review result does not match its request")
    return ModeloWorkReviewProjection(profile_id=private.profile_id, review=private.review)


def _bound_ports(
    payload: ModeloWorkReviewRequest, factory: ModeloHistoryPortsFactory, operation: PinnedAuthorityOperation
) -> ModeloHistoryPorts:
    ports = factory(bucket_id=str(payload.profile_id), operation=operation)
    if any(
        repo.bucket_id != str(payload.profile_id)
        for repo in (
            ports.work_unit_repository,
            ports.calculation_repository,
            ports.verification_repository,
            ports.filing_repository,
        )
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _read_unit(payload: ModeloWorkReviewRequest, ports: ModeloHistoryPorts) -> WorkUnit:
    unit = ports.work_unit_repository.load().get(payload.work_unit_id)
    if unit is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if unit.bucket_id != str(payload.profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return unit


class ModeloWorkReviewExecutor:
    """Build a canonical review inside the bound profile worker."""

    def __init__(self, factory: ModeloHistoryPortsFactory) -> None:
        """Retain composition's profile-bound repository factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloWorkReviewRequest], context: OperationExecutorContext
    ) -> str:
        """Build and encrypt the canonical review under the retained authority pin."""
        payload = request.payload
        if request.definition_id != MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id, expected_subject_ref=payload.work_unit_id)
        await context.events.phase(MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID)

        def read() -> ModeloWorkReviewResult:
            ports = _bound_ports(payload, self._factory, context.authority_operation)
            unit = _read_unit(payload, ports)
            review = build_modelo_work_review(
                unit.bucket_id,
                unit.modelo,
                unit.filing_year,
                unit.period,
                operation=context.authority_operation,
                work_unit_repository=ports.work_unit_repository,
                calculation_repository=ports.calculation_repository,
                verification_repository=ports.verification_repository,
            )
            snapshot = ModeloWorkReviewSnapshot.from_review(review)
            if snapshot.work_unit_id != unit.work_unit_id or snapshot.registry_revision_id != unit.revision_id:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            return ModeloWorkReviewResult(profile_id=payload.profile_id, review=snapshot)

        return await capture_read_result(context, read, task_name="modelo-work-review")


def build_modelo_work_review_definition(factory: ModeloHistoryPortsFactory) -> OperationDefinition:
    """Declare one recorded, encrypted exact-unit review read."""
    return OperationDefinition(
        definition_id=MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,
        request_type=ModeloWorkReviewRequest,
        result_type=ModeloWorkReviewResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloWorkReviewRequest,
            executor_type=ModeloWorkReviewExecutor,
            build=lambda: ModeloWorkReviewExecutor(factory),
        ),
        phase_codes=(MODELO_WORK_REVIEW_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_work_review_registration(
    definition: OperationDefinition, factory: ModeloHistoryPortsFactory
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the stored work period and explicit tax-value result disclosure."""

    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        payload = request.payload
        if request.definition_id != definition.definition_id or not isinstance(payload, ModeloWorkReviewRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if payload.profile_id != context.profile_id or request.subject_ref != payload.work_unit_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        admitted = context.admitted_request
        if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
            periods = require_single_period_admission(
                admitted, profile_id=context.profile_id, definition_id=request.definition_id
            )
        else:
            if context.authority_operation is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            ports = _bound_ports(payload, factory, context.authority_operation)
            periods = frozenset({_read_unit(payload, ports).period})
        return bind_operation_access_profile(
            context,
            LIFECYCLE_SELECTED_PERIODS_REGISTERED_RESULT_TAX_VALUES_ACCESS,
            profile_id=context.profile_id,
            definition_id=request.definition_id,
            periods=periods,
        )

    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=ModeloWorkReviewProjection,
        result_projector=project_modelo_work_review_result,
        access_resolver=resolve,
    )
