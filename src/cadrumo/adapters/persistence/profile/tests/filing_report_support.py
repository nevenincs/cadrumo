"""Explicit approved-report prerequisite for isolated persistence-gate tests.

These tests seed already-verified revisions to exercise a later filing writer.
The fixture report does not claim the live verifier would grant that scenario.
"""

from __future__ import annotations

from cadrumo.core.identity.hex_ids import VerificationReportId
from cadrumo.domain.modelos.calculation_revision import CalculationRevision
from cadrumo.domain.modelos.protocols import VerificationReportCatalogueRepositoryProtocol
from cadrumo.domain.modelos.verification_report import (
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from cadrumo.domain.modelos.verification_repository import upsert_verification_report


def seed_filing_gate_report(
    revision: CalculationRevision,
    repository: VerificationReportCatalogueRepositoryProtocol,
) -> VerificationReportId:
    """Persist a matching grant for a deliberately synthetic verified fixture."""
    actor = revision.verified_by
    run_at = revision.verified_at
    assert actor is not None and run_at is not None, "fixture revision must be verified"
    report_id = derive_verification_report_id(
        calculation_revision_id=revision.calculation_revision_id,
        completeness_status=VerificationCompletenessStatus.COMPLETE,
        findings=(),
        verified_by=actor,
    )
    repository.save(
        upsert_verification_report(
            repository.load(),
            VerificationReport(
                verification_report_id=report_id,
                calculation_revision_id=revision.calculation_revision_id,
                registry_snapshot_ref=revision.registry_snapshot_ref,
                completeness_status=VerificationCompletenessStatus.COMPLETE,
                findings=(),
                run_at=run_at,
                verified_by=actor,
                granted_verificado_completo=True,
            ),
        )
    )
    return report_id
