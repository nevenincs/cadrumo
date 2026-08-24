"""Derived cross-authority closure report for the shipped registry.

This dev-side projection joins the three application-owned closure authorities.
It does not reinterpret registry, source-connectivity, or export evidence:
those facts are composed in ``cadrumo.application.registry`` and this module
only makes their common release predicate explicit, deterministic, and
blocking.

The temporal report is the canonical revision denominator.  A missing source
or filing limb is therefore reported against the affected temporal coordinate;
an extra limb remains visible as a top-level join disagreement.  Neither shape
can be mistaken for a satisfied release condition.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, Field, computed_field, model_validator

from cadrumo.application.registry import (
    FilingExportCoverageReport,
    FilingExportProofAuthority,
    RegistryClosureLimb,
    RegistryClosureLimbName,
    RegistryClosureOwnerDisposition,
    SourceConnectivityCoverageReport,
    TemporalCoverageReport,
    TemporalRevisionCoverage,
    compose_filing_export_coverage,
    compose_source_connectivity_coverage,
    compose_temporal_coverage,
    load_source_connectivity_census,
)
from cadrumo.core import STRICT_FROZEN_CONFIG, SourceConnectivityProofAuthority
from cadrumo.domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority

__all__ = [
    "RegistryClosureJoinDisagreement",
    "RegistryClosurePredicateRefusal",
    "RegistryClosureReleaseResult",
    "RegistryClosureReport",
    "RegistryClosureRevisionReport",
    "build_registry_closure_report",
    "check_registry_closure_release",
    "load_registry_closure_report",
    "render_registry_closure_report",
]

type RegistryClosurePredicateOutcome = Literal["satisfied", "refused"]
type RegistryClosureJoinDisagreementKind = Literal["missing_from_limb", "unexpected_limb_coordinate"]
type RegistryClosurePredicateRefusalReason = Literal[
    "below_filing_grade",
    "conflicting_evidence",
    "cross_limb_disagreement",
    "missing_evidence",
    "scope_inadequate_evidence",
    "stale_evidence",
    "unreviewed_evidence",
    "unmeasured",
    "law_selection_refused",
    "selected_revision_mismatch",
    "undeclared_authority_grade",
    "declared_grade_snapshot_refused",
    "snapshot_revision_mismatch",
]

_TEMPORAL_WORK_ITEMS: Final[dict[str, str]] = {
    "law_selection_refused": "registry-temporal-coverage:law-selection",
    "selected_revision_mismatch": "registry-temporal-coverage:law-selection",
    "undeclared_authority_grade": "registry-temporal-coverage:authority-grade",
    "declared_grade_snapshot_refused": "registry-temporal-coverage:authority-grade",
    "snapshot_revision_mismatch": "registry-temporal-coverage:authority-grade",
}


class _ClosureReportModel(BaseModel):
    """Strict frozen base for dev-side closure-report records."""

    model_config = STRICT_FROZEN_CONFIG


class RegistryClosureJoinDisagreement(_ClosureReportModel):
    """One source or filing projection that cannot join the temporal denominator."""

    modelo: str = Field(min_length=1, max_length=32)
    revision: str = Field(min_length=1, max_length=128)
    limb: Literal["source_connectivity", "filing_export"]
    kind: RegistryClosureJoinDisagreementKind
    detail: str = Field(min_length=1, max_length=1_024)


class RegistryClosurePredicateRefusal(_ClosureReportModel):
    """One accountable reason a predicate limb prevents release."""

    limb: RegistryClosureLimbName
    reason: RegistryClosurePredicateRefusalReason
    detail: str = Field(min_length=1, max_length=1_024)
    disposition: RegistryClosureOwnerDisposition

    @model_validator(mode="after")
    def _require_matching_disposition_limb(self) -> RegistryClosurePredicateRefusal:
        if self.disposition.limb != self.limb:
            raise ValueError("closure predicate refusal disposition must name its refusal limb")
        return self


class RegistryClosureRevisionReport(_ClosureReportModel):
    """The three closure limbs and release outcome for one registered revision."""

    modelo: str = Field(min_length=1, max_length=32)
    revision: str = Field(min_length=1, max_length=128)
    temporal_coverage: TemporalRevisionCoverage
    source_connectivity: RegistryClosureLimb | None = None
    filing_export: RegistryClosureLimb | None = None
    join_disagreements: tuple[RegistryClosureJoinDisagreement, ...] = ()

    @model_validator(mode="after")
    def _require_exact_coordinate_and_limb_identity(self) -> RegistryClosureRevisionReport:
        coordinate = (self.modelo, self.revision)
        if (str(self.temporal_coverage.modelo), str(self.temporal_coverage.revision)) != coordinate:
            raise ValueError("temporal coverage coordinate must match its closure-report row")
        expected = (
            ("source_connectivity", self.source_connectivity),
            ("filing_export", self.filing_export),
        )
        for name, limb in expected:
            disagreements = tuple(item for item in self.join_disagreements if item.limb == name)
            if limb is None:
                if len(disagreements) != 1 or disagreements[0].kind != "missing_from_limb":
                    raise ValueError(f"missing {name} limb requires one missing-from-limb disagreement")
                continue
            if (str(limb.modelo), str(limb.revision)) != coordinate or limb.name != name:
                raise ValueError(f"{name} limb coordinate must match its closure-report row")
            if disagreements:
                raise ValueError(f"present {name} limb cannot carry a join disagreement")
        if any((item.modelo, item.revision) != coordinate for item in self.join_disagreements):
            raise ValueError("closure-report row disagreement must name the enclosing coordinate")
        return self

    @computed_field
    @property
    def refusals(self) -> tuple[RegistryClosurePredicateRefusal, ...]:
        """Project every unsatisfied predicate limb without hiding its owner."""
        refusals: list[RegistryClosurePredicateRefusal] = []
        if self.temporal_coverage.status != "validated":
            refusals.append(_temporal_refusal(self.temporal_coverage))
        refusals.extend(
            _limb_or_join_refusal(
                limb_name="source_connectivity",
                limb=self.source_connectivity,
                disagreements=self.join_disagreements,
            ),
        )
        refusals.extend(
            _limb_or_join_refusal(
                limb_name="filing_export",
                limb=self.filing_export,
                disagreements=self.join_disagreements,
            ),
        )
        return tuple(refusals)

    @computed_field
    @property
    def predicate_outcome(self) -> RegistryClosurePredicateOutcome:
        """Return satisfied only when all three release limbs are satisfied."""
        return "satisfied" if not self.refusals else "refused"


class RegistryClosureReport(_ClosureReportModel):
    """Complete, fail-closed cross-authority release projection."""

    as_of: date
    registry_validated: Literal[True] = True
    rows: tuple[RegistryClosureRevisionReport, ...] = Field(min_length=1)
    join_disagreements: tuple[RegistryClosureJoinDisagreement, ...] = ()

    @model_validator(mode="after")
    def _require_complete_deterministic_join(self) -> RegistryClosureReport:
        coordinates = tuple((row.modelo, row.revision) for row in self.rows)
        if len(coordinates) != len(set(coordinates)):
            raise ValueError("registry closure report must contain one row per temporal revision coordinate")
        if coordinates != tuple(sorted(coordinates)):
            raise ValueError("registry closure report rows must be sorted by modelo and revision")
        expected_row_disagreements = tuple(
            disagreement for row in self.rows for disagreement in row.join_disagreements
        )
        report_missing_limb_disagreements = tuple(
            item for item in self.join_disagreements if item.kind == "missing_from_limb"
        )
        if report_missing_limb_disagreements != expected_row_disagreements:
            raise ValueError("registry closure report must retain every row-level join disagreement in row order")
        if self.join_disagreements != tuple(
            sorted(
                self.join_disagreements,
                key=lambda item: (item.modelo, item.revision, item.limb, item.kind),
            )
        ):
            raise ValueError("registry closure report join disagreements must be deterministically ordered")
        return self

    @computed_field
    @property
    def satisfied_revision_count(self) -> int:
        """Count temporal-denominator revisions satisfying all predicate limbs."""
        return sum(row.predicate_outcome == "satisfied" for row in self.rows)

    @computed_field
    @property
    def refused_revision_count(self) -> int:
        """Count visible temporal-denominator revisions that block release."""
        return len(self.rows) - self.satisfied_revision_count

    @computed_field
    @property
    def refusal_reason_census(self) -> dict[str, int]:
        """Count each visible predicate refusal reason in stable key order."""
        counts: dict[str, int] = {}
        for refusal in (refusal for row in self.rows for refusal in row.refusals):
            counts[refusal.reason] = counts.get(refusal.reason, 0) + 1
        return dict(sorted(counts.items()))

    @computed_field
    @property
    def release_eligible(self) -> bool:
        """Return the blocking release predicate over all registered revisions."""
        return not self.join_disagreements and self.refused_revision_count == 0


class RegistryClosureReleaseResult(_ClosureReportModel):
    """The release-gate verdict over a derived closure report."""

    report: RegistryClosureReport

    @computed_field
    @property
    def passed(self) -> bool:
        """Whether this exact cross-authority report permits a completeness claim."""
        return self.report.release_eligible

    @computed_field
    @property
    def blocking_reason_count(self) -> int:
        """Count every revision refusal and every denominator disagreement."""
        return sum(len(row.refusals) for row in self.report.rows) + len(self.report.join_disagreements)


def build_registry_closure_report(
    *,
    temporal_coverage: TemporalCoverageReport,
    source_connectivity: SourceConnectivityCoverageReport,
    filing_export: FilingExportCoverageReport,
    as_of: date,
) -> RegistryClosureReport:
    """Join application-owned limbs into the one fail-closed release report.

    ``temporal_coverage`` defines the law-selectable revision denominator.  The
    other reports may never shrink that denominator: a missing limb becomes a
    row-level disagreement and an unexpected limb remains a top-level
    disagreement.  The release predicate therefore stays false in either case.
    """
    source_by_coordinate = {(str(limb.modelo), str(limb.revision)): limb for limb in source_connectivity.limbs}
    filing_by_coordinate = {(str(limb.modelo), str(limb.revision)): limb for limb in filing_export.limbs}
    temporal_rows = tuple(
        sorted(temporal_coverage.rows, key=lambda row: (str(row.modelo), str(row.revision))),
    )
    temporal_coordinates = {(str(row.modelo), str(row.revision)) for row in temporal_rows}
    row_disagreements: list[RegistryClosureJoinDisagreement] = []
    rows: list[RegistryClosureRevisionReport] = []
    for temporal in temporal_rows:
        coordinate = (str(temporal.modelo), str(temporal.revision))
        source_limb = source_by_coordinate.get(coordinate)
        filing_limb = filing_by_coordinate.get(coordinate)
        disagreements: list[RegistryClosureJoinDisagreement] = []
        if source_limb is None:
            disagreements.append(_missing_limb_disagreement(coordinate=coordinate, limb="source_connectivity"))
        if filing_limb is None:
            disagreements.append(_missing_limb_disagreement(coordinate=coordinate, limb="filing_export"))
        row_disagreements.extend(disagreements)
        rows.append(
            RegistryClosureRevisionReport(
                modelo=coordinate[0],
                revision=coordinate[1],
                temporal_coverage=temporal,
                source_connectivity=source_limb,
                filing_export=filing_limb,
                join_disagreements=tuple(disagreements),
            ),
        )
    extra_disagreements = [
        _unexpected_limb_disagreement(coordinate=coordinate, limb="source_connectivity")
        for coordinate in source_by_coordinate
        if coordinate not in temporal_coordinates
    ]
    extra_disagreements.extend(
        _unexpected_limb_disagreement(coordinate=coordinate, limb="filing_export")
        for coordinate in filing_by_coordinate
        if coordinate not in temporal_coordinates
    )
    disagreements = tuple(
        sorted(
            (*row_disagreements, *extra_disagreements),
            key=lambda item: (item.modelo, item.revision, item.limb, item.kind),
        ),
    )
    # Each row already owns its missing-limb disagreement.  Align the report's
    # authoritative sequence with the same deterministic ordering before model
    # validation, rather than relying on construction order.
    rows = [
        row.model_copy(
            update={
                "join_disagreements": tuple(
                    item
                    for item in disagreements
                    if item.kind == "missing_from_limb" and (item.modelo, item.revision) == (row.modelo, row.revision)
                ),
            },
        )
        for row in rows
    ]
    return RegistryClosureReport(as_of=as_of, rows=tuple(rows), join_disagreements=disagreements)


def load_registry_closure_report(
    *,
    as_of: date | None = None,
    registry_authority: ValidatedRegistryAuthority | None = None,
    source_proof_authority: SourceConnectivityProofAuthority | None = None,
    filing_proof_authority: FilingExportProofAuthority | None = None,
) -> RegistryClosureReport:
    """Compose the bundled registry's closure report from current evidence.

    Proof authorities are explicit injectable ports.  Passing neither never
    creates a success claim: connected source rows and filing-grade exports
    retain their application-owned missing-evidence refusals.  A release caller
    that has live proof authorities can supply them to this same single join.
    """
    authority = bundled_authority() if registry_authority is None else registry_authority
    resolved_as_of = date.today() if as_of is None else as_of
    return build_registry_closure_report(
        temporal_coverage=compose_temporal_coverage(authority=authority),
        source_connectivity=compose_source_connectivity_coverage(
            authority=authority,
            census=load_source_connectivity_census(proof_authority=source_proof_authority),
            as_of=resolved_as_of,
            proof_authority=source_proof_authority,
        ),
        filing_export=compose_filing_export_coverage(
            authority=authority,
            proof_authority=filing_proof_authority,
        ),
        as_of=resolved_as_of,
    )


def check_registry_closure_release(report: RegistryClosureReport) -> RegistryClosureReleaseResult:
    """Evaluate the blocking release predicate over one already-derived report."""
    return RegistryClosureReleaseResult(report=report)


def render_registry_closure_report(report: RegistryClosureReport) -> str:
    """Render the release projection as deterministic greppable rows."""
    verdict = check_registry_closure_release(report)
    lines = [
        _kv_line(
            "closure",
            as_of=report.as_of.isoformat(),
            registry_validated=report.registry_validated,
            release_eligible=verdict.passed,
            revisions=len(report.rows),
            satisfied_revisions=report.satisfied_revision_count,
            refused_revisions=report.refused_revision_count,
            join_disagreements=len(report.join_disagreements),
            blocking_reasons=verdict.blocking_reason_count,
        ),
    ]
    lines.extend(
        _kv_line(
            "closure_row",
            modelo=row.modelo,
            revision=row.revision,
            predicate_outcome=row.predicate_outcome,
            temporal_status=row.temporal_coverage.status,
            temporal_failure_code=row.temporal_coverage.failure_code,
            source_outcome=None if row.source_connectivity is None else row.source_connectivity.outcome,
            filing_outcome=None if row.filing_export is None else row.filing_export.outcome,
            refusal_count=len(row.refusals),
        )
        for row in report.rows
    )
    lines.extend(
        _kv_line(
            "closure_refusal",
            modelo=row.modelo,
            revision=row.revision,
            limb=refusal.limb,
            reason=refusal.reason,
            owner=refusal.disposition.owner,
            work_item=refusal.disposition.work_item,
            reconsideration_condition=refusal.disposition.reconsideration_condition,
            detail=refusal.detail,
        )
        for row in report.rows
        for refusal in row.refusals
    )
    lines.extend(
        _kv_line(
            "closure_join_disagreement",
            modelo=item.modelo,
            revision=item.revision,
            limb=item.limb,
            kind=item.kind,
            detail=item.detail,
        )
        for item in report.join_disagreements
    )
    lines.extend(
        _kv_line("closure_refusal_reason", reason=reason, count=count)
        for reason, count in report.refusal_reason_census.items()
    )
    lines.append("note release_eligible=true requires every temporal denominator revision to satisfy every limb")
    return "\n".join(lines)


def _temporal_refusal(coverage: TemporalRevisionCoverage) -> RegistryClosurePredicateRefusal:
    """Translate a typed temporal refusal without discarding its specific code."""
    assert coverage.failure_code is not None
    assert coverage.failure_detail is not None
    work_item = _TEMPORAL_WORK_ITEMS[coverage.failure_code]
    return RegistryClosurePredicateRefusal(
        limb="temporal_coverage",
        reason=coverage.failure_code,
        detail=coverage.failure_detail,
        disposition=RegistryClosureOwnerDisposition(
            limb="temporal_coverage",
            state="blocked",
            owner="registry-temporal-coverage",
            work_item=work_item,
            reconsideration_condition=(
                "Revalidate the exact law-selected revision and its declared authority-grade snapshot."
            ),
        ),
    )


def _limb_or_join_refusal(
    *,
    limb_name: Literal["source_connectivity", "filing_export"],
    limb: RegistryClosureLimb | None,
    disagreements: tuple[RegistryClosureJoinDisagreement, ...],
) -> tuple[RegistryClosurePredicateRefusal, ...]:
    """Return the application refusal, or a visible join refusal when absent."""
    if limb is None:
        disagreement = next(item for item in disagreements if item.limb == limb_name)
        return (
            RegistryClosurePredicateRefusal(
                limb=limb_name,
                reason="cross_limb_disagreement",
                detail=disagreement.detail,
                disposition=RegistryClosureOwnerDisposition(
                    limb=limb_name,
                    state="blocked",
                    owner="registry-completeness-closure",
                    work_item="registry-completeness-closure:cross-authority-join",
                    reconsideration_condition=(
                        "Compose one exact closure limb for this temporal denominator coordinate."
                    ),
                ),
            ),
        )
    if limb.outcome == "satisfied":
        return ()
    assert limb.refusal is not None
    return (
        RegistryClosurePredicateRefusal(
            limb=limb_name,
            reason=limb.refusal.reason,
            detail=limb.refusal.detail,
            disposition=limb.refusal.disposition,
        ),
    )


def _missing_limb_disagreement(
    *,
    coordinate: tuple[str, str],
    limb: Literal["source_connectivity", "filing_export"],
) -> RegistryClosureJoinDisagreement:
    """Name a missing limb against the law-selected temporal denominator."""
    return RegistryClosureJoinDisagreement(
        modelo=coordinate[0],
        revision=coordinate[1],
        limb=limb,
        kind="missing_from_limb",
        detail=f"{limb} projection has no limb for this temporal denominator coordinate",
    )


def _unexpected_limb_disagreement(
    *,
    coordinate: tuple[str, str],
    limb: Literal["source_connectivity", "filing_export"],
) -> RegistryClosureJoinDisagreement:
    """Retain a limb coordinate outside the temporal release denominator."""
    return RegistryClosureJoinDisagreement(
        modelo=coordinate[0],
        revision=coordinate[1],
        limb=limb,
        kind="unexpected_limb_coordinate",
        detail=f"{limb} projection names a coordinate absent from temporal coverage",
    )


def _kv_line(record: str, **fields: object) -> str:
    """Render one closure record without relying on manager-private helpers."""
    return " ".join((record, *(f"{key}={_render_value(value)}" for key, value in fields.items())))


def _render_value(value: object) -> str:
    """Keep absent fields distinct from literal strings and numeric zeroes."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if not text or any(character in text for character in ' \t"='):
        return json.dumps(text)
    return text
