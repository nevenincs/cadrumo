"""The registered export result carries a lossless strict fichero-BOE receipt."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....application.calculations.observations_repository import PriorDomiciliationElectionProjection
from ....application.operations.models import OperationIdentity, OperationTerminalReceipt
from ....application.operations.registry import (
    OperationDefinition,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ....core.modelo_export_artefact import ModeloExportArtefact
from ....core.operations import OperationEffect, OperationTerminalCondition
from ....core.payment_election import PaymentElection
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.refund_election import RefundElection
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.tax_id_format import SubjectTaxId
from ....domain.filing.schema import ModeloCasillaProvenance
from ....domain.filing.software_identity import AeatSoftwareIdentityGrade
from ..calculation_summary_pdf_ports import CalculationSummaryCertifier, CalculationSummaryPdfRequest
from ..export import ModeloExportResult, ModeloIvaWalletDecisionProvenance
from ..export_ports import ModeloExportPorts
from ..export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV2,
    ModeloFicheroBoePublicReceipt,
)
from ..operation_definitions import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    ModeloExportSettledResult,
    build_modelo_export_definition,
    build_modelo_export_registration,
)
from ..review_package_signing_ports import ReviewPackageSigningKeypairCapability

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REVISION_ID = "a" * 64
_WORK_UNIT_ID = "b" * 64
_BASELINE_FILING_ID = "c" * 64
_FILE_DIGEST = "d" * 64
_AT = datetime(2026, 9, 26, 8, 30, tzinfo=UTC)


def _canonical_receipt(
    *,
    include_prior_proof: bool,
    include_wallet_provenance: bool,
    include_elections: bool,
    completeness_unverified: bool,
) -> ModeloExportResult:
    """Build real canonical domain values for both full and neutral receipts."""
    prior_election = (
        PriorDomiciliationElection.CANCEL_OR_MODIFY if include_prior_proof else PriorDomiciliationElection.KEEP
    )
    prior = PriorDomiciliationElectionProjection(
        election=prior_election,
        baseline_filing_record_id=_BASELINE_FILING_ID if include_prior_proof else None,
        baseline_evidence_reference_id="aeat-evidence-reference" if include_prior_proof else None,
        baseline_result_disposition=ResultDisposition.DOMICILIACION if include_prior_proof else None,
        baseline_source_header_locator="fichero-boe:header:tipo-declaracion" if include_prior_proof else None,
    )
    wallet = (
        ModeloIvaWalletDecisionProvenance(
            decision_ref=f"sha256:{'e' * 64}",
            selected_authority="official_observation",
            divergence="none",
            target_year=2025,
            target_period=Period.from_year_and_code(2025, "4T"),
            authority_source_kinds=("aeat_capture", "app_filing"),
            authority_source_refs=(f"sha256:{'f' * 64}",),
        )
        if include_wallet_provenance
        else None
    )
    return ModeloExportResult(
        calculation_revision_id=_REVISION_ID,
        work_unit_id=_WORK_UNIT_ID,
        bucket_id="5aa00000-0000-4000-8000-0000000000aa",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        output_path=Path("C:/tax exports/modelo-303.fichero-boe"),
        byte_size=18_432,
        file_sha256=_FILE_DIGEST,
        format="fichero-boe",
        exported_at=_AT,
        actor="gestoria operator",
        bucket_event_id="modelo-export-event-42",
        resolved_result_disposition=(
            ResultDisposition.DOMICILIACION if include_elections else ResultDisposition.INGRESO
        ),
        payment_election=PaymentElection.DOMICILIACION if include_elections else None,
        refund_election=RefundElection.DEVOLVER if include_elections else None,
        prior_domiciliation_election=prior,
        casilla_provenance=(
            ModeloCasillaProvenance(
                casilla_id="303.resultado-final",
                formula_id="m303.resultado-final",
                legal_refs=("ley-37-1992:art-116",),
                source_refs=("aeat-303-diseno-2026",),
            ),
        ),
        iva_wallet_decision_provenance=wallet,
        local_evidence_status="local_export_not_official_aeat_filing_evidence",
        official_evidence_message="The operator must submit this local export through AEAT.",
        completeness_unverified=completeness_unverified,
        software_identity_grade=AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK if include_elections else None,
    )


def test_fichero_boe_receipt_roundtrips_complete_canonical_receipt() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=True,
        include_wallet_provenance=True,
        include_elections=True,
        completeness_unverified=True,
    )

    projected = ModeloFicheroBoePublicReceipt.from_result(canonical)
    restored_projection = ModeloFicheroBoePublicReceipt.model_validate_json(projected.model_dump_json())

    assert restored_projection == projected
    assert restored_projection.to_result() == canonical
    assert restored_projection.period.filing_year == canonical.period.filing_year
    assert restored_projection.period.code == canonical.period.registry_token
    assert restored_projection.output_path == str(canonical.output_path)
    assert restored_projection.payment_election is PaymentElection.DOMICILIACION
    assert restored_projection.refund_election is RefundElection.DEVOLVER
    assert restored_projection.prior_domiciliation_election.to_provenance() == canonical.prior_domiciliation_election
    assert restored_projection.iva_wallet_decision_provenance is not None
    assert (
        restored_projection.iva_wallet_decision_provenance.to_provenance() == canonical.iva_wallet_decision_provenance
    )
    assert restored_projection.casilla_provenance == canonical.casilla_provenance
    assert restored_projection.completeness_unverified
    assert restored_projection.to_result().completeness_advisory_message == canonical.completeness_advisory_message
    assert restored_projection.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK


def test_fichero_boe_receipt_preserves_neutral_optional_provenance() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=False,
        include_wallet_provenance=False,
        include_elections=False,
        completeness_unverified=False,
    )

    projected = ModeloFicheroBoePublicReceipt.from_result(canonical)
    restored = ModeloFicheroBoePublicReceipt.model_validate_json(projected.model_dump_json())

    assert restored.to_result() == canonical
    assert restored.prior_domiciliation_election.to_provenance() == canonical.prior_domiciliation_election
    assert restored.prior_domiciliation_election.baseline_filing_record_id is None
    assert restored.iva_wallet_decision_provenance is None
    assert restored.payment_election is None
    assert restored.refund_election is None
    assert not restored.completeness_unverified
    assert restored.software_identity_grade is None


def _unused_ports_factory(*, bucket_id: str, m303_rectificativa_taxpayer_tax_id: SubjectTaxId) -> ModeloExportPorts:
    del bucket_id, m303_rectificativa_taxpayer_tax_id
    raise AssertionError("registration must not construct export ports")


def _unused_signing_keypair(*, bucket_id: str) -> ReviewPackageSigningKeypairCapability:
    del bucket_id
    raise AssertionError("registration must not open the signing key")


def _unused_pdf_writer(request: CalculationSummaryPdfRequest, /, *, certify: CalculationSummaryCertifier) -> bytes:
    del request, certify
    raise AssertionError("registration must not draw a summary")


def _export_registration() -> tuple[OperationDefinition, OperationPublicDefinitionRegistrationV1]:
    definition = build_modelo_export_definition(
        export_ports_factory=_unused_ports_factory,
        signing_keypair_capability_factory=_unused_signing_keypair,
        calculation_summary_pdf_writer=_unused_pdf_writer,
    )
    return definition, build_modelo_export_registration(definition)


def test_export_registration_binds_v2_to_the_public_wire_model() -> None:
    definition, registration = _export_registration()
    OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    assert definition.result_type is ModeloExportSettledResult
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "modelo.export.result"
    assert registration.contract.result_schema.schema_version == 2
    result_binding = next(
        binding for binding in registration.schema_bindings if binding.identity.schema_id == "modelo.export.result"
    )
    assert result_binding.model_type is ModeloExportPublicResultV2


def test_export_projection_carries_the_complete_fichero_boe_receipt() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=True,
        include_wallet_provenance=True,
        include_elections=True,
        completeness_unverified=True,
    )
    _, registration = _export_registration()
    projector = registration.result_projector
    assert projector is not None
    terminal = OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="e" * 64, definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID, subject_ref=_WORK_UNIT_ID
        ),
        revision=4,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.UPDATED,
        settled_at=_AT,
        result_ref="f" * 64,
    )

    projected = projector(ModeloExportSettledResult(fichero_boe=canonical), terminal)
    assert isinstance(projected, ModeloExportPublicResultV2)
    restored = ModeloExportPublicResultV2.model_validate_json(projected.model_dump_json())

    assert restored.artefact is ModeloExportArtefact.FICHERO_BOE
    assert restored.evidence_status is ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
    assert restored.completeness is ModeloExportCompleteness.UNVERIFIED
    assert restored.fichero_boe is not None
    assert restored.fichero_boe.to_result() == canonical


def test_export_public_result_refuses_a_receipt_that_does_not_match_its_artefact() -> None:
    canonical = _canonical_receipt(
        include_prior_proof=False,
        include_wallet_provenance=False,
        include_elections=False,
        completeness_unverified=False,
    )
    summary = {
        "calculation_revision_id": _REVISION_ID,
        "export_format": "fichero-boe",
        "output_path": str(canonical.output_path),
        "byte_size": canonical.byte_size,
        "file_sha256": _FILE_DIGEST,
        "software_identity_grade": None,
        "evidence_status": ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE,
        "completeness": ModeloExportCompleteness.NOT_FLAGGED,
    }

    with pytest.raises(ValueError, match="carries exactly its receipt"):
        ModeloExportPublicResultV2.model_validate({**summary, "artefact": ModeloExportArtefact.FICHERO_BOE})
    with pytest.raises(ValueError, match="carries exactly its receipt"):
        ModeloExportPublicResultV2.model_validate(
            {
                **summary,
                "artefact": ModeloExportArtefact.CALCULATION_REPORT_CSV,
                "fichero_boe": ModeloFicheroBoePublicReceipt.from_result(canonical),
            }
        )
