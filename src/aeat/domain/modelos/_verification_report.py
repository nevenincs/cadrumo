"""Structured verification report produced by ``aeat app modelo verify``.

A :class:`VerificationReport` is the decision artifact the verify
command persists for every run. It captures whether the target
calculation revision meets the ``verificado_completo`` contract,
which blocking findings prevent that transition, which inputs are
missing, which casillas are unresolved, which waivers were
accepted, and what the operator should do next.

The report is bucket-scoped and content-addressed by the parent
calculation revision plus the run timestamp. Failed verification
attempts produce a persisted report (so the audit trail explains
why a transition was refused) without mutating the target
revision.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, override

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ...core.hashing import content_hash_hex
from ._errors import ModeloValidationError
from ._ids import VerificationReportId

_HEX_64_PATTERN = r"^[0-9a-f]{64}$"

_ReportId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=64, max_length=64, pattern=_HEX_64_PATTERN),
]
_CalculationRevisionId = _ReportId
ModeloActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
"""Validated string identifying the operator who triggered a verification run.

Strips surrounding whitespace; must be 1–64 characters after stripping.
Used as ``verified_by`` on :class:`VerificationReport` to record the actor
label fed into the content-addressed id derivation.
"""
_FindingMessage = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
_CasillaRef = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class VerificationCompletenessStatus(StrEnum):
    """Top-level verdict from one verification run.

    * ``COMPLETE`` — every required input resolved, zero blocking
      findings. The revision transitions to ``VERIFICADO_COMPLETO``.
    * ``INCOMPLETE`` — required inputs missing or unresolved
      casillas remain. Soft refusal: operator can act on the
      missing-inputs list.
    * ``BLOCKED`` — blocking validation findings exist (e.g.
      reconciliation total mismatch over tolerance, schema
      violation). Hard refusal: operator must fix the finding
      before the revision can be verified.
    """

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


class ModeloVerificationFindingKind(StrEnum):
    """Closed catalogue of verification-finding kinds.

    Maps to the readiness vocabulary mandated by the verify ADR:
    bucket / ledger source / profile fact / prior filed revision /
    live observation / casilla / waiver / blocking finding.
    """

    MISSING_REQUIRED_CASILLA = "missing_required_casilla"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    UNRESOLVED_BINDING = "unresolved_binding"
    CROSS_PERIOD_DEPENDENCY_UNCLEAN = "cross_period_dependency_unclean"
    INVALID_WAIVER = "invalid_waiver"
    BLOCKING_RULE = "blocking_rule"
    ADVISORY = "advisory"


class ModeloVerificationFindingSeverity(StrEnum):
    """Severity of one verification finding."""

    BLOCKING = "blocking"
    WARNING = "warning"


class ModeloVerificationFinding(BaseModel):
    """One verification finding.

    Findings of ``BLOCKING`` severity force ``BLOCKED`` completeness
    status. ``WARNING`` severity findings surface in the report but
    do not block ``COMPLETE`` status on their own.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: _CasillaRef | None = None
    expectation_id: _CasillaRef | None = None
    message: _FindingMessage
    next_action: _FindingMessage | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


def derive_verification_report_id(
    *,
    calculation_revision_id: str,
    run_at: datetime,
    verified_by: str,
) -> str:
    """Deterministic 64-char SHA-256 id for a verification report."""
    payload = {
        "calculation_revision_id": calculation_revision_id.strip(),
        "run_at": run_at.isoformat(),
        "verified_by": verified_by.strip(),
    }
    return content_hash_hex(payload)


class VerificationReport(BaseModel):
    """Decision record of one verification run against a calculation revision.

    The id is content-addressed by ``calculation_revision_id``,
    ``run_at``, and ``verified_by`` via :func:`derive_verification_report_id`.
    A ``model_validator`` enforces the derivation on construction so
    no :class:`VerificationReport` can carry an inconsistent id.

    ``granted_verificado_completo`` is ``True`` if and only if
    ``completeness_status`` is ``COMPLETE`` and no blocking findings exist.
    The model validator enforces this invariant bidirectionally.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    verification_report_id: VerificationReportId
    calculation_revision_id: _CalculationRevisionId
    completeness_status: VerificationCompletenessStatus
    findings: tuple[ModeloVerificationFinding, ...] = Field(default_factory=tuple)
    resolved_casillas: tuple[_CasillaRef, ...] = Field(default_factory=tuple)
    missing_required_casillas: tuple[_CasillaRef, ...] = Field(default_factory=tuple)
    run_at: datetime
    verified_by: ModeloActorLabel
    granted_verificado_completo: bool

    @model_validator(mode="after")
    def _enforce_invariants(self) -> VerificationReport:
        derived = derive_verification_report_id(
            calculation_revision_id=self.calculation_revision_id,
            run_at=self.run_at,
            verified_by=self.verified_by,
        )
        if derived != self.verification_report_id:
            raise ModeloValidationError(
                f"verification_report_id {self.verification_report_id!r} does not match the derived id {derived!r}",
            )
        # granted_verificado_completo is a True iff completeness_status is COMPLETE
        # AND no blocking findings exist.
        has_blocking = any(finding.severity is ModeloVerificationFindingSeverity.BLOCKING for finding in self.findings)
        if self.granted_verificado_completo:
            if self.completeness_status is not VerificationCompletenessStatus.COMPLETE:
                raise ModeloValidationError("granted_verificado_completo=True requires completeness_status=COMPLETE")
            if has_blocking:
                raise ModeloValidationError("granted_verificado_completo=True requires no blocking findings")
        else:
            if self.completeness_status is VerificationCompletenessStatus.COMPLETE and not has_blocking:
                raise ModeloValidationError(
                    "completeness_status=COMPLETE with no blocking findings must set granted_verificado_completo=True",
                )
        # Required-casilla sets must be disjoint from resolved.
        overlap = set(self.resolved_casillas) & set(self.missing_required_casillas)
        if overlap:
            raise ModeloValidationError(f"casillas cannot be both resolved and missing: {sorted(overlap)!r}")
        return self


class VerificationReportCatalogue(BaseModel):
    """Immutable catalogue of every verification report in a bucket's storage.

    Keyed by ``verification_report_id``; the model validator enforces that
    every key equals the id of the :class:`VerificationReport` it maps to.
    Iteration yields :class:`VerificationReport` values (not key–value
    pairs), which diverges from the standard ``Mapping`` contract — the
    override is annotated with a suppression comment on
    ``__iter__``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    reports: Mapping[str, VerificationReport] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_keys_match(self) -> VerificationReportCatalogue:
        for key, report in self.reports.items():
            if key != report.verification_report_id:
                raise ModeloValidationError(
                    f"catalogue key {key!r} does not match verification_report_id {report.verification_report_id!r}",
                )
        return self

    def get(self, verification_report_id: str) -> VerificationReport | None:
        """Return the :class:`VerificationReport` for ``verification_report_id``, or ``None``."""
        return self.reports.get(verification_report_id)

    def for_calculation_revision(self, calculation_revision_id: str) -> tuple[VerificationReport, ...]:
        """Return every :class:`VerificationReport` against one calculation revision, ordered by run_at."""
        matching = tuple(r for r in self.reports.values() if r.calculation_revision_id == calculation_revision_id)
        return tuple(sorted(matching, key=lambda r: r.run_at))

    def values(self):
        """Return a view of all :class:`VerificationReport` values in the catalogue."""
        return self.reports.values()

    @override
    def __iter__(self) -> Iterator[VerificationReport]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional pydantic catalogue iteration shim — yields domain items not field-value tuples
        """Iterate over :class:`VerificationReport` values (not ``(key, value)`` pairs)."""
        return iter(self.reports.values())

    def __len__(self) -> int:
        """Return the number of reports in the catalogue."""
        return len(self.reports)


__all__ = [
    "ModeloVerificationFinding",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "VerificationCompletenessStatus",
    "VerificationReport",
    "VerificationReportCatalogue",
    "derive_verification_report_id",
]
