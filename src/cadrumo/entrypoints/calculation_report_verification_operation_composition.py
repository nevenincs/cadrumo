"""Compose the existing calculation-summary verifier for one admitted profile."""

from __future__ import annotations

from uuid import UUID

from ..adapters.persistence.profile.review_package_signing import build_review_package_signing_keypair_reader
from ..application.modelo.calculation_report_verification import CalculationSummaryStoreContext
from ..application.modelo.calculation_report_verification_operation import ModeloCalculationReportVerificationPorts
from ..application.modelo.calculation_summary_pdf_ports import CalculationSummaryPdfReader
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..application.user_profile.capsule_record import ProfileRecordStore
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..application.wizard.status import taxpayer_profile_from_record
from ..core.bucket_pointer import require_active_bucket_id
from ..domain.calculations.registry.authority import PinnedAuthorityOperation
from ..domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .adapter_composition import build_modelo_export_ports


def build_modelo_calculation_report_verification_ports(
    *,
    profile_id: UUID,
    operation: PinnedAuthorityOperation,
    reader: CalculationSummaryPdfReader | None = None,
) -> ModeloCalculationReportVerificationPorts:
    """Decode the explicit profile with the worker pin and compose read authorities."""
    bucket_id = str(profile_id)
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if reader is None:
        from ..adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf

        reader = read_calculation_summary_pdf
    with validating_governed_facts(operation):
        repository = ProfileRecordRepository.for_current_session(
            profile_id, profile_decode_context=operation.profile_decode_context()
        )
        record = ProfileRecordStore(session=repository.session).load().record
        if repository.profile_id != profile_id or record.profile_id != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        workflow_profile = taxpayer_profile_from_record(record, schema=operation.profile_schema())
        export_ports = build_modelo_export_ports(
            bucket_id=bucket_id,
            m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
        )
    return ModeloCalculationReportVerificationPorts(
        profile_id=profile_id,
        reader=reader,
        store=CalculationSummaryStoreContext(
            active_bucket_id=bucket_id,
            export_ports=export_ports,
            signing_keypair=build_review_package_signing_keypair_reader(bucket_id=bucket_id),
            operation=operation,
        ),
    )
