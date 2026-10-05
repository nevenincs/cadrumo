"""TUI submission door for Modelo lifecycle operations.

The door owns no tax or persistence behaviour.  It creates registered public
requests and hands them to the session's runtime host, so the modal remains
the one place that observes cancellation, refusal and terminal success.

Editing is admitted lazily: the baseline arrives with the workbench's form
read, and the door holds the worker's renewal, preflight and prerequisite
reads as callables, run off the event loop when an edit session reviews and
submits. Every edit is a typed intent -- set, clear or restore a casilla, set
or remove a binding override -- and a submission renews its baseline first, so
an unchanged declaration is never refused merely for time passing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from ....application.modelo.action_errors import modelo_edit_refusal_error
from ....application.modelo.edit_admission import ModeloEditRenewalResultV1
from ....application.modelo.edit_apply_contracts import ModeloEditApplySubmissionV1
from ....application.modelo.edit_contract import ModeloEditMutationFamily
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditPreflightResultV1,
    ModeloEditRefusedV1,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.edit_operator_input import ModeloEditOperatorInputV2
from ....application.modelo.export_projection import ModeloExportPublicResultV3
from ....application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
)
from ....application.modelo.work_calculation_contracts import (
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV2,
    ModeloWorkCalculateRequest,
)
from ....application.modelo.work_export_contracts import ModeloExportRequest
from ....application.modelo.work_filing_contracts import ModeloWorkFileApproval, ModeloWorkFileRequest
from ....application.modelo.work_verification_contracts import ModeloWorkVerifyRequest
from ....application.modelo.workbench_operations import ModeloEditApplyPrerequisiteV1
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.models import OperationRequest
from ....application.runtime.contracts import RuntimeRefusalError
from ....core.errors.hierarchy import CadrumoError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.payment_election import PaymentElection
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ..operations.controller_port import OperationControllerPort

_ACTOR_REF = "operator:tui-modelo"


class ModeloLifecycleActionUnavailableError(CadrumoError):
    """The selected lifecycle state does not admit the requested action."""


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceLifecycleDoor:
    """Submit one selected declaration lifecycle action through the runtime host."""

    work_unit_id: str
    submit_operation: Callable[[OperationRequest[BaseModel]], Awaitable[OperationControllerPort]]
    calculation_revision_id: str | None = None
    verification_report_id: str | None = None
    refresh_after_success: Callable[[], object] | None = None
    #: Renews a baseline when only its lifetime changed, or refuses naming what moved.
    edit_renewal: Callable[[ModeloEditBaselineV1], ModeloEditRenewalResultV1] | None = None
    #: Evaluates a submission without applying it and names the address of every finding.
    edit_preflight: Callable[[ModeloEditSubmissionV1], ModeloEditPreflightResultV1] | None = None
    #: Reads, once, the calculation prerequisite a settled Apply of this baseline named, in this registry revision.
    apply_prerequisite: Callable[[str, ModeloEditBaselineV1, str], ModeloEditApplyPrerequisiteV1 | None] | None = None
    m303_exonerado_390_attestation_admission: (
        Callable[[datetime], M303Exonerado390ApplicabilityAttestationAdmission] | None
    ) = None
    #: Whether this work unit's Modelo 303 period asks the Modelo 390 exemption, resolved under the pinned authority.
    asks_modelo_390: bool = False
    #: Reads one settled export's public result through the same runtime session.
    read_export_result: Callable[[OperationPublicProjectionV1], Awaitable[ModeloExportPublicResultV3]] | None = None

    async def calculate(
        self,
        *,
        ordinary_m303_filing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV2 | None = None,
    ) -> OperationControllerPort:
        """Calculate the selected work unit from its canonical persisted ledger."""
        # Other modelos keep the request shape without the optional M303 field set at all.
        payload = (
            ModeloWorkCalculateRequest(work_unit_id=self.work_unit_id, actor=_ACTOR_REF)
            if ordinary_m303_filing_evidence is None
            else ModeloWorkCalculateRequest(
                work_unit_id=self.work_unit_id,
                actor=_ACTOR_REF,
                ordinary_m303_filing_evidence=ordinary_m303_filing_evidence,
            )
        )
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=payload,
            )
        )

    async def author_ordinary_m303_filing_evidence(
        self,
        *,
        joint_return_elected: bool,
        observed_at: datetime,
    ) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV2:
        """Admit a new secure attestation, then expose only its typed coordinates to calculation."""
        admit = self.m303_exonerado_390_attestation_admission
        if admit is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="tui.modelo.m303_evidence.admission_unavailable"
            )
        admission = await asyncio.to_thread(admit, observed_at)
        return ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
            joint_return_elected=joint_return_elected,
            m303_exonerado_390_attachment_id=admission.attachment_id,
            m303_exonerado_390_sha256=admission.sha256,
        )

    async def preflight_edits(
        self,
        *,
        baseline: ModeloEditBaselineV1,
        scalar_intents: tuple[ModeloScalarEditIntentV1, ...] = (),
        binding_intents: tuple[ModeloBindingEditIntentV1, ...] = (),
    ) -> ModeloEditPreflightResultV1:
        """Evaluate staged intents without applying them, off the event loop, naming every finding's address."""
        preflight = self.edit_preflight
        if preflight is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.edit_unavailable"
            )
        return await asyncio.to_thread(
            preflight, _edit_submission(baseline, scalar_intents=scalar_intents, binding_intents=binding_intents)
        )

    async def apply_edits(
        self,
        *,
        baseline: ModeloEditBaselineV1,
        scalar_intents: tuple[ModeloScalarEditIntentV1, ...] = (),
        binding_intents: tuple[ModeloBindingEditIntentV1, ...] = (),
    ) -> tuple[OperationControllerPort, ModeloEditBaselineV1]:
        """Renew the baseline, then submit the typed intents through Modelo Edit Contract V1.

        The renewal is silent when only the baseline's lifetime changed. When
        the declaration itself moved, the stale refusal is raised as its
        registered, localized error before anything is submitted, so the
        operator's staged intents stay with the caller. The renewed baseline is
        returned with the controller, because a failed Apply's prerequisite is
        read against exactly that baseline.
        """
        renewal = await asyncio.to_thread(self._require_renewal(), baseline)
        if isinstance(renewal, ModeloEditRefusedV1):
            raise modelo_edit_refusal_error(renewal.refusal)
        submission = _edit_submission(renewal.baseline, scalar_intents=scalar_intents, binding_intents=binding_intents)
        controller = await self._submit(
            OperationRequest(
                definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloEditOperatorInputV2(submission=ModeloEditApplySubmissionV1.from_submission(submission)),
            )
        )
        return controller, renewal.baseline

    async def settled_apply_prerequisite(
        self, operation_id: str, baseline: ModeloEditBaselineV1, registry_revision_id: str
    ) -> ModeloEditApplyPrerequisiteV1 | None:
        """Read the named source a settled Apply failed on, or ``None`` when it named none."""
        read = self.apply_prerequisite
        if read is None:
            return None
        return await asyncio.to_thread(read, operation_id, baseline, registry_revision_id)

    async def verify(self) -> OperationControllerPort:
        """Verify the selected current calculation or refuse when none is present."""
        calculation_revision_id = self._require_calculation_revision()
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloWorkVerifyRequest(calculation_revision_id=calculation_revision_id, actor=_ACTOR_REF),
            )
        )

    async def file(self) -> OperationControllerPort:
        """Record the locally filed revision after the caller's explicit confirmation."""
        calculation_revision_id = self._require_calculation_revision()
        if self.verification_report_id is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.verification_required"
            )
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloWorkFileRequest(
                    approval=ModeloWorkFileApproval(
                        calculation_revision_id=calculation_revision_id,
                        verification_report_id=self.verification_report_id,
                    ),
                    actor=_ACTOR_REF,
                ),
            )
        )

    async def export(
        self,
        *,
        output_path: str,
        refund_election: RefundElection,
        payment_election: PaymentElection,
        prior_domiciliation_election: PriorDomiciliationElection,
        replace_existing: bool = False,
        artefact: ModeloExportArtefact = ModeloExportArtefact.FICHERO_BOE,
        charge_account_id: str | None = None,
        refund_account_id: str | None = None,
    ) -> OperationControllerPort:
        """Export the selected verified revision to the operator-selected path with the operator's choices.

        ``artefact`` names which export the operator asked for. It defaults to the
        AEAT-compatible filing file so a caller that offers no choice submits the
        export this door always submitted.
        """
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloExportRequest(
                    calculation_revision_id=self._require_calculation_revision(),
                    output_path=str(Path(output_path).resolve()),
                    refund_election=refund_election,
                    payment_election=payment_election,
                    prior_domiciliation_election=prior_domiciliation_election,
                    charge_account_id=charge_account_id,
                    refund_account_id=refund_account_id,
                    replace_existing=replace_existing,
                    artefact=artefact,
                    report_language=OutputLanguage(output_language()),
                    actor=_ACTOR_REF,
                ),
            )
        )

    async def settled_export_result(self, projection: OperationPublicProjectionV1) -> ModeloExportPublicResultV3 | None:
        """Resolve one settled export's public result through the runtime's result door.

        ``None`` when the projection is not a successful export or its result
        cannot be resolved; the caller states that absence rather than inventing
        the facts the result would have carried.
        """
        if (
            self.read_export_result is None
            or projection.definition_id != MODELO_EXPORT_OPERATION_DEFINITION_ID
            or projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or projection.definition_contract.result_schema is None
        ):
            return None
        try:
            return await self.read_export_result(projection)
        except (RuntimeRefusalError, RuntimeFrontendRefusedError):
            return None

    def _require_renewal(self) -> Callable[[ModeloEditBaselineV1], ModeloEditRenewalResultV1]:
        renew = self.edit_renewal
        if renew is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.edit_unavailable"
            )
        return renew

    def _require_calculation_revision(self) -> str:
        if self.calculation_revision_id is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.calculation_required"
            )
        return self.calculation_revision_id

    async def _submit(self, request: OperationRequest[BaseModel]) -> OperationControllerPort:
        controller = await self.submit_operation(request)
        try:
            await controller.start()
        except (RuntimeRefusalError, RuntimeFrontendRefusedError) as refusal:
            # Admission may have succeeded before its acknowledgement was lost.
            # Keep the submitted identity without inferring rollback or retry.
            raise ModeloLifecycleActionUnavailableError(
                refusal.reason.value if isinstance(refusal, RuntimeRefusalError) else refusal.reason,
                context={
                    "operation_id": controller.operation_id,
                    "effect": OperationEffect.UNKNOWN.value,
                },
            ) from None
        return controller


def _edit_submission(
    baseline: ModeloEditBaselineV1,
    *,
    scalar_intents: tuple[ModeloScalarEditIntentV1, ...],
    binding_intents: tuple[ModeloBindingEditIntentV1, ...],
) -> ModeloEditSubmissionV1:
    return ModeloEditSubmissionV1(
        baseline=baseline,
        mutation_family=ModeloEditMutationFamily.CALCULATE,
        scalar_intents=scalar_intents,
        binding_intents=binding_intents,
    )


__all__ = ["ModeloLifecycleActionUnavailableError", "ModeloWorkspaceLifecycleDoor"]
