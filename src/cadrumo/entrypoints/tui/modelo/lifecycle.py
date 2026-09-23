"""TUI submission door for Modelo lifecycle operations.

The door owns no tax or persistence behaviour.  It creates registered public
requests and hands them to the session's composed operation services, so the
modal remains the one place that observes cancellation, refusal and terminal
success.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

from ....application.modelo.edit_contract import ModeloEditMutationFamily
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBaselineV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
    ModeloEditScalarAddressV1,
    ModeloEditScalarIntentKind,
    ModeloEditSubmissionV1,
    ModeloScalarEditIntentV1,
)
from ....application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationAdmission,
)
from ....application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_WORK_FILE_OPERATION_DEFINITION_ID,
    MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
    ModeloEditApplyOperationRequestV1,
    ModeloEditApplySubmissionV1,
    ModeloExportRequest,
    ModeloWorkCalculateOrdinaryM303EvidenceRequestV1,
    ModeloWorkCalculateRequest,
    ModeloWorkFileApproval,
    ModeloWorkFileRequest,
    ModeloWorkVerifyRequest,
)
from ....application.operations.composition import OperationComposedServices
from ....application.operations.models import OperationRequest
from ....core.errors.hierarchy import CadrumoError
from ..operations.controller import OperationController

_ACTOR_REF = "operator:tui-modelo"


class ModeloLifecycleActionUnavailableError(CadrumoError):
    """The selected lifecycle state does not admit the requested action."""


@dataclass(frozen=True, slots=True)
class ModeloWorkspaceLifecycleDoor:
    """Submit one selected declaration lifecycle action through public services."""

    services: OperationComposedServices
    work_unit_id: str
    calculation_revision_id: str | None = None
    verification_report_id: str | None = None
    refresh_after_success: Callable[[], object] | None = None
    edit_baseline: ModeloEditBaselineV1 | None = None
    m303_exonerado_390_attestation_admission: (
        Callable[[datetime], M303Exonerado390ApplicabilityAttestationAdmission] | None
    ) = None

    async def calculate(
        self,
        *,
        ordinary_m303_filing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV1 | None = None,
    ) -> OperationController:
        """Calculate the selected work unit from its canonical persisted ledger."""
        payload: dict[str, object] = {
            "work_unit_id": self.work_unit_id,
            "actor": _ACTOR_REF,
        }
        if ordinary_m303_filing_evidence is not None:
            payload["ordinary_m303_filing_evidence"] = ordinary_m303_filing_evidence
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_WORK_CALCULATE_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloWorkCalculateRequest(**payload),
            )
        )

    async def author_ordinary_m303_filing_evidence(
        self,
        *,
        joint_return_elected: bool,
        annual_volume_nonzero: bool,
        observed_at: datetime,
    ) -> ModeloWorkCalculateOrdinaryM303EvidenceRequestV1:
        """Admit a new secure attestation, then expose only its typed coordinates to calculation."""
        admit = self.m303_exonerado_390_attestation_admission
        if admit is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="tui.modelo.m303_evidence.admission_unavailable"
            )
        admission = await asyncio.to_thread(admit, observed_at)
        return ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
            joint_return_elected=joint_return_elected,
            annual_volume_nonzero=annual_volume_nonzero,
            m303_exonerado_390_attachment_id=admission.attachment_id,
            m303_exonerado_390_sha256=admission.sha256,
        )

    async def apply_edits(
        self,
        *,
        scalar_values: dict[str, str],
        binding_values: dict[str, str],
    ) -> OperationController:
        """Apply staged registry-addressed values through Modelo Edit Contract V1."""
        baseline = self.edit_baseline
        if baseline is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.edit_unavailable"
            )
        submission = ModeloEditSubmissionV1(
            baseline=baseline,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            scalar_intents=tuple(
                ModeloScalarEditIntentV1(
                    address=ModeloEditScalarAddressV1(casilla_id=casilla_id),
                    kind=ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                    value=value,
                )
                for casilla_id, value in scalar_values.items()
            ),
            binding_intents=tuple(
                ModeloBindingEditIntentV1(
                    address=ModeloEditBindingAddressV1(binding_id=binding_id),
                    kind=ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                    value=value,
                )
                for binding_id, value in binding_values.items()
            ),
        )
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloEditApplyOperationRequestV1(
                    submission=ModeloEditApplySubmissionV1.from_submission(submission)
                ),
            )
        )

    async def verify(self) -> OperationController:
        """Verify the selected current calculation or refuse when none is present."""
        calculation_revision_id = self._require_calculation_revision()
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_WORK_VERIFY_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloWorkVerifyRequest(calculation_revision_id=calculation_revision_id, actor=_ACTOR_REF),
            )
        )

    async def file(self) -> OperationController:
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

    async def export(self, *, output_path: str) -> OperationController:
        """Export the selected verified revision to the operator-selected local path."""
        return await self._submit(
            OperationRequest(
                definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                subject_ref=self.work_unit_id,
                payload=ModeloExportRequest(
                    calculation_revision_id=self._require_calculation_revision(),
                    output_path=output_path,
                    actor=_ACTOR_REF,
                ),
            )
        )

    def _require_calculation_revision(self) -> str:
        if self.calculation_revision_id is None:
            raise ModeloLifecycleActionUnavailableError(
                translated_message="application.modelo.lifecycle.refusal.calculation_required"
            )
        return self.calculation_revision_id

    async def _submit(self, request: OperationRequest[BaseModel]) -> OperationController:
        submission = await self.services.submission.submit(request, actor_ref=_ACTOR_REF)
        controller = OperationController(services=self.services, submission=submission, actor_ref=_ACTOR_REF)
        await controller.start()
        return controller


__all__ = ["ModeloLifecycleActionUnavailableError", "ModeloWorkspaceLifecycleDoor"]
