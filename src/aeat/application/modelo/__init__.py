"""Application services for modelo work-unit lifecycle.

The modelo work-unit verbs (``create``, ``list``, ``status``,
``rename``) call into this package. The CLI layer at
``aeat.entrypoints.cli._modelo`` is a thin Typer transport over
the services exposed here.

Bucket scoping is honoured at the API boundary: every action
accepts an explicit ``bucket_id`` rather than implicitly reading
the active profile. The CLI layer derives ``bucket_id`` from the
active profile when the caller did not pass one explicitly; this
keeps the application service unit-testable without a workflow-
state fixture.
"""

from __future__ import annotations

from ._actions import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    FilingRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitAlreadyDiscardedError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    calculate_modelo_revision,
    create_work_unit,
    discard_work_unit,
    file_modelo_revision,
    get_calculation_revision,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    list_calculation_revisions,
    list_filing_records,
    list_verification_reports,
    list_work_units,
    mark_revision_verified_complete,
    rename_work_unit,
    verify_modelo_revision,
)

__all__ = [
    "CalculationRevisionNotFoundError",
    "CalculationRevisionStateError",
    "FilingRecordNotFoundError",
    "VerificationReportNotFoundError",
    "WorkUnitAlreadyDiscardedError",
    "WorkUnitMutationRefusedError",
    "WorkUnitNotFoundError",
    "calculate_modelo_revision",
    "create_work_unit",
    "discard_work_unit",
    "file_modelo_revision",
    "get_calculation_revision",
    "get_filing_record",
    "get_verification_report",
    "get_work_unit",
    "list_calculation_revisions",
    "list_filing_records",
    "list_verification_reports",
    "list_work_units",
    "mark_revision_verified_complete",
    "rename_work_unit",
    "verify_modelo_revision",
]
