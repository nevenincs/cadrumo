"""Public real-storage construction support for the modelo workbench surfaces.

Entrypoint tests consume this defining test-support module directly.

A seeded, complete taxpayer and one real declaration, read through the
production workbench: the form builder, the published form layout, the work
review, the edit admission, renewal, preflight and the apply prerequisite all
run for real against the bundled registry, through the same application reads
the profile worker's registered operations call. The seeded taxpayer is
deliberately complete, because an incomplete one would exercise refusal paths
in tests that mean to exercise a rendered workbench.

Operation submission is the one stand-in: a submitted request is recorded and
never supervised, so a test proves what the workbench asked for and can run the
captured request through the production executor itself. Every figure is
synthetic.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ....application.modelo.declarations_workspace_contracts import DeclarationsWorkspaceDeclarationRefV1
from ....application.modelo.edit_admission import ModeloEditRenewalResultV1, renew_modelo_edit_baseline
from ....application.modelo.edit_models import ModeloEditBaselineV1, ModeloEditPreflightResultV1, ModeloEditSubmissionV1
from ....application.modelo.edit_preflight import preflight_modelo_edit
from ....application.modelo.edit_refusal_projection import ModeloEditRefusalProjectionStore
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.workbench_operations import ModeloEditApplyPrerequisiteV1
from ....application.modelo.workbench_read import (
    ModeloWorkbenchFormReadV1,
    ModeloWorkbenchReadPorts,
    modelo_edit_prerequisite_source_boxes,
    read_modelo_casilla_help,
    read_modelo_workbench_form,
)
from ....application.operations.models import OperationId, OperationRequest
from ....core.casilla_id import CasillaId
from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tax_id_format import runtime_tax_id_format
from ....domain.modelos.work_unit import WorkUnit
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...adapter_composition import build_calculation_action_ports, build_work_lifecycle_ports
from ...operation_composition import build_production_operation_registry
from ..modelo.lifecycle import ModeloWorkspaceLifecycleDoor
from ..modelo.workbench.installed import InstalledModeloWorkbench

if TYPE_CHECKING:
    from ....application.operations.event_replay import OperationEventCursor
    from ....application.operations.frontend_contracts import (
        OperationCancellationResultV1,
        OperationDetachResultV1,
        OperationReviewProjectionResultV1,
    )
    from ....application.operations.frontend_projection import OperationReviewProjectionReferenceV1
    from ....application.operations.frontend_requests import OperationObservationResultV1
    from ....application.operations.interactions import OperationActorReference
    from ....application.operations.models import OperationRevision
    from ....application.operations.persistence.replay import OperationReplayLimit
    from ....application.operations.registry import OperationPublicContractSetV1
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation
    from ..operations.controller_port import OperationResponseControlPort

_BUCKET_ID = "13000000-0000-4000-8000-000000000451"
_T0 = datetime(2026, 6, 5, 9, 0, 0, tzinfo=UTC)
_ACTOR = "operator:tui-modelo"

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="identity.surnames", value="Workspace"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


class SubmittedOperation:
    """A recorded submission: it has an identity and admits start, and nothing ever supervises it."""

    def __init__(self, request: OperationRequest[BaseModel], operation_id: OperationId) -> None:
        """Keep the submitted request under its recorded identity."""
        self.request = request
        self._operation_id = operation_id

    @property
    def operation_id(self) -> OperationId:
        """The identity the recorded submission was given."""
        return self._operation_id

    @property
    def actor_ref(self) -> OperationActorReference:
        """The actor the workbench submits as."""
        return _ACTOR

    async def start(self) -> OperationId:
        """Admit the recorded submission without running it."""
        return self._operation_id

    async def observe(
        self, after_cursor: OperationEventCursor, *, page_limit: OperationReplayLimit = 256
    ) -> OperationObservationResultV1:
        """A recorded submission is never observed."""
        raise AssertionError("a recorded workbench submission is never supervised")

    async def resolve_review[ReviewT: BaseModel](
        self, reference: OperationReviewProjectionReferenceV1, projection_type: type[ReviewT]
    ) -> OperationReviewProjectionResultV1[ReviewT]:
        """A recorded submission has no review."""
        raise AssertionError("a recorded workbench submission is never supervised")

    async def response_control(
        self, *, interaction_id: str, revision: OperationRevision
    ) -> OperationResponseControlPort:
        """A recorded submission has no response."""
        raise AssertionError("a recorded workbench submission is never supervised")

    async def cancel(self, *, expected_revision: OperationRevision) -> OperationCancellationResultV1:
        """A recorded submission is never cancelled."""
        raise AssertionError("a recorded workbench submission is never supervised")

    async def detach(self, *, expected_revision: OperationRevision) -> OperationDetachResultV1:
        """A recorded submission is never detached."""
        raise AssertionError("a recorded workbench submission is never supervised")


@dataclass
class RecordedSubmissions:
    """Every request the workbench submitted, in order, under deterministic identities."""

    submitted: list[SubmittedOperation] = field(default_factory=list)

    async def submit(self, request: OperationRequest[BaseModel]) -> SubmittedOperation:
        """Record one submission and hand back its stand-in controller."""
        operation = SubmittedOperation(request, f"{len(self.submitted) + 1:064x}")
        self.submitted.append(operation)
        return operation

    def pop(self) -> OperationRequest[BaseModel]:
        """Take the latest recorded request."""
        return self.submitted.pop().request


@dataclass(frozen=True, slots=True)
class ApplicationWorkbenchSource:
    """Reads one declaration through the application reads the worker's operations run."""

    bucket_id: str
    work_unit_id: str
    ports: ModeloWorkbenchReadPorts
    operation: PinnedAuthorityOperation
    contracts: OperationPublicContractSetV1

    def read_form(self, language: OutputLanguage) -> ModeloWorkbenchFormReadV1:
        """Read the form and admit its edit baseline, as ``modelo.work.form`` does."""
        return read_modelo_workbench_form(
            self.work_unit_id,
            bucket_id=self.bucket_id,
            ports=self.ports,
            operation=self.operation,
            operation_contracts=self.contracts,
            language=language,
        )

    def help_card(
        self,
        casilla_id: CasillaId,
        *,
        registry_revision_id: str,
        calculation_revision_id: str | None,
        language: OutputLanguage,
    ) -> ModeloCasillaHelpCardV1:
        """Assemble one casilla's help, as ``modelo.work.casilla_help`` does."""
        return read_modelo_casilla_help(
            self.work_unit_id,
            casilla_id,
            bucket_id=self.bucket_id,
            registry_revision_id=registry_revision_id,
            calculation_revision_id=calculation_revision_id,
            ports=self.ports,
            operation=self.operation,
            language=language,
        )


def workbench_read_ports(bucket_id: str, operation: PinnedAuthorityOperation) -> ModeloWorkbenchReadPorts:
    """The profile repositories a declaration's workbench is read from."""
    ports = build_calculation_action_ports(bucket_id=bucket_id, operation=operation)
    return ModeloWorkbenchReadPorts(
        work_units=ports.work_unit_repository,
        calculations=ports.calculation_repository,
        verifications=VerificationReportCatalogueRepository(bucket_id=bucket_id),
        bucket_events=ports.bucket_event_repository,
    )


def application_lifecycle_door(
    *,
    work_unit_id: str,
    bucket_id: str,
    ports: ModeloWorkbenchReadPorts,
    operation: PinnedAuthorityOperation,
    contracts: OperationPublicContractSetV1,
    submissions: RecordedSubmissions,
    read: ModeloWorkbenchFormReadV1 | None,
    prerequisites: ModeloEditRefusalProjectionStore | None = None,
) -> ModeloWorkspaceLifecycleDoor:
    """The declaration's lifecycle door on the application reads the worker's operations run."""

    def renew(baseline: ModeloEditBaselineV1) -> ModeloEditRenewalResultV1:
        return renew_modelo_edit_baseline(
            baseline,
            work_catalogue=ports.work_units.load(),
            calculation_catalogue=ports.calculations.load(),
            operation=operation,
            operation_contracts=contracts,
        )

    def preflight(submission: ModeloEditSubmissionV1) -> ModeloEditPreflightResultV1:
        return preflight_modelo_edit(
            submission,
            work_catalogue=ports.work_units.load(),
            calculation_catalogue=ports.calculations.load(),
            tax_id_format=runtime_tax_id_format(authority=operation),
        )

    def prerequisite(
        operation_id: str, baseline: ModeloEditBaselineV1, registry_revision_id: str
    ) -> ModeloEditApplyPrerequisiteV1 | None:
        if prerequisites is None:
            return None
        taken = prerequisites.take(
            operation_id,
            work_unit_id=work_unit_id,
            baseline_id=baseline.baseline_id,
            calculation_revision_id=baseline.current_calculation_revision_id,
        )
        if taken is None:
            return None
        return ModeloEditApplyPrerequisiteV1(
            casilla_id=taken.casilla_id,
            calculation_revision_id=taken.calculation_revision_id,
            source_boxes=modelo_edit_prerequisite_source_boxes(
                taken, bucket_id=bucket_id, registry_revision_id=registry_revision_id, ports=ports, operation=operation
            ),
        )

    return ModeloWorkspaceLifecycleDoor(
        work_unit_id=work_unit_id,
        submit_operation=submissions.submit,
        calculation_revision_id=None if read is None else read.calculation_revision_id,
        verification_report_id=None if read is None else read.verification_report_id,
        edit_renewal=renew,
        edit_preflight=preflight,
        apply_prerequisite=prerequisite,
        asks_modelo_390=read is not None and read.asks_modelo_390,
    )


def declaration_of(unit: WorkUnit) -> DeclarationsWorkspaceDeclarationRefV1:
    """The declarations list's reference to one work unit, before it is calculated or filed."""
    return DeclarationsWorkspaceDeclarationRefV1(
        work_unit_id=unit.work_unit_id,
        modelo=unit.modelo,
        filing_year=unit.filing_year,
        period=unit.period,
        state=unit.state,
        has_current_calculation=False,
        has_current_filing=False,
    )


def application_workbench(
    unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
    submissions: RecordedSubmissions | None = None,
    prerequisites: ModeloEditRefusalProjectionStore | None = None,
    door_override: Callable[[ModeloWorkbenchFormReadV1 | None], ModeloWorkspaceLifecycleDoor] | None = None,
) -> InstalledModeloWorkbench:
    """The production workbench of one stored declaration, read and acted on through the application."""
    contracts = build_production_operation_registry().public_contract_set
    ports = workbench_read_ports(unit.bucket_id, operation)
    recorded = submissions if submissions is not None else RecordedSubmissions()

    def door(read: ModeloWorkbenchFormReadV1 | None) -> ModeloWorkspaceLifecycleDoor:
        return application_lifecycle_door(
            work_unit_id=unit.work_unit_id,
            bucket_id=unit.bucket_id,
            ports=ports,
            operation=operation,
            contracts=contracts,
            submissions=recorded,
            read=read,
            prerequisites=prerequisites,
        )

    return InstalledModeloWorkbench(
        declaration=declaration_of(unit),
        source=ApplicationWorkbenchSource(
            bucket_id=unit.bucket_id,
            work_unit_id=unit.work_unit_id,
            ports=ports,
            operation=operation,
            contracts=contracts,
        ),
        door=door_override or door,
    )


@contextmanager
def real_workbench(
    tmp_path: Path,
    *,
    modelo: str = "130",
    filing_year: int = 2026,
    period_code: str = "1T",
) -> Generator[InstalledModeloWorkbench]:
    """Yield the production reader and actions of one seeded declaration.

    Held open as a context manager because the profile runtime must stay live
    while a mounted workbench reads through it. The address picks the SHAPE of
    the data -- a compact quarterly return or a dense annual one -- from the
    bundled registry rather than from padded fixture rows.
    """
    with (
        isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile,
        bundled_indexed_authority().operation() as operation,
    ):
        seed_test_profile_record(
            create_user_profile_record(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=profile.bucket_id,
                facts=_READY_PROFILE_FACTS,
                created_at=_T0,
                updated_at=_T0,
                context=operation.profile_create_context(),
            ),
        )
        period = Period.from_year_and_code(filing_year, period_code)
        unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=str(
                operation.revision_for_context(modelo, filing_year=filing_year, period=period.registry_token).id
            ),
            ports=build_work_lifecycle_ports(bucket_id=profile.bucket_id),
            clock=_T0,
            operation=operation,
        )
        yield application_workbench(unit, operation=operation)


__all__ = [
    "ApplicationWorkbenchSource",
    "RecordedSubmissions",
    "SubmittedOperation",
    "application_lifecycle_door",
    "application_workbench",
    "declaration_of",
    "real_workbench",
    "workbench_read_ports",
]
