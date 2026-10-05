"""Read persisted filing records and verification reports back for assertions.

Reads go through the same repositories and verification-report coordinate gate
the application services use, so a test observes the persisted state a
runtime caller would.
"""

from __future__ import annotations

from ...application.calculations.verification_report_gate import require_verification_report_coordinates_current
from ...application.modelo.filing_action_ports import FilingActionPorts
from ...core.identity.hex_ids import CalculationRevisionId
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.modelos.filing_record import ModeloRecord
from ...domain.modelos.verification_report import VerificationReport


def persisted_filing_record(filing_record_id: str, *, ports: FilingActionPorts) -> ModeloRecord:
    """Return the persisted filing record, failing the test when it is absent."""
    record = ports.filing_repository.load().get(filing_record_id)
    assert record is not None, f"filing record {filing_record_id} is not persisted"
    return record


def persisted_verification_reports(
    *,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
    calculation_revision_id: CalculationRevisionId | None = None,
) -> tuple[VerificationReport, ...]:
    """Return persisted verification reports ordered by revision and run time."""
    catalogue = require_verification_report_coordinates_current(
        ports.verification_repository.load(operation=operation),
        operation=operation,
    )
    return tuple(
        sorted(
            (
                report
                for report in catalogue.reports.values()
                if calculation_revision_id is None or report.calculation_revision_id == calculation_revision_id
            ),
            key=lambda report: (report.calculation_revision_id, report.run_at),
        )
    )


def persisted_verification_report(
    verification_report_id: str,
    *,
    ports: FilingActionPorts,
    operation: PinnedAuthorityOperation,
) -> VerificationReport:
    """Return one persisted verification report, failing the test when it is absent."""
    catalogue = require_verification_report_coordinates_current(
        ports.verification_repository.load(operation=operation),
        operation=operation,
    )
    report = catalogue.get(verification_report_id)
    assert report is not None, f"verification report {verification_report_id} is not persisted"
    return report
