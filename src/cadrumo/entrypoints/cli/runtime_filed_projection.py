"""Restore filed-capture presentation reports from their safe public projections."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, TypedDict
from uuid import UUID

from pydantic import BaseModel

from ...application.live.filed_single_capture_operation import (
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
)
from ...application.live.remote_state_models import FiledCaptureEvidenceTally
from ...application.modelo.filing_chain_reconciliation import (
    FilingEvidenceBasis,
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ...core.casilla_id import validated_casilla_id
from ...core.json_contract import Notice
from ...core.operations import OperationEffect, OperationTerminalCondition
from ...core.period import Period
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error


def context_from_pairs(pairs: tuple[tuple[str, str], ...] | None) -> dict[str, str] | None:
    """Rebuild a notice context, refusing a projection that repeats a key."""
    if pairs is None:
        return None
    context = dict(pairs)
    if len(context) != len(pairs):
        raise ValueError("notice context contains duplicate keys")
    return context


def capture_notice(notice: FiledCaptureNoticeV1) -> Notice:
    """Restore one capture advisory with its original severity, code and context."""
    return Notice(
        severity=notice.severity,
        code=notice.code,
        message=notice.message,
        context=context_from_pairs(notice.context),
    )


class _CaptureTallyProjection(Protocol):
    """The evidence tally every public filed-capture projection carries."""

    @property
    def captured_count(self) -> int:
        """Return how many observations were captured."""
        ...

    @property
    def reached_count(self) -> int:
        """Return how many units the capture reached."""
        ...

    @property
    def observation_paths(self) -> tuple[str, ...]:
        """Return the encrypted observation stores."""
        ...

    @property
    def artefact_refs(self) -> tuple[str, ...]:
        """Return the stored artefact references."""
        ...

    @property
    def justificante_metadata_count(self) -> int:
        """Return how many justificante metadata rows were enrolled."""
        ...

    @property
    def justificante_csvs(self) -> tuple[str, ...]:
        """Return the justificante CSV references."""
        ...

    @property
    def filing_evidence_stamped_count(self) -> int:
        """Return how many filing records were stamped with evidence."""
        ...

    @property
    def filing_record_ids(self) -> tuple[str, ...]:
        """Return the stamped filing record identifiers."""
        ...

    @property
    def filing_evidence_conflict_count(self) -> int:
        """Return how many filing records conflicted with captured evidence."""
        ...

    @property
    def filing_evidence_conflict_record_ids(self) -> tuple[str, ...]:
        """Return the conflicting filing record identifiers."""
        ...

    @property
    def evidence_notices(self) -> tuple[FiledCaptureNoticeV1, ...]:
        """Return the per-observation capture advisories."""
        ...

    @property
    def casilla_count(self) -> int:
        """Return how many casillas came back."""
        ...

    @property
    def calculation_observation_count(self) -> int:
        """Return how many calculation observations came back."""
        ...

    @property
    def calculation_observation_keys(self) -> tuple[str, ...]:
        """Return the calculation observation keys."""
        ...


class CaptureTallyFields(TypedDict):
    """The evidence tally fields every filed-capture report is constructed with."""

    captured_count: int
    reached_count: int
    observation_paths: tuple[str, ...]
    artefact_refs: tuple[str, ...]
    justificante_metadata_count: int
    justificante_csvs: tuple[str, ...]
    filing_evidence_stamped_count: int
    filing_record_ids: tuple[str, ...]
    filing_evidence_conflict_count: int
    filing_evidence_conflict_record_ids: tuple[str, ...]
    evidence_notices: tuple[Notice, ...]
    casilla_count: int
    calculation_observation_count: int
    calculation_observation_keys: tuple[str, ...]


def capture_tally_fields(projection: _CaptureTallyProjection) -> CaptureTallyFields:
    """Carry the shared evidence tally from a public projection into a report constructor."""
    return CaptureTallyFields(
        captured_count=projection.captured_count,
        reached_count=projection.reached_count,
        observation_paths=projection.observation_paths,
        artefact_refs=projection.artefact_refs,
        justificante_metadata_count=projection.justificante_metadata_count,
        justificante_csvs=projection.justificante_csvs,
        filing_evidence_stamped_count=projection.filing_evidence_stamped_count,
        filing_record_ids=projection.filing_record_ids,
        filing_evidence_conflict_count=projection.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=projection.filing_evidence_conflict_record_ids,
        evidence_notices=tuple(capture_notice(notice) for notice in projection.evidence_notices),
        casilla_count=projection.casilla_count,
        calculation_observation_count=projection.calculation_observation_count,
        calculation_observation_keys=projection.calculation_observation_keys,
    )


def _reconciliation_notice(notice: FiledReconciliationNoticeV1) -> FilingReconciliationNotice:
    return FilingReconciliationNotice(
        code=FilingReconciliationNoticeCode(notice.code),
        context=context_from_pairs(notice.context) or {},
    )


def reconciliation_result(row: FiledReconciliationV1, *, profile_id: UUID) -> FilingReconciliationResult:
    """Restore one filing-chain outcome, refusing another profile's row or an unknown basis."""
    if row.bucket_id != str(profile_id):
        raise ValueError("reconciliation does not match its profile")
    basis: FilingEvidenceBasis | None
    if row.evidence_basis == "casillas":
        basis = "casillas"
    elif row.evidence_basis == "receipt_totals":
        basis = "receipt_totals"
    elif row.evidence_basis is None:
        basis = None
    else:
        raise ValueError("reconciliation has an unknown evidence basis")
    return FilingReconciliationResult(
        outcome=FilingReconciliationOutcome(row.outcome),
        bucket_id=row.bucket_id,
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=Period.from_year_and_code(row.filing_year, row.period),
        member_nif=row.member_nif,
        filing_record_id=row.filing_record_id,
        affected_filing_record_ids=row.affected_filing_record_ids,
        differing_casilla_ids=tuple(validated_casilla_id(value) for value in row.differing_casilla_ids),
        evidence_basis=basis,
        notices=tuple(_reconciliation_notice(notice) for notice in row.notices),
    )


def capture_evidence_effect(report: FiledCaptureEvidenceTally) -> OperationEffect:
    """Return the effect a capture that persisted evidence must have settled with."""
    return (
        OperationEffect.UPDATED
        if report.captured_count or report.calculation_observation_count or report.filing_evidence_stamped_count
        else OperationEffect.NONE
    )


def settled_capture_report[ResultT: BaseModel, ReportT](
    completed: RegisteredOperationCompletion[ResultT],
    result_type: type[ResultT],
    restore: Callable[[ResultT], ReportT],
    expected_effect: Callable[[ReportT], OperationEffect],
) -> ReportT:
    """Restore the report only when its settled receipt agrees with what it reports.

    A provider session refresh can persist even when the capture itself writes
    nothing, so an updated receipt is accepted for a report that expects none.
    """
    try:
        projection = completed.projection
        if not isinstance(projection, result_type):
            raise ValueError("capture result projection has an invalid type")
        report = restore(projection)
        expected = expected_effect(report)
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or (
                completed.effect is not expected
                and not (expected is OperationEffect.NONE and completed.effect is OperationEffect.UPDATED)
            )
        ):
            raise ValueError("capture result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return report
