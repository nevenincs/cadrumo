"""Structured verification report produced by ``aeat app modelo work verify``.

A :class:`VerificationReport` is the decision artifact the verify
command persists for every run. It captures whether the target
calculation :class:`CalculationRevision` meets the
``verificado_completo`` contract,
which blocking findings prevent that transition, which inputs are
missing, which :class:`CasillaId` identifiers are unresolved, which
waivers were accepted, and the factual reason the verification outcome was
granted or refused.

The report is bucket-scoped and content-addressed by the
verification outcome (parent calculation revision, completeness
status, findings, and actor); the run timestamp is a non-identity
last-seen body field. Failed verification attempts produce a
persisted report (so the audit trail explains why a transition was
refused) without mutating the target revision, and an identical-outcome
retry collapses onto the same report rather than accumulating.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, override

from pydantic import BaseModel, Field, StringConstraints, field_serializer, field_validator, model_validator

from cadrumo.domain.calculations.registry.ids import LegalRefId, SourceRefId, VerificationExpectationId

from ...core import STRICT_FROZEN_CONFIG, CasillaId, OperatorActionAxis
from ...core.hashing import content_hash_hex
from ...core.identity import CalculationRevisionId, VerificationReportId
from ...core.time import validate_utc_aware
from .errors import ModeloValidationError

ModeloActorLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]
"""Validated string identifying the operator who triggered a verification run.

Strips surrounding whitespace; must be 1–64 characters after stripping.
Used as ``verified_by`` on :class:`VerificationReport` to record the actor
label fed into the content-addressed id derivation.
"""
_LOCALE_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$"
_FACT_KEY_PATTERN = r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$"
_PRESENTATION_FACT_TOKENS = frozenset(
    {
        "action",
        "command",
        "help",
        "hint",
        "instruction",
        "label",
        "message",
        "next",
        "prose",
        "remediation",
        "suggestion",
        "text",
        "title",
    },
)
_FindingLocaleKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=200, pattern=_LOCALE_KEY_PATTERN),
]
_FindingFactValue = str | int | bool | Decimal


def _is_presentation_fact_key(key: str) -> bool:
    """Return whether a fact key attempts to smuggle presentation semantics."""
    return any(token in _PRESENTATION_FACT_TOKENS for token in re.split(r"[._]", key))


def _is_blank_or_spaced_string_fact(item: _FindingFactValue) -> bool:
    """Return whether a string fact is blank or carries whitespace.

    Non-string facts are never rejected here; a string fact must be a non-blank
    locale-neutral token, so any internal or surrounding whitespace disqualifies it.
    """
    if not isinstance(item, str):
        return False
    return not item or item != item.strip() or any(ch.isspace() for ch in item)


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

    Covers the readiness vocabulary: bucket / ledger source / profile
    fact / prior filed revision / live observation / casilla / waiver /
    blocking finding.
    """

    MISSING_REQUIRED_CASILLA = "missing_required_casilla"
    RECONCILIATION_MISMATCH = "reconciliation_mismatch"
    CROSS_PERIOD_DEPENDENCY_UNCLEAN = "cross_period_dependency_unclean"
    BLOCKING_RULE = "blocking_rule"
    ADVISORY = "advisory"


OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND: Mapping[
    ModeloVerificationFindingKind,
    OperatorActionAxis,
] = MappingProxyType(
    {
        ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        ModeloVerificationFindingKind.RECONCILIATION_MISMATCH: OperatorActionAxis.RESOLVE_VALUE_DIVERGENCE,
        ModeloVerificationFindingKind.CROSS_PERIOD_DEPENDENCY_UNCLEAN: OperatorActionAxis.FILE_PRIOR_PERIOD,
        ModeloVerificationFindingKind.BLOCKING_RULE: OperatorActionAxis.SUPPLY_MANUAL_INPUT,
        ModeloVerificationFindingKind.ADVISORY: OperatorActionAxis.REVIEW_ADVISORY,
    },
)
"""Total coarse action spine for verification findings.

The finding kind remains present beside this projection.  More precise native
facts, such as a cross-period blocker code in ``message_facts``, may refine the
operator action downstream; this table never replaces or discards them.
"""

if set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND) != set(ModeloVerificationFindingKind):
    missing = sorted(
        finding_kind.value
        for finding_kind in set(ModeloVerificationFindingKind)
        - set(OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND)
    )
    raise RuntimeError(
        f"every ModeloVerificationFindingKind must declare an OperatorActionAxis; missing={missing}",
    )


class ModeloVerificationFindingSeverity(StrEnum):
    """Severity of one verification finding."""

    BLOCKING = "blocking"
    WARNING = "warning"


class ModeloVerificationFinding(BaseModel):
    """One verification finding.

    Findings of ``BLOCKING`` severity force ``BLOCKED`` completeness
    status. ``WARNING`` severity findings surface in the report but
    do not block ``COMPLETE`` status on their own.

    A finding may point at the affected :class:`CasillaId`, the registry
    :class:`VerificationExpectationId` that raised it, and the
    :class:`LegalRefId` / :class:`SourceRefId` provenance that grounds the
    locale-neutral finding identity.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: ModeloVerificationFindingKind
    severity: ModeloVerificationFindingSeverity
    casilla_id: CasillaId | None = None
    expectation_id: VerificationExpectationId | None = None
    message_locale_key: _FindingLocaleKey
    message_facts: Mapping[str, _FindingFactValue] = Field(default_factory=dict)
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = ()

    @field_validator("message_facts")
    @classmethod
    def _freeze_message_facts(
        cls,
        value: Mapping[str, _FindingFactValue],
    ) -> Mapping[str, _FindingFactValue]:
        """Admit deterministic typed facts, never prose or rendering instructions."""
        if any(not re.fullmatch(_FACT_KEY_PATTERN, key) for key in value):
            raise ValueError("verification finding fact keys must be stable identifiers")
        if any(_is_presentation_fact_key(key) for key in value):
            raise ValueError("verification finding facts cannot carry presentation semantics")
        if any(_is_blank_or_spaced_string_fact(item) for item in value.values()):
            raise ValueError("verification finding string facts must be non-blank locale-neutral tokens")
        return MappingProxyType(dict(sorted(value.items())))

    @field_serializer("message_facts")
    def _serialize_message_facts(
        self,
        value: Mapping[str, _FindingFactValue],
    ) -> dict[str, _FindingFactValue]:
        """Serialize the immutable fact map as a deterministic JSON object."""
        return dict(value)


def derive_verification_report_id(
    *,
    calculation_revision_id: CalculationRevisionId,
    completeness_status: VerificationCompletenessStatus,
    findings: tuple[ModeloVerificationFinding, ...],
    verified_by: str,
) -> str:
    """Deterministic 64-char SHA-256 id for a verification report.

    Content-addressed by the verification *outcome* - the parent
    :class:`CalculationRevision` id, the ``completeness_status``, the ordered
    ``findings`` tuple, and the ``verified_by`` actor. ``run_at`` is
    deliberately excluded from the identity so two retries of an
    identical-outcome verify collapse to one report on upsert (the id is
    clock-free); a re-verify whose findings change produces a new distinct
    report, the audit-meaningful granularity.
    """
    payload = {
        "calculation_revision_id": calculation_revision_id.strip(),
        "completeness_status": completeness_status.value,
        "findings": [finding.model_dump(mode="json") for finding in findings],
        "verified_by": verified_by.strip(),
    }
    return content_hash_hex(payload)


class VerificationReport(BaseModel):
    """Decision record of one verification run against a :class:`CalculationRevision`.

    The id is content-addressed by the verification outcome
    (``calculation_revision_id``, ``completeness_status``, ``findings``,
    and ``verified_by``) via :func:`derive_verification_report_id`;
    ``run_at`` is a non-identity last-seen timestamp. A ``model_validator``
    enforces the derivation on construction so no
    :class:`VerificationReport` can carry an inconsistent id.

    ``granted_verificado_completo`` is ``True`` if and only if
    ``completeness_status`` is ``COMPLETE`` and no blocking findings exist.
    The model validator enforces this invariant bidirectionally.
    """

    model_config = STRICT_FROZEN_CONFIG

    verification_report_id: VerificationReportId
    calculation_revision_id: CalculationRevisionId
    completeness_status: VerificationCompletenessStatus
    findings: tuple[ModeloVerificationFinding, ...] = Field(default_factory=tuple)
    resolved_casilla_ids: tuple[CasillaId, ...] = Field(default_factory=tuple)
    missing_required_casilla_ids: tuple[CasillaId, ...] = Field(default_factory=tuple)
    run_at: datetime
    verified_by: ModeloActorLabel
    granted_verificado_completo: bool

    @field_validator("run_at")
    @classmethod
    def _run_at_is_utc(cls, value: datetime) -> datetime:
        """Reject naive and non-UTC verification instants at the model boundary."""
        return validate_utc_aware(value)

    @model_validator(mode="after")
    def _enforce_invariants(self) -> VerificationReport:
        derived = derive_verification_report_id(
            calculation_revision_id=self.calculation_revision_id,
            completeness_status=self.completeness_status,
            findings=self.findings,
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
        overlap = set(self.resolved_casilla_ids) & set(self.missing_required_casilla_ids)
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

    model_config = STRICT_FROZEN_CONFIG

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

    def for_calculation_revision(
        self,
        calculation_revision_id: CalculationRevisionId,
    ) -> tuple[VerificationReport, ...]:
        """Return every :class:`VerificationReport` against one calculation revision, ordered by run_at."""
        matching = tuple(r for r in self.reports.values() if r.calculation_revision_id == calculation_revision_id)
        return tuple(sorted(matching, key=lambda r: r.run_at))

    def values(self):
        """Return a view of all :class:`VerificationReport` values in the catalogue."""
        return self.reports.values()

    @override
    def __iter__(self) -> Iterator[VerificationReport]:  # pyright: ignore[reportIncompatibleMethodOverride]  # ty: ignore[invalid-method-override]  # pyrefly: ignore[bad-override]  # reason: intentional Pydantic catalogue iteration adapter; the established public API yields VerificationReport records, not BaseModel field-value tuples
        """Iterate over :class:`VerificationReport` values (not ``(key, value)`` pairs)."""
        return iter(self.reports.values())

    def __len__(self) -> int:
        """Return the number of reports in the catalogue."""
        return len(self.reports)


__all__ = [
    "OPERATOR_ACTION_BY_MODELO_VERIFICATION_FINDING_KIND",
    "ModeloVerificationFinding",
    "ModeloVerificationFindingKind",
    "ModeloVerificationFindingSeverity",
    "VerificationCompletenessStatus",
    "VerificationReport",
    "VerificationReportCatalogue",
    "derive_verification_report_id",
]
