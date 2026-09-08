"""Registry-coordinate gate for persisted verification-report catalogues."""

from __future__ import annotations

from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.verification_report import VerificationReportCatalogue
from .revision_carry_gate import revision_carry_outcome


def require_verification_report_coordinates_current(
    catalogue: VerificationReportCatalogue,
) -> VerificationReportCatalogue:
    """Return ``catalogue`` only when every report's producing revision re-confirms."""
    for report in catalogue.values():
        outcome = revision_carry_outcome(report.registry_snapshot_ref)
        if outcome.refused:
            raise ModeloValidationError(
                "verification report registry coordinate cannot be re-confirmed: "
                f"{report.registry_snapshot_ref.revision_id}: {outcome.detail}"
            )
    return catalogue


__all__ = ["require_verification_report_coordinates_current"]
