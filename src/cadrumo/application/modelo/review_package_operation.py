"""Registered profile-worker build of a local Modelo review package."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.filing_year import FilingYear
from ...core.identity.bucket import BucketId
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef
from ...domain.deadlines.models import TaxpayerProfile
from ...domain.transactions.own_accounts import OwnAccountId
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .export import ModeloExportCommand, ModeloExportResult, export_modelo_revision
from .export_ports import ModeloExportPortsFactory
from .review_package import (
    ReviewPackageActor,
    ReviewPackageBuildResult,
    ReviewPackageError,
    ReviewPackageManifest,
    build_review_package,
)
from .review_package_text import ReviewPackageNote
from .verification_projection import ModeloRegistrySnapshotCoordinates
from .verification_repository_ports import VerificationRepositoryBundleFactory

MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID = "modelo.review_package.build"


class ModeloReviewPackageBuildRequest(BaseModel):
    """Exact revision and operator output, stored by secure reference."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    output_path: Annotated[str, Field(min_length=1, max_length=4096, pattern=r"\S")]
    actor: ReviewPackageActor
    refund_election: RefundElection = RefundElection.COMPENSAR
    payment_election: PaymentElection = PaymentElection.INGRESO
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP
    charge_account_id: OwnAccountId | None = None
    refund_account_id: OwnAccountId | None = None
    notes: ReviewPackageNote = ""

    @model_validator(mode="after")
    def _absolute_output(self) -> Self:
        if not Path(self.output_path).is_absolute():
            raise ValueError("review package output path must be absolute")
        return self


class ModeloReviewPackageManifestPublic(BaseModel):
    """Complete package-info descriptor with a public period coordinate."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    package_info_version: int = Field(ge=1)
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    registry_snapshot_ref: ModeloRegistrySnapshotCoordinates
    modelo: str = Field(min_length=1, max_length=8)
    filing_year: FilingYear
    period: PublicPeriod
    revision_state: str = Field(min_length=1)
    has_ledger_evidence: bool
    built_at: datetime
    built_by: ReviewPackageActor
    notes: ReviewPackageNote

    @model_validator(mode="after")
    def _canonical_manifest(self) -> Self:
        self.to_manifest()
        return self

    @classmethod
    def from_manifest(cls, manifest: ReviewPackageManifest) -> Self:
        """Project all canonical descriptor fields without coercive registry types."""
        return cls(
            package_info_version=manifest.package_info_version,
            bucket_id=manifest.bucket_id,
            work_unit_id=manifest.work_unit_id,
            calculation_revision_id=manifest.calculation_revision_id,
            registry_snapshot_ref=ModeloRegistrySnapshotCoordinates(
                modelo=manifest.registry_snapshot_ref.modelo,
                revision_id=manifest.registry_snapshot_ref.revision_id,
                modelo_year=manifest.registry_snapshot_ref.modelo_year,
                period=str(manifest.registry_snapshot_ref.period),
            ),
            modelo=manifest.modelo,
            filing_year=manifest.filing_year,
            period=PublicPeriod.from_period(manifest.period),
            revision_state=manifest.revision_state,
            has_ledger_evidence=manifest.has_ledger_evidence,
            built_at=manifest.built_at,
            built_by=manifest.built_by,
            notes=manifest.notes,
        )

    def to_manifest(self) -> ReviewPackageManifest:
        """Restore the exact registry reference through its canonical model."""
        return ReviewPackageManifest(
            package_info_version=self.package_info_version,
            bucket_id=self.bucket_id,
            work_unit_id=self.work_unit_id,
            calculation_revision_id=self.calculation_revision_id,
            registry_snapshot_ref=RegistrySnapshotRef(
                modelo=self.registry_snapshot_ref.modelo,
                revision_id=self.registry_snapshot_ref.revision_id,
                modelo_year=self.registry_snapshot_ref.modelo_year,
                period=self.registry_snapshot_ref.period,
            ),
            modelo=self.modelo,
            filing_year=self.filing_year,
            period=self.period.to_period(),
            revision_state=self.revision_state,
            has_ledger_evidence=self.has_ledger_evidence,
            built_at=self.built_at,
            built_by=self.built_by,
            notes=self.notes,
        )


class ModeloReviewPackageBuildPublicResultV1(BaseModel):
    """Complete build receipt and export event, without package bytes."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result_version: Literal[1] = 1
    output_path: str = Field(min_length=1)
    manifest: ModeloReviewPackageManifestPublic
    corpus_root_name: str = Field(min_length=1)
    member_count: int = Field(ge=1)
    export_bucket_event_id: str = Field(min_length=1, max_length=128)
    handoff_required: Literal[True] = True

    @classmethod
    def from_results(cls, build: ReviewPackageBuildResult, *, export_bucket_event_id: str) -> Self:
        """Carry the full package receipt and export event without draft bytes."""
        return cls(
            output_path=str(build.output_path),
            manifest=ModeloReviewPackageManifestPublic.from_manifest(build.manifest),
            corpus_root_name=build.corpus_root_name,
            member_count=build.member_count,
            export_bucket_event_id=export_bucket_event_id,
        )

    def to_result(self) -> ReviewPackageBuildResult:
        """Restore the canonical build receipt for existing CLI rendering."""
        return ReviewPackageBuildResult(
            output_path=Path(self.output_path),
            manifest=self.manifest.to_manifest(),
            corpus_root_name=self.corpus_root_name,
            member_count=self.member_count,
        )


def _require_review_package_export_identity(
    exported: ModeloExportResult,
    *,
    profile_id: str,
    work_unit_id: WorkUnitId,
    calculation_revision_id: CalculationRevisionId,
) -> None:
    """Admit the export receipt before rechecking the captured repository revisions."""
    if (
        exported.bucket_id != profile_id
        or exported.work_unit_id != work_unit_id
        or exported.calculation_revision_id != calculation_revision_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


class ModeloReviewPackageBuildExecutor:
    """Keep export, revision capture, staging, and package write in one worker."""

    def __init__(
        self,
        *,
        profile_resolver: Callable[[PinnedAuthorityOperation], TaxpayerProfile],
        export_ports_factory: ModeloExportPortsFactory,
        repositories: VerificationRepositoryBundleFactory,
    ) -> None:
        self._profile_resolver = profile_resolver
        self._export_ports_factory = export_ports_factory
        self._repositories = repositories

    async def execute(
        self, request: OperationRequest[ModeloReviewPackageBuildRequest], context: OperationExecutorContext
    ) -> str:
        """Publish the package within the worker's irreversible authority guard."""
        payload = request.payload
        if (
            request.definition_id != MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID
            or context.identity.subject_ref != request.subject_ref
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        await context.events.phase("modelo.review_package.build.preconditions")

        def publish() -> ModeloReviewPackageBuildPublicResultV1:
            profile_id = str(payload.profile_id)
            if require_active_bucket_id() != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            bundle = self._repositories(profile_id, operation=context.authority_operation)
            if bundle.calculation.bucket_id != profile_id or bundle.work_unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            revisions, revision_token = bundle.calculation.load_revisioned(operation=context.authority_operation)
            revision = revisions.get(payload.calculation_revision_id)
            if revision is None or revision.work_unit_id != request.subject_ref:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
            units, unit_token = bundle.work_unit.load_revisioned()
            unit = units.get(revision.work_unit_id)
            if unit is None or unit.bucket_id != profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            output = Path(payload.output_path)
            with validating_governed_facts(context.authority_operation):
                workflow_profile = self._profile_resolver(context.authority_operation)
                output.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="cadrumo-review-package-draft-", dir=output.parent) as name:
                    draft_path = Path(name) / "draft.fichero-boe"
                    exported = export_modelo_revision(
                        ModeloExportCommand(
                            calculation_revision_id=payload.calculation_revision_id,
                            output_path=draft_path,
                            actor=payload.actor,
                            refund_election=payload.refund_election,
                            payment_election=payload.payment_election,
                            prior_domiciliation_election=payload.prior_domiciliation_election,
                            charge_account_id=payload.charge_account_id,
                            refund_account_id=payload.refund_account_id,
                        ),
                        workflow_profile=workflow_profile,
                        operation=context.authority_operation,
                        export_ports=self._export_ports_factory(
                            bucket_id=profile_id,
                            m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
                            operation=context.authority_operation,
                        ),
                    )
                    _require_review_package_export_identity(
                        exported,
                        profile_id=profile_id,
                        work_unit_id=unit.work_unit_id,
                        calculation_revision_id=revision.calculation_revision_id,
                    )
                    _fresh_revisions, fresh_revision_token = bundle.calculation.load_revisioned(
                        operation=context.authority_operation
                    )
                    _fresh_units, fresh_unit_token = bundle.work_unit.load_revisioned()
                    if fresh_revision_token != revision_token or fresh_unit_token != unit_token:
                        raise ReviewPackageError(
                            translated_message="application.modelo.errors.review_package_generic",
                            context={
                                "calculation_revision_id": payload.calculation_revision_id,
                                "detail": "calculation or work unit changed during export",
                            },
                        )
                    built = build_review_package(
                        revision=revision,
                        work_unit=unit,
                        draft_bytes=draft_path.read_bytes(),
                        output_path=output,
                        built_by=payload.actor,
                        operation=context.authority_operation,
                        notes=payload.notes,
                    )
            return ModeloReviewPackageBuildPublicResultV1.from_results(
                built, export_bucket_event_id=exported.bucket_event_id
            )

        async def commit() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                result = await asyncio.to_thread(publish)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(result, written_at=now())

        return await await_cancellation_complete(commit(), task_name="modelo-review-package-build")


def build_modelo_review_package_build_definition(
    *,
    profile_resolver: Callable[[PinnedAuthorityOperation], TaxpayerProfile],
    export_ports_factory: ModeloExportPortsFactory,
    repositories: VerificationRepositoryBundleFactory,
) -> OperationDefinition:
    """Register one irreversible, secure-reference package publication."""

    def build() -> ModeloReviewPackageBuildExecutor:
        return ModeloReviewPackageBuildExecutor(
            profile_resolver=profile_resolver,
            export_ports_factory=export_ports_factory,
            repositories=repositories,
        )

    return OperationDefinition(
        definition_id=MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID,
        request_type=ModeloReviewPackageBuildRequest,
        result_type=ModeloReviewPackageBuildPublicResultV1,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloReviewPackageBuildRequest,
            executor_type=ModeloReviewPackageBuildExecutor,
            build=build,
        ),
        phase_codes=("modelo.review_package.build.preconditions",),
        interaction_kinds=frozenset(),
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
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}),
    )


def build_modelo_review_package_build_registration(
    definition: OperationDefinition, *, access_resolver: OperationAccessResolver | None = None
) -> OperationPublicDefinitionRegistrationV1:
    """Bind version-one public schemas and the composition-owned period gate."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloReviewPackageBuildRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=ModeloReviewPackageBuildPublicResultV1,
        ),
        access_resolver=access_resolver,
    )


__all__ = [
    "MODELO_REVIEW_PACKAGE_BUILD_OPERATION_DEFINITION_ID",
    "ModeloReviewPackageBuildPublicResultV1",
    "ModeloReviewPackageBuildRequest",
    "build_modelo_review_package_build_definition",
    "build_modelo_review_package_build_registration",
]
