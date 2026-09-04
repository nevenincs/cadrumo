"""The typed, freshness-bound Ledger backend/CLI/TUI capability matrix.

The matrix is a reviewed campaign ledger, not a collection of optimistic
statuses. It binds rows to accepted and current denominator censuses, keeps
applicability separate from implementation and proof, and admits evidence only
when its role and subject snapshot are current.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, model_validator

SCHEMA_VERSION: Final[int] = 3
_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
_CAPABILITY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^ledger(?:\.[a-z][a-z0-9_]*)(?:\.[a-z][a-z0-9_]*)*$")
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^evidence\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_FINDING_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^finding\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_SUBJECT_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^subject\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_CENSUS_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^census\.ledger(?:\.[a-z][a-z0-9_]*)*$")
_ATTESTATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^attestation\.ledger(?:\.[a-z][a-z0-9_]*)*$")
_PLACEHOLDER_TEXT: Final[frozenset[str]] = frozenset({"", "n/a", "na", "none", "tbd", "todo", "unknown", "unmeasured"})
ACCEPTED_LEDGER_PARITY_PLAN_OWNER: Final[str] = "clitui-ledger"


class LedgerCapabilityAxis(StrEnum):
    """The independent backend, surface, and proof axes."""

    BACKEND = "backend"
    CLI = "cli"
    TUI = "tui"
    COMPOSITION = "composition"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"
    PROOF = "proof"


class ApplicabilityState(StrEnum):
    """Whether one axis applies to a Ledger capability."""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class AxisProofState(StrEnum):
    """The evidence maturity of an applicable axis."""

    NOT_APPLICABLE = "not_applicable"
    UNPROVEN = "unproven"
    PARTIAL = "partial"
    PROVEN = "proven"


class SurfaceCapabilityState(StrEnum):
    """The observed implementation state of a surface axis."""

    NOT_APPLICABLE = "not_applicable"
    ABSENT = "absent"
    PARTIAL = "partial"
    PROVEN = "proven"


class CapabilityAnnotation(StrEnum):
    """Ownership and reachability facts that must not substitute for proof."""

    CLI_OWNED = "cli_owned"
    DELEGATING = "delegating"
    COMPONENT_ONLY = "component_only"
    INSTALLED = "installed"


class InitialCliOwnership(StrEnum):
    """Immutable ownership captured at the first denominator review."""

    NOT_CLI_OWNED = "not_cli_owned"
    CLI_OWNED = "cli_owned"


class LedgerGapClass(StrEnum):
    """The closed taxonomy of unresolved Ledger gaps."""

    AUTHORITY = "authority"
    PRODUCT = "product"
    COMPOSITION = "composition"
    PROOF = "proof"
    REACHABILITY = "reachability"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"


class DenominatorSourceKind(StrEnum):
    """The mandatory input streams of the union denominator."""

    CLI_ENDPOINT = "cli_endpoint"
    CLI_SUBOPERATION = "cli_suboperation"
    BACKEND_ONLY = "backend_only"
    MISSING_PRODUCT = "missing_product"
    REGISTRY_ROUTE = "registry_route"
    ARTIFACT_PRODUCT = "artifact_product"
    SUPPORTED_SURFACE = "supported_surface"


class ReviewRuling(StrEnum):
    """The closed independent-review decision vocabulary."""

    ACCEPT = "accept"
    ACCEPT_WITH_REQUIRED_CHANGES = "accept_with_required_changes"
    REJECT = "reject"


class EvidenceKind(StrEnum):
    """The durable source form of a cited evidence coordinate."""

    CODE = "code"
    TEST = "test"
    COMMAND = "command"
    ARTIFACT = "artifact"
    REVIEW = "review"
    REFERENCE = "reference"


class EvidenceRole(StrEnum):
    """The precise conclusion evidence is allowed to support."""

    APPLICABILITY_REVIEW = "applicability_review"
    BASELINE = "baseline"
    DIRECT_BACKEND_BEHAVIOR = "direct_backend_behavior"
    ADAPTER_DETECTOR = "adapter_detector"
    CLI_SUCCESS = "cli_success"
    CLI_REFUSAL = "cli_refusal"
    CLI_ARTIFACT = "cli_artifact"
    TUI_PARITY = "tui_parity"
    TUI_REACHABILITY = "tui_reachability"
    MATRIX_PUBLICATION = "matrix_publication"
    INDEPENDENT_ENGINEERING_REVIEW = "independent_engineering_review"


class LedgerGate(StrEnum):
    """Ordered G0--G4 campaign gates."""

    G0_DENOMINATOR_AND_OWNERSHIP_FREEZE = "g0_denominator_and_ownership_freeze"
    G1_SEMANTIC_AUTHORITY_RECOVERY = "g1_semantic_authority_recovery"
    G2_BACKEND_PRODUCT_COMPLETENESS = "g2_backend_product_completeness"
    G3_CLI_CLEAN_BREAK_AND_COMPLETENESS = "g3_cli_clean_break_and_completeness"
    G4_TUI_ADMISSION_AND_PARITY = "g4_tui_admission_and_parity"


_GATE_ORDER: Final[tuple[LedgerGate, ...]] = tuple(LedgerGate)
_ALL_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(LedgerCapabilityAxis)
_SURFACE_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI}
)
_G2_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {
        LedgerCapabilityAxis.BACKEND,
        LedgerCapabilityAxis.COMPOSITION,
        LedgerCapabilityAxis.ARTIFACT,
        LedgerCapabilityAxis.PROVENANCE,
        LedgerCapabilityAxis.REGISTRY,
        LedgerCapabilityAxis.PROOF,
    }
)
_G2_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {
        LedgerGapClass.PRODUCT,
        LedgerGapClass.COMPOSITION,
        LedgerGapClass.PROOF,
        LedgerGapClass.ARTIFACT,
        LedgerGapClass.PROVENANCE,
        LedgerGapClass.REGISTRY,
    }
)
_G3_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {LedgerGapClass.AUTHORITY, LedgerGapClass.PRODUCT, LedgerGapClass.REACHABILITY, LedgerGapClass.ARTIFACT}
)


def _require_non_placeholder(value: str, *, field_name: str) -> str:
    if value.strip().lower() in _PLACEHOLDER_TEXT:
        raise ValueError(f"{field_name} must be bounded, not a placeholder")
    return value


def _require_identity(value: str, *, field_name: str, pattern: re.Pattern[str]) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"{field_name} must be a stable dotted identity: {value!r}")
    return value


def _require_digest(value: str, *, field_name: str) -> str:
    if not _DIGEST_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a sha256 digest")
    return value


def _require_observed_at(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must carry an explicit timezone")
    return value


def _canonical_value(value: object) -> object:
    """Return a recursively stable JSON value for digest-bearing contracts."""
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="python"))
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        pairs = sorted(((str(key), item) for key, item in mapping.items()), key=lambda item: item[0])
        return {key: _canonical_value(item) for key, item in pairs}
    if isinstance(value, (frozenset, set)):
        values = cast(frozenset[object] | set[object], value)
        normalized = [_canonical_value(item) for item in values]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        )
    if isinstance(value, tuple | list):
        values = cast(tuple[object, ...] | list[object], value)
        return [_canonical_value(item) for item in values]
    return value


def _canonical_digest(payload: object) -> str:
    """Return the SHA-256 digest of the contract's canonical JSON payload."""
    encoded = json.dumps(_canonical_value(payload), ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class _EvidenceRoleContract:
    kinds: frozenset[EvidenceKind]
    axes: frozenset[LedgerCapabilityAxis] | None
    single_axis: bool = False


_EVIDENCE_ROLE_CONTRACTS: Final[Mapping[EvidenceRole, _EvidenceRoleContract]] = {
    EvidenceRole.APPLICABILITY_REVIEW: _EvidenceRoleContract(frozenset({EvidenceKind.REVIEW}), None, True),
    EvidenceRole.BASELINE: _EvidenceRoleContract(
        frozenset(
            {EvidenceKind.CODE, EvidenceKind.TEST, EvidenceKind.COMMAND, EvidenceKind.ARTIFACT, EvidenceKind.REFERENCE}
        ),
        None,
        True,
    ),
    EvidenceRole.DIRECT_BACKEND_BEHAVIOR: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.BACKEND})
    ),
    EvidenceRole.ADAPTER_DETECTOR: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_SUCCESS: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_REFUSAL: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.CLI})
    ),
    EvidenceRole.CLI_ARTIFACT: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST, EvidenceKind.ARTIFACT}),
        frozenset({LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.ARTIFACT}),
    ),
    EvidenceRole.TUI_PARITY: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}),
        frozenset({LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI}),
    ),
    EvidenceRole.TUI_REACHABILITY: _EvidenceRoleContract(
        frozenset({EvidenceKind.TEST}), frozenset({LedgerCapabilityAxis.TUI})
    ),
    EvidenceRole.MATRIX_PUBLICATION: _EvidenceRoleContract(frozenset({EvidenceKind.REFERENCE}), _ALL_AXES),
    EvidenceRole.INDEPENDENT_ENGINEERING_REVIEW: _EvidenceRoleContract(frozenset({EvidenceKind.REVIEW}), _ALL_AXES),
}


class LedgerCapabilityIdentityV1(BaseModel):
    """Stable family, operation, and sub-operation identifiers."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    suboperation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_hierarchy(self) -> LedgerCapabilityIdentityV1:
        for field_name in ("capability_id", "operation_id", "suboperation_id"):
            _require_identity(getattr(self, field_name), field_name=field_name, pattern=_CAPABILITY_ID_PATTERN)
        if self.operation_id == self.capability_id or not self.operation_id.startswith(f"{self.capability_id}."):
            raise ValueError("operation_id must be a child of capability_id")
        if self.suboperation_id != self.operation_id and not self.suboperation_id.startswith(f"{self.operation_id}."):
            raise ValueError("suboperation_id must equal operation_id or be its child")
        return self

    @property
    def row_id(self) -> str:
        """Return the unique row identity."""
        return self.suboperation_id


class CanonicalSemanticHomeV1(BaseModel):
    """Canonical frontend-neutral command owner and result contract."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    owner: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    result_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_values(self) -> CanonicalSemanticHomeV1:
        for field_name in ("owner", "command_type", "result_type"):
            _require_non_placeholder(getattr(self, field_name), field_name=field_name)
        return self


class EvidenceSubjectSnapshotV1(BaseModel):
    """A current, independently observed subject used to freshness-check evidence."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    subject_id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    digest: str = Field(min_length=1)
    observed_at: datetime

    @model_validator(mode="after")
    def _check_snapshot(self) -> EvidenceSubjectSnapshotV1:
        _require_identity(self.subject_id, field_name="subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.locator, field_name="locator")
        _require_non_placeholder(self.revision, field_name="revision")
        _require_digest(self.digest, field_name="digest")
        _require_observed_at(self.observed_at, field_name="observed_at")
        return self


class EvidenceCoordinateV1(BaseModel):
    """A role-bound evidence claim tied to one exact current subject snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    role: EvidenceRole
    axes: frozenset[LedgerCapabilityAxis] = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    subject_revision: str = Field(min_length=1)
    subject_digest: str = Field(min_length=1)
    observed_at: datetime
    locator: str = Field(min_length=1)
    claim: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_role_contract(self) -> EvidenceCoordinateV1:
        _require_identity(self.evidence_id, field_name="evidence_id", pattern=_EVIDENCE_ID_PATTERN)
        _require_identity(self.subject_id, field_name="subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.subject_revision, field_name="subject_revision")
        _require_digest(self.subject_digest, field_name="subject_digest")
        _require_observed_at(self.observed_at, field_name="observed_at")
        _require_non_placeholder(self.locator, field_name="locator")
        _require_non_placeholder(self.claim, field_name="claim")
        contract = _EVIDENCE_ROLE_CONTRACTS[self.role]
        if self.kind not in contract.kinds:
            raise ValueError(f"{self.role.value} evidence has an invalid kind: {self.kind.value}")
        if contract.axes is not None and self.axes != contract.axes:
            raise ValueError(
                f"{self.role.value} evidence must prove exactly {sorted(axis.value for axis in contract.axes)}"
            )
        if contract.single_axis and len(self.axes) != 1:
            raise ValueError(f"{self.role.value} evidence must name exactly one axis")
        return self

    def is_current_against(self, subject: EvidenceSubjectSnapshotV1) -> bool:
        """Return whether this claim matches the exact current subject snapshot."""
        return (
            self.subject_id == subject.subject_id
            and self.subject_revision == subject.revision
            and self.subject_digest == subject.digest
            and self.observed_at == subject.observed_at
            and self.locator == subject.locator
        )


class DenominatorEntryV1(BaseModel):
    """One identity in the complete union census and each selecting source stream."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    sources: frozenset[DenominatorSourceKind] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_entry(self) -> DenominatorEntryV1:
        _require_identity(self.capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        return self


class CensusStreamObservationV1(BaseModel):
    """One independently readable mandatory source stream in a live census."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    source: DenominatorSourceKind
    revision: str = Field(min_length=1)
    observed_at: datetime
    scan_succeeded: bool
    readable: bool
    complete: bool
    ambiguous: bool
    reviewed_zero: bool
    capability_ids: tuple[str, ...] = ()
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_stream(self) -> CensusStreamObservationV1:
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        identities = self.capability_ids
        if len(set(identities)) != len(identities):
            raise ValueError(f"{self.source.value} census stream has duplicate capability identities")
        for capability_id in identities:
            _require_identity(capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        if identities and self.reviewed_zero:
            raise ValueError("a nonempty census stream cannot be declared reviewed zero")
        if not identities and not self.reviewed_zero:
            raise ValueError("an empty census stream requires an explicit reviewed zero")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError(f"{self.source.value} census stream digest does not match its observation")
        return self

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of every scan result and declared zero."""
        return _canonical_digest(
            {
                "source": self.source,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "scan_succeeded": self.scan_succeeded,
                "readable": self.readable,
                "complete": self.complete,
                "ambiguous": self.ambiguous,
                "reviewed_zero": self.reviewed_zero,
                "capability_ids": tuple(sorted(self.capability_ids)),
            }
        )

    @property
    def readiness_errors(self) -> tuple[str, ...]:
        """Return fail-closed diagnostics for an unavailable source stream."""
        errors: list[str] = []
        if not self.scan_succeeded:
            errors.append(f"{self.source.value} census stream did not scan successfully")
        if not self.readable:
            errors.append(f"{self.source.value} census stream is unreadable")
        if not self.complete:
            errors.append(f"{self.source.value} census stream is partial")
        if self.ambiguous:
            errors.append(f"{self.source.value} census stream is ambiguous")
        return tuple(errors)


class LedgerLiveCensusReportV1(BaseModel):
    """A complete external observation of every denominator source stream."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    streams: tuple[CensusStreamObservationV1, ...]
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_report(self) -> LedgerLiveCensusReportV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        sources = tuple(stream.source for stream in self.streams)
        if len(set(sources)) != len(sources) or frozenset(sources) != frozenset(DenominatorSourceKind):
            raise ValueError("a live census report must account for every mandatory source stream exactly once")
        if not self.capability_ids:
            raise ValueError("a complete live census report cannot be empty")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("live census report digest does not match its complete stream observations")
        return self

    @property
    def capability_ids(self) -> frozenset[str]:
        """Return the union of identities selected by all successful streams."""
        return frozenset(capability_id for stream in self.streams for capability_id in stream.capability_ids)

    @property
    def denominator_entries(self) -> tuple[DenominatorEntryV1, ...]:
        """Project source-stream observations into the complete union denominator."""
        sources_by_capability: dict[str, set[DenominatorSourceKind]] = {}
        for stream in self.streams:
            for capability_id in stream.capability_ids:
                sources_by_capability.setdefault(capability_id, set()).add(stream.source)
        return tuple(
            DenominatorEntryV1(capability_id=capability_id, sources=frozenset(sources))
            for capability_id, sources in sorted(sources_by_capability.items())
        )

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of the full source-stream observation."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "streams": tuple(sorted(self.streams, key=lambda stream: stream.source.value)),
            }
        )

    @property
    def readiness_errors(self) -> tuple[str, ...]:
        """Return the complete fail-closed diagnostics for this live census."""
        errors = [error for stream in self.streams for error in stream.readiness_errors]
        if not self.capability_ids:
            errors.append("the complete live census report is empty")
        return tuple(errors)


class LedgerDenominatorSnapshotV1(BaseModel):
    """A digested and dated complete denominator snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    entries: tuple[DenominatorEntryV1, ...]
    source_report_digest: str = Field(min_length=1)
    source_report_revision: str = Field(min_length=1)
    source_report_observed_at: datetime
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_snapshot(self) -> LedgerDenominatorSnapshotV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        _require_digest(self.source_report_digest, field_name="source_report_digest")
        _require_non_placeholder(self.source_report_revision, field_name="source_report_revision")
        _require_observed_at(self.source_report_observed_at, field_name="source_report_observed_at")
        if not self.entries:
            raise ValueError("a denominator census cannot be content-free")
        identities = tuple(entry.capability_id for entry in self.entries)
        if len(set(identities)) != len(identities):
            raise ValueError("a denominator census contains duplicate capability identities")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("denominator digest does not match its complete observed entries")
        return self

    @property
    def capability_ids(self) -> frozenset[str]:
        """Return the stable identities selected by this census."""
        return frozenset(entry.capability_id for entry in self.entries)

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of identities and source categories."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "entries": tuple(sorted(self.entries, key=lambda entry: entry.capability_id)),
                "source_report_digest": self.source_report_digest,
                "source_report_revision": self.source_report_revision,
                "source_report_observed_at": self.source_report_observed_at,
            }
        )

    @classmethod
    def from_live_report(cls, report: LedgerLiveCensusReportV1) -> LedgerDenominatorSnapshotV1:
        """Freeze a denominator snapshot that remains bound to its live report."""
        provisional = cls.model_construct(
            census_id=report.census_id,
            revision=report.revision,
            observed_at=report.observed_at,
            entries=report.denominator_entries,
            source_report_digest=report.digest,
            source_report_revision=report.revision,
            source_report_observed_at=report.observed_at,
            digest="",
        )
        return cls(**provisional.model_dump(exclude={"digest"}), digest=provisional.calculated_digest)


class AxisAssessmentV1(BaseModel):
    """One per-axis reviewed applicability decision and independent proof state."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    axis: LedgerCapabilityAxis
    applicability: ApplicabilityState
    applicability_rationale: str = Field(min_length=1)
    applicability_review_evidence: EvidenceCoordinateV1
    proof: AxisProofState
    surface_state: SurfaceCapabilityState | None = None
    evidence: tuple[EvidenceCoordinateV1, ...] = ()

    @model_validator(mode="after")
    def _check_assessment(self) -> AxisAssessmentV1:
        _require_non_placeholder(self.applicability_rationale, field_name="applicability_rationale")
        review = self.applicability_review_evidence
        if review.role is not EvidenceRole.APPLICABILITY_REVIEW or review.axes != frozenset({self.axis}):
            raise ValueError("each axis requires its own applicability-review evidence")
        if self.axis in _SURFACE_AXES and self.surface_state is None:
            raise ValueError(f"{self.axis.value} requires a surface_state")
        if self.axis not in _SURFACE_AXES and self.surface_state is not None:
            raise ValueError(f"{self.axis.value} must not carry a surface_state")
        if self.applicability is ApplicabilityState.NOT_APPLICABLE:
            if self.proof is not AxisProofState.NOT_APPLICABLE or self.evidence:
                raise ValueError("a non-applicable axis has no operational proof or evidence")
            if self.surface_state not in {None, SurfaceCapabilityState.NOT_APPLICABLE}:
                raise ValueError("a non-applicable surface must have not_applicable state")
        else:
            if self.proof is AxisProofState.NOT_APPLICABLE:
                raise ValueError("an applicable axis requires unproven, partial, or proven proof")
            if self.surface_state is SurfaceCapabilityState.NOT_APPLICABLE:
                raise ValueError("an applicable surface cannot be not_applicable")
        if any(self.axis not in coordinate.axes for coordinate in self.evidence):
            raise ValueError("operational evidence must name the assessment axis")
        if any(coordinate.role is EvidenceRole.APPLICABILITY_REVIEW for coordinate in self.evidence):
            raise ValueError("applicability review evidence belongs in its dedicated coordinate")
        if len({coordinate.evidence_id for coordinate in self.evidence}) != len(self.evidence):
            raise ValueError("assessment has duplicate operational evidence identities")
        return self

    @property
    def needs_finding(self) -> bool:
        """Return whether an applicable incomplete state needs a closure finding."""
        return self.applicability is ApplicabilityState.APPLICABLE and (
            self.proof is not AxisProofState.PROVEN
            or self.surface_state in {SurfaceCapabilityState.ABSENT, SurfaceCapabilityState.PARTIAL}
        )


class CapabilityFindingV1(BaseModel):
    """An unresolved axis-scoped gap and its bounded next action."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    finding_id: str = Field(min_length=1)
    gap_class: LedgerGapClass
    affected_axes: frozenset[LedgerCapabilityAxis] = Field(min_length=1)
    description: str = Field(min_length=1)
    next_closure_action: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_finding(self) -> CapabilityFindingV1:
        _require_identity(self.finding_id, field_name="finding_id", pattern=_FINDING_ID_PATTERN)
        _require_non_placeholder(self.description, field_name="description")
        _require_non_placeholder(self.next_closure_action, field_name="next_closure_action")
        return self


class AuthorityMigrationHistoryV1(BaseModel):
    """Monotonic G1 ownership history; it cannot be erased after cutover."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    initial_cli_ownership: InitialCliOwnership
    migration_completed: bool


class AuthorityDispositionEntryV1(BaseModel):
    """The initial CLI authority fact for one stable denominator row."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    row_id: str = Field(min_length=1)
    initial_cli_ownership: InitialCliOwnership

    @model_validator(mode="after")
    def _check_entry(self) -> AuthorityDispositionEntryV1:
        _require_identity(self.row_id, field_name="row_id", pattern=_CAPABILITY_ID_PATTERN)
        return self


class AuthorityDispositionSnapshotV1(BaseModel):
    """Digested immutable initial-ownership dispositions across matrix revisions."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    census_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    observed_at: datetime
    entries: tuple[AuthorityDispositionEntryV1, ...]
    digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_snapshot(self) -> AuthorityDispositionSnapshotV1:
        _require_identity(self.census_id, field_name="census_id", pattern=_CENSUS_ID_PATTERN)
        _require_non_placeholder(self.revision, field_name="revision")
        _require_observed_at(self.observed_at, field_name="observed_at")
        row_ids = tuple(entry.row_id for entry in self.entries)
        if not row_ids or len(set(row_ids)) != len(row_ids):
            raise ValueError("authority disposition snapshots require unique nonempty row identities")
        _require_digest(self.digest, field_name="digest")
        if self.digest != self.calculated_digest:
            raise ValueError("authority disposition snapshot digest does not match its entries")
        return self

    @property
    def dispositions(self) -> Mapping[str, InitialCliOwnership]:
        """Return initial ownership keyed by stable row identity."""
        return {entry.row_id: entry.initial_cli_ownership for entry in self.entries}

    @property
    def calculated_digest(self) -> str:
        """Return the canonical digest of immutable initial ownership facts."""
        return _canonical_digest(
            {
                "census_id": self.census_id,
                "revision": self.revision,
                "observed_at": self.observed_at,
                "entries": tuple(sorted(self.entries, key=lambda entry: entry.row_id)),
            }
        )


class LedgerCapabilityRowV1(BaseModel):
    """One complete reviewed row bound to the union denominator."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    identity: LedgerCapabilityIdentityV1
    semantic_home: CanonicalSemanticHomeV1
    assessments: tuple[AxisAssessmentV1, ...]
    annotations: frozenset[CapabilityAnnotation] = frozenset()
    findings: tuple[CapabilityFindingV1, ...] = ()
    authority_migration: AuthorityMigrationHistoryV1
    cli_delegates_to_canonical: bool

    @model_validator(mode="after")
    def _check_complete_row(self) -> LedgerCapabilityRowV1:
        has_all_axes = frozenset(assessment.axis for assessment in self.assessments) == _ALL_AXES
        if not has_all_axes or len(self.assessments) != len(_ALL_AXES):
            raise ValueError("rows require exactly one reviewed assessment for every axis")
        if not any(assessment.applicability is ApplicabilityState.APPLICABLE for assessment in self.assessments):
            raise ValueError("a capability row cannot be content-free or all not_applicable")
        if len({finding.finding_id for finding in self.findings}) != len(self.findings):
            raise ValueError("rows contain duplicate finding identities")
        for assessment in self.assessments:
            if assessment.needs_finding and not any(
                assessment.axis in finding.affected_axes for finding in self.findings
            ):
                raise ValueError(f"{assessment.axis.value} is unresolved but has no affected-axis finding")
        cli = self.assessment(LedgerCapabilityAxis.CLI)
        tui = self.assessment(LedgerCapabilityAxis.TUI)
        if self.cli_delegates_to_canonical != (CapabilityAnnotation.DELEGATING in self.annotations):
            raise ValueError("cli_delegates_to_canonical must exactly match delegating")
        if CapabilityAnnotation.CLI_OWNED in self.annotations and (
            cli.applicability is not ApplicabilityState.APPLICABLE or self.cli_delegates_to_canonical
        ):
            raise ValueError("cli_owned requires applicable non-delegating CLI")
        if self.cli_delegates_to_canonical and cli.applicability is not ApplicabilityState.APPLICABLE:
            raise ValueError("delegating requires applicable CLI")
        history = self.authority_migration
        if history.initial_cli_ownership is InitialCliOwnership.CLI_OWNED:
            if history.migration_completed != self.cli_delegates_to_canonical:
                raise ValueError("CLI-owned rows require matching migration and delegation state")
            if not history.migration_completed and CapabilityAnnotation.CLI_OWNED not in self.annotations:
                raise ValueError("uncut CLI-owned rows retain cli_owned")
            if not history.migration_completed and not any(
                finding.gap_class is LedgerGapClass.AUTHORITY and LedgerCapabilityAxis.CLI in finding.affected_axes
                for finding in self.findings
            ):
                raise ValueError(
                    "an incomplete CLI-owned migration requires an authority finding and next closure action"
                )
        elif CapabilityAnnotation.CLI_OWNED in self.annotations:
            raise ValueError("cli_owned contradicts immutable initial ownership")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("component_only requires applicable TUI")
        if (
            CapabilityAnnotation.INSTALLED in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("installed requires applicable TUI")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and CapabilityAnnotation.INSTALLED in self.annotations
        ):
            raise ValueError("a TUI capability cannot be component_only and installed")
        return self

    def assessment(self, axis: LedgerCapabilityAxis) -> AxisAssessmentV1:
        """Return the one validated assessment for an axis."""
        return next(assessment for assessment in self.assessments if assessment.axis is axis)

    def evidence_with_role(self, role: EvidenceRole, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Return whether the row has an operational coordinate of a role."""
        assessments: Iterable[AxisAssessmentV1] = self.assessments if axis is None else (self.assessment(axis),)
        return any(coordinate.role is role for assessment in assessments for coordinate in assessment.evidence)

    def has_gap(self, gap_class: LedgerGapClass, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Return whether a gap class affects the optional requested axis."""
        return any(
            finding.gap_class is gap_class and (axis is None or axis in finding.affected_axes)
            for finding in self.findings
        )


class LedgerCampaignControlsV1(BaseModel):
    """Singular-plan ownership and TUI-hold facts required by gate ordering."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    sole_ledger_parity_plan_owner: str = Field(min_length=1)
    tui_implementation_hold_recorded: bool
    tui_implementation_hold_active: bool

    @model_validator(mode="after")
    def _check_owner(self) -> LedgerCampaignControlsV1:
        if self.sole_ledger_parity_plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
            raise ValueError("sole_ledger_parity_plan_owner must be the accepted clitui-ledger plan identity")
        return self


class LedgerMatrixAcceptanceAttestationV1(BaseModel):
    """An independent ACCEPT ruling for one exact frozen matrix state."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    attestation_id: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    ruling: ReviewRuling
    plan_owner: str = Field(min_length=1)
    matrix_digest: str = Field(min_length=1)
    denominator_digest: str = Field(min_length=1)
    denominator_revision: str = Field(min_length=1)
    review_subject_id: str = Field(min_length=1)
    review_subject_revision: str = Field(min_length=1)
    review_subject_digest: str = Field(min_length=1)
    review_subject_observed_at: datetime
    attested_at: datetime

    @model_validator(mode="after")
    def _check_attestation(self) -> LedgerMatrixAcceptanceAttestationV1:
        _require_identity(self.attestation_id, field_name="attestation_id", pattern=_ATTESTATION_ID_PATTERN)
        _require_non_placeholder(self.reviewer, field_name="reviewer")
        if self.plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
            raise ValueError("acceptance attestation must name the accepted clitui-ledger plan identity")
        _require_digest(self.matrix_digest, field_name="matrix_digest")
        _require_digest(self.denominator_digest, field_name="denominator_digest")
        _require_non_placeholder(self.denominator_revision, field_name="denominator_revision")
        _require_identity(self.review_subject_id, field_name="review_subject_id", pattern=_SUBJECT_ID_PATTERN)
        _require_non_placeholder(self.review_subject_revision, field_name="review_subject_revision")
        _require_digest(self.review_subject_digest, field_name="review_subject_digest")
        _require_observed_at(self.review_subject_observed_at, field_name="review_subject_observed_at")
        _require_observed_at(self.attested_at, field_name="attested_at")
        return self


class LedgerCapabilityMatrixV1(BaseModel):
    """Accepted/current census and current evidence subjects bind every matrix row."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    controls: LedgerCampaignControlsV1
    accepted_denominator: LedgerDenominatorSnapshotV1
    current_denominator: LedgerDenominatorSnapshotV1
    accepted_authority_dispositions: AuthorityDispositionSnapshotV1
    current_authority_dispositions: AuthorityDispositionSnapshotV1
    current_subjects: tuple[EvidenceSubjectSnapshotV1, ...]
    rows: tuple[LedgerCapabilityRowV1, ...]
    campaign_evidence: tuple[EvidenceCoordinateV1, ...] = ()
    matrix_digest: str = Field(min_length=1)
    acceptance_attestation: LedgerMatrixAcceptanceAttestationV1

    @model_validator(mode="after")
    def _check_matrix(self) -> LedgerCapabilityMatrixV1:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported Ledger capability matrix schema version: {self.schema_version}")
        if not self.current_subjects:
            raise ValueError("matrix requires current evidence-subject snapshots")
        subject_ids = tuple(subject.subject_id for subject in self.current_subjects)
        if len(set(subject_ids)) != len(subject_ids):
            raise ValueError("current subject snapshots contain duplicate identities")
        row_ids = tuple(row.identity.row_id for row in self.rows)
        if len(set(row_ids)) != len(row_ids):
            raise ValueError("matrix contains duplicate row identities")
        if frozenset(row_ids) != self.current_denominator.capability_ids:
            raise ValueError("matrix rows must exactly equal current complete denominator")
        if frozenset(self.accepted_authority_dispositions.dispositions) != self.accepted_denominator.capability_ids:
            raise ValueError("accepted authority dispositions must exactly equal the accepted denominator")
        if self.accepted_authority_dispositions.census_id != self.accepted_denominator.census_id:
            raise ValueError("accepted authority dispositions must bind the accepted denominator census")
        if frozenset(row_ids) != frozenset(self.current_authority_dispositions.dispositions):
            raise ValueError("current authority dispositions must exactly equal matrix rows")
        if self.current_authority_dispositions.census_id != self.current_denominator.census_id:
            raise ValueError("current authority dispositions must bind the current denominator census")
        current_dispositions = self.current_authority_dispositions.dispositions
        for row in self.rows:
            if current_dispositions[row.identity.row_id] is not row.authority_migration.initial_cli_ownership:
                raise ValueError("current authority disposition contradicts immutable row history")
        evidence = tuple(self.iter_evidence())
        evidence_ids = tuple(coordinate.evidence_id for coordinate in evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence identities must be globally unique")
        subjects = {subject.subject_id: subject for subject in self.current_subjects}
        for coordinate in evidence:
            subject = subjects.get(coordinate.subject_id)
            if subject is None or not coordinate.is_current_against(subject):
                raise ValueError(f"evidence {coordinate.evidence_id!r} is stale or absent from current subjects")
        _require_digest(self.matrix_digest, field_name="matrix_digest")
        if self.matrix_digest != self.calculated_matrix_digest:
            raise ValueError("matrix digest does not bind the current campaign state")
        attestation = self.acceptance_attestation
        if attestation.plan_owner != self.controls.sole_ledger_parity_plan_owner:
            raise ValueError("acceptance attestation plan owner differs from campaign controls")
        if attestation.matrix_digest != self.matrix_digest:
            raise ValueError("acceptance attestation is not bound to this exact matrix digest")
        if (
            attestation.denominator_digest != self.current_denominator.digest
            or attestation.denominator_revision != self.current_denominator.revision
        ):
            raise ValueError("acceptance attestation is not bound to this exact denominator revision")
        review_subject = subjects.get(attestation.review_subject_id)
        if review_subject is None or (
            attestation.review_subject_revision != review_subject.revision
            or attestation.review_subject_digest != review_subject.digest
            or attestation.review_subject_observed_at != review_subject.observed_at
        ):
            raise ValueError("acceptance attestation review subject is stale or absent")
        return self

    def iter_evidence(self) -> Iterable[EvidenceCoordinateV1]:
        """Yield every coordinate whose identity and freshness are globally checked."""
        for row in self.rows:
            for assessment in row.assessments:
                yield assessment.applicability_review_evidence
                yield from assessment.evidence
        yield from self.campaign_evidence

    def has_campaign_evidence(self, role: EvidenceRole) -> bool:
        """Return whether a current campaign-wide coordinate has a role."""
        return any(coordinate.role is role for coordinate in self.campaign_evidence)

    @property
    def calculated_matrix_digest(self) -> str:
        """Return the digest of all mutable semantic and proof-bearing campaign facts."""
        return self.calculate_digest(
            schema_version=self.schema_version,
            controls=self.controls,
            accepted_denominator=self.accepted_denominator,
            current_denominator=self.current_denominator,
            accepted_authority_dispositions=self.accepted_authority_dispositions,
            current_authority_dispositions=self.current_authority_dispositions,
            current_subjects=self.current_subjects,
            rows=self.rows,
            campaign_evidence=self.campaign_evidence,
        )

    @classmethod
    def calculate_digest(
        cls,
        *,
        schema_version: int,
        controls: LedgerCampaignControlsV1,
        accepted_denominator: LedgerDenominatorSnapshotV1,
        current_denominator: LedgerDenominatorSnapshotV1,
        accepted_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_authority_dispositions: AuthorityDispositionSnapshotV1,
        current_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
        rows: tuple[LedgerCapabilityRowV1, ...],
        campaign_evidence: tuple[EvidenceCoordinateV1, ...],
    ) -> str:
        """Calculate the pre-attestation digest without constructing an invalid matrix."""
        return _canonical_digest(
            {
                "schema_version": schema_version,
                "controls": controls,
                "accepted_denominator": accepted_denominator,
                "current_denominator": current_denominator,
                "accepted_authority_dispositions": accepted_authority_dispositions,
                "current_authority_dispositions": current_authority_dispositions,
                "current_subjects": tuple(sorted(current_subjects, key=lambda subject: subject.subject_id)),
                "rows": tuple(sorted(rows, key=lambda row: row.identity.row_id)),
                "campaign_evidence": tuple(
                    sorted(campaign_evidence, key=lambda coordinate: coordinate.evidence_id)
                ),
            }
        )


class GateAssessmentV1(BaseModel):
    """The deterministic open/closed result for one gate predicate."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    gate: LedgerGate
    closed: bool
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_shape(self) -> GateAssessmentV1:
        if self.closed and self.blockers:
            raise ValueError("a closed gate cannot carry blockers")
        if not self.closed and not self.blockers:
            raise ValueError("an open gate must name blockers")
        return self


def _denominator_drift(accepted: LedgerDenominatorSnapshotV1, current: LedgerDenominatorSnapshotV1) -> tuple[str, ...]:
    if accepted.census_id != current.census_id:
        return ("accepted and current denominator census identities differ",)
    accepted_entries = {entry.capability_id: entry.sources for entry in accepted.entries}
    current_entries = {entry.capability_id: entry.sources for entry in current.entries}
    drift: list[str] = []
    for identity in sorted(current_entries.keys() - accepted_entries.keys()):
        drift.append(f"new live denominator capability: {identity}")
    for identity in sorted(accepted_entries.keys() - current_entries.keys()):
        drift.append(f"accepted denominator capability missing from current census: {identity}")
    for identity in sorted(accepted_entries.keys() & current_entries.keys()):
        if accepted_entries[identity] != current_entries[identity]:
            drift.append(f"denominator source classification drifted: {identity}")
    if accepted.revision != current.revision:
        drift.append("denominator revision drifted")
    if accepted.observed_at != current.observed_at:
        drift.append("denominator observation time drifted")
    if accepted.source_report_revision != current.source_report_revision:
        drift.append("denominator source-report revision drifted")
    if accepted.source_report_observed_at != current.source_report_observed_at:
        drift.append("denominator source-report observation time drifted")
    if accepted.source_report_digest != current.source_report_digest:
        drift.append("denominator source-report digest drifted")
    if accepted.digest != current.digest and not drift:
        drift.append("denominator digest drifted without an entry-level explanation")
    return tuple(drift)


def _authority_disposition_drift(
    accepted: AuthorityDispositionSnapshotV1, current: AuthorityDispositionSnapshotV1
) -> tuple[str, ...]:
    """Detect erased or changed immutable initial CLI ownership across revisions."""
    if accepted.census_id != current.census_id:
        return ("accepted and current authority disposition census identities differ",)
    accepted_entries = accepted.dispositions
    current_entries = current.dispositions
    drift: list[str] = []
    for row_id in sorted(current_entries.keys() - accepted_entries.keys()):
        drift.append(f"new authority disposition row: {row_id}")
    for row_id in sorted(accepted_entries.keys() - current_entries.keys()):
        drift.append(f"accepted authority disposition missing from current snapshot: {row_id}")
    for row_id in sorted(accepted_entries.keys() & current_entries.keys()):
        if accepted_entries[row_id] is not current_entries[row_id]:
            drift.append(f"immutable initial CLI ownership drifted: {row_id}")
    if accepted.revision != current.revision:
        drift.append("authority disposition revision drifted")
    if accepted.observed_at != current.observed_at:
        drift.append("authority disposition observation time drifted")
    if accepted.digest != current.digest and not drift:
        drift.append("authority disposition digest drifted without an entry-level explanation")
    return tuple(drift)


def _live_census_report_errors(report: LedgerLiveCensusReportV1) -> list[str]:
    """Recheck a supplied report so model-copy construction cannot bypass G0."""
    errors: list[str] = []
    sources = tuple(stream.source for stream in report.streams)
    if len(set(sources)) != len(sources) or frozenset(sources) != frozenset(DenominatorSourceKind):
        errors.append("live census report does not account for every mandatory source stream exactly once")
    if report.digest != report.calculated_digest:
        errors.append("live census report digest is stale or does not match its stream observations")
    for stream in report.streams:
        if stream.digest != stream.calculated_digest:
            errors.append(f"{stream.source.value} census stream digest is stale or does not match its observation")
        if len(set(stream.capability_ids)) != len(stream.capability_ids):
            errors.append(f"{stream.source.value} census stream has duplicate capability identities")
        if stream.capability_ids and stream.reviewed_zero:
            errors.append(f"{stream.source.value} census stream has entries but is declared reviewed zero")
        if not stream.capability_ids and not stream.reviewed_zero:
            errors.append(f"{stream.source.value} census stream is empty without an explicit reviewed zero")
        errors.extend(stream.readiness_errors)
    if not report.capability_ids:
        errors.append("the complete live census report is empty")
    return errors


def _matrix_acceptance_errors(matrix: LedgerCapabilityMatrixV1) -> list[str]:
    """Recheck digest-bound G0 acceptance before trusting a supplied matrix."""
    errors: list[str] = []
    if matrix.controls.sole_ledger_parity_plan_owner != ACCEPTED_LEDGER_PARITY_PLAN_OWNER:
        errors.append("campaign controls do not name the accepted clitui-ledger plan identity")
    if matrix.matrix_digest != matrix.calculated_matrix_digest:
        errors.append("matrix digest is stale or does not bind the current campaign state")
    attestation = matrix.acceptance_attestation
    if attestation.plan_owner != matrix.controls.sole_ledger_parity_plan_owner:
        errors.append("acceptance attestation plan owner differs from campaign controls")
    if attestation.matrix_digest != matrix.matrix_digest:
        errors.append("acceptance attestation is not bound to this exact matrix digest")
    if (
        attestation.denominator_digest != matrix.current_denominator.digest
        or attestation.denominator_revision != matrix.current_denominator.revision
    ):
        errors.append("acceptance attestation is not bound to this exact denominator revision")
    subjects = {subject.subject_id: subject for subject in matrix.current_subjects}
    review_subject = subjects.get(attestation.review_subject_id)
    if review_subject is None or (
        attestation.review_subject_revision != review_subject.revision
        or attestation.review_subject_digest != review_subject.digest
        or attestation.review_subject_observed_at != review_subject.observed_at
    ):
        errors.append("acceptance attestation review subject is stale or absent")
    return errors


def validate_ledger_matrix_currentness(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> list[str]:
    """Compare persisted state to mandatory live census and evidence observations."""
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers:
        return validation_blockers
    if canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        return ["gate input validation failed at <root>: incomplete_canonical_result"]
    matrix = canonical_matrix
    observed_census = canonical_census
    observed_subjects = canonical_subjects
    errors = _live_census_report_errors(observed_census)
    observed_denominator = LedgerDenominatorSnapshotV1.from_live_report(observed_census)
    errors.extend(_denominator_drift(matrix.current_denominator, observed_denominator))
    if not observed_subjects:
        errors.append("live evidence-subject observation is empty")
    expected = {subject.subject_id: subject for subject in matrix.current_subjects}
    observed = {subject.subject_id: subject for subject in observed_subjects}
    if len(observed) != len(observed_subjects):
        errors.append("live evidence-subject observation contains duplicate identities")
    for subject_id in sorted(observed.keys() - expected.keys()):
        errors.append(f"new evidence subject absent from matrix snapshot: {subject_id}")
    for subject_id in sorted(expected.keys() - observed.keys()):
        errors.append(f"matrix evidence subject no longer observed: {subject_id}")
    for subject_id in sorted(expected.keys() & observed.keys()):
        if expected[subject_id] != observed[subject_id]:
            errors.append(f"evidence subject freshness drifted: {subject_id}")
    return errors


def _gate_assessment(gate: LedgerGate, blockers: list[str]) -> GateAssessmentV1:
    return GateAssessmentV1(gate=gate, closed=not blockers, blockers=tuple(blockers))


def _serialized_python_data(value: object) -> object:
    """Detach a supplied model from model-copy state before revalidation."""
    return value.model_dump(mode="python") if isinstance(value, BaseModel) else value


def _validation_blockers(scope: str, error: ValidationError) -> list[str]:
    """Render canonical, stable fail-closed blockers without exposing values."""
    return [
        f"{scope} validation failed at {'.'.join(str(part) for part in item['loc']) or '<root>'}: {item['type']}"
        for item in sorted(error.errors(include_url=False), key=lambda item: (item["loc"], item["type"]))
    ]


def _canonical_gate_inputs(
    matrix: LedgerCapabilityMatrixV1,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> tuple[
    LedgerCapabilityMatrixV1 | None,
    LedgerLiveCensusReportV1 | None,
    tuple[EvidenceSubjectSnapshotV1, ...] | None,
    list[str],
]:
    """Exhaustively revalidate every supplied gate object from serialized data."""
    blockers: list[str] = []
    canonical_matrix: LedgerCapabilityMatrixV1 | None = None
    canonical_census: LedgerLiveCensusReportV1 | None = None
    canonical_subjects: tuple[EvidenceSubjectSnapshotV1, ...] | None = None
    try:
        canonical_matrix = LedgerCapabilityMatrixV1.model_validate(_serialized_python_data(matrix))
    except ValidationError as error:
        blockers.extend(_validation_blockers("matrix", error))
    except (TypeError, ValueError):
        blockers.append("matrix validation failed at <root>: invalid_serialized_data")
    try:
        canonical_census = LedgerLiveCensusReportV1.model_validate(_serialized_python_data(observed_census))
    except ValidationError as error:
        blockers.extend(_validation_blockers("live census", error))
    except (TypeError, ValueError):
        blockers.append("live census validation failed at <root>: invalid_serialized_data")
    try:
        canonical_subjects = TypeAdapter(tuple[EvidenceSubjectSnapshotV1, ...]).validate_python(
            _serialized_python_data(observed_subjects)
        )
    except ValidationError as error:
        blockers.extend(_validation_blockers("observed subjects", error))
    except (TypeError, ValueError):
        blockers.append("observed subjects validation failed at <root>: invalid_serialized_data")
    return canonical_matrix, canonical_census, canonical_subjects, blockers


def evaluate_ledger_capability_gate(
    matrix: LedgerCapabilityMatrixV1,
    gate: LedgerGate,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> GateAssessmentV1:
    """Evaluate the exact G0--G4 predicate against typed current evidence."""
    canonical_matrix, canonical_census, canonical_subjects, validation_blockers = _canonical_gate_inputs(
        matrix, observed_census, observed_subjects
    )
    if validation_blockers:
        return _gate_assessment(gate, validation_blockers)
    if canonical_matrix is None or canonical_census is None or canonical_subjects is None:
        return _gate_assessment(gate, ["gate input validation failed at <root>: incomplete_canonical_result"])
    matrix = canonical_matrix
    observed_census = canonical_census
    observed_subjects = canonical_subjects
    blockers: list[str] = []
    if gate is LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE:
        blockers.extend(_denominator_drift(matrix.accepted_denominator, matrix.current_denominator))
        blockers.extend(
            _authority_disposition_drift(matrix.accepted_authority_dispositions, matrix.current_authority_dispositions)
        )
        blockers.extend(
            validate_ledger_matrix_currentness(
                matrix, observed_census=observed_census, observed_subjects=observed_subjects
            )
        )
        blockers.extend(_matrix_acceptance_errors(matrix))
        if not matrix.controls.tui_implementation_hold_recorded or not matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold is not recorded and active")
        if matrix.acceptance_attestation.ruling is not ReviewRuling.ACCEPT:
            blockers.append("independent review has not issued an ACCEPT attestation for the frozen matrix")
        for row in matrix.rows:
            for assessment in row.assessments:
                if (
                    assessment.applicability is ApplicabilityState.APPLICABLE
                    and assessment.proof is not AxisProofState.UNPROVEN
                    and not row.evidence_with_role(EvidenceRole.BASELINE, axis=assessment.axis)
                ):
                    blockers.append(f"{row.identity.row_id}: {assessment.axis.value} lacks exact baseline evidence")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY:
        for row in matrix.rows:
            backend = row.assessment(LedgerCapabilityAxis.BACKEND)
            if row.has_gap(LedgerGapClass.AUTHORITY):
                blockers.append(f"{row.identity.row_id}: an authority finding remains")
            if CapabilityAnnotation.CLI_OWNED in row.annotations:
                blockers.append(f"{row.identity.row_id}: cli_owned annotation remains")
            if (
                backend.applicability is ApplicabilityState.APPLICABLE
                and backend.surface_state is SurfaceCapabilityState.ABSENT
            ):
                blockers.append(f"{row.identity.row_id}: applicable backend owner is absent")
            if row.authority_migration.initial_cli_ownership is InitialCliOwnership.CLI_OWNED:
                if not row.authority_migration.migration_completed:
                    blockers.append(f"{row.identity.row_id}: immutable CLI-owned migration is incomplete")
                if not row.evidence_with_role(EvidenceRole.DIRECT_BACKEND_BEHAVIOR, axis=LedgerCapabilityAxis.BACKEND):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks direct backend behavior evidence")
                if not row.evidence_with_role(EvidenceRole.ADAPTER_DETECTOR, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks an adapter detector")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS:
        for row in matrix.rows:
            backend = row.assessment(LedgerCapabilityAxis.BACKEND)
            if backend.applicability is ApplicabilityState.APPLICABLE:
                if (
                    backend.surface_state is not SurfaceCapabilityState.PROVEN
                    or backend.proof is not AxisProofState.PROVEN
                ):
                    blockers.append(f"{row.identity.row_id}: backend is not implemented and proven")
                if not row.evidence_with_role(EvidenceRole.DIRECT_BACKEND_BEHAVIOR, axis=LedgerCapabilityAxis.BACKEND):
                    blockers.append(f"{row.identity.row_id}: backend lacks direct behavior evidence")
            for axis in _G2_AXES - {LedgerCapabilityAxis.BACKEND}:
                assessment = row.assessment(axis)
                if (
                    assessment.applicability is ApplicabilityState.APPLICABLE
                    and assessment.proof is not AxisProofState.PROVEN
                ):
                    blockers.append(f"{row.identity.row_id}: applicable {axis.value} axis is not proven")
            for gap_class in _G2_GAP_CLASSES:
                if row.has_gap(gap_class):
                    blockers.append(f"{row.identity.row_id}: {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS:
        for row in matrix.rows:
            cli = row.assessment(LedgerCapabilityAxis.CLI)
            if cli.applicability is not ApplicabilityState.APPLICABLE:
                continue
            if cli.proof is not AxisProofState.PROVEN or cli.surface_state is not SurfaceCapabilityState.PROVEN:
                blockers.append(f"{row.identity.row_id}: CLI is not proven through a stable interface contract")
            if not row.cli_delegates_to_canonical:
                blockers.append(f"{row.identity.row_id}: CLI does not delegate to the canonical owner")
            if not row.evidence_with_role(EvidenceRole.CLI_SUCCESS, axis=LedgerCapabilityAxis.CLI):
                blockers.append(f"{row.identity.row_id}: CLI success behavior is not evidenced")
            if not row.evidence_with_role(EvidenceRole.CLI_REFUSAL, axis=LedgerCapabilityAxis.CLI):
                blockers.append(f"{row.identity.row_id}: CLI refusal behavior is not evidenced")
            if row.assessment(
                LedgerCapabilityAxis.ARTIFACT
            ).applicability is ApplicabilityState.APPLICABLE and not row.evidence_with_role(
                EvidenceRole.CLI_ARTIFACT, axis=LedgerCapabilityAxis.CLI
            ):
                blockers.append(f"{row.identity.row_id}: CLI artifact behavior is not evidenced")
            for gap_class in _G3_GAP_CLASSES:
                if row.has_gap(gap_class, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: CLI {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)
    if gate is LedgerGate.G4_TUI_ADMISSION_AND_PARITY:
        if matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold remains active")
        for row in matrix.rows:
            tui = row.assessment(LedgerCapabilityAxis.TUI)
            if tui.applicability is ApplicabilityState.APPLICABLE:
                if tui.proof is not AxisProofState.PROVEN or tui.surface_state is not SurfaceCapabilityState.PROVEN:
                    blockers.append(f"{row.identity.row_id}: TUI is not proven and installed")
                if CapabilityAnnotation.INSTALLED not in row.annotations:
                    blockers.append(f"{row.identity.row_id}: TUI is not marked installed")
            for finding in row.findings:
                if any(
                    row.assessment(axis).applicability is ApplicabilityState.APPLICABLE
                    for axis in finding.affected_axes
                ):
                    blockers.append(f"{row.identity.row_id}: blocking {finding.gap_class.value} finding remains")
        for role in (EvidenceRole.TUI_PARITY, EvidenceRole.TUI_REACHABILITY, EvidenceRole.MATRIX_PUBLICATION):
            if not matrix.has_campaign_evidence(role):
                blockers.append(f"campaign-wide {role.value} evidence is missing")
        return _gate_assessment(gate, blockers)
    raise ValueError(f"unsupported Ledger gate: {gate}")


def evaluate_ledger_capability_gates(
    matrix: LedgerCapabilityMatrixV1,
    *,
    observed_census: LedgerLiveCensusReportV1,
    observed_subjects: tuple[EvidenceSubjectSnapshotV1, ...],
) -> tuple[GateAssessmentV1, ...]:
    """Evaluate ordered gates without allowing a later false closure."""
    assessments: list[GateAssessmentV1] = []
    prior_open = False
    for gate in _GATE_ORDER:
        assessment = evaluate_ledger_capability_gate(
            matrix, gate, observed_census=observed_census, observed_subjects=observed_subjects
        )
        if prior_open and assessment.closed:
            assessment = GateAssessmentV1(
                gate=gate, closed=False, blockers=(f"{gate.value} cannot close while an earlier gate remains open",)
            )
        assessments.append(assessment)
        prior_open = prior_open or not assessment.closed
    return tuple(assessments)


def reopened_gates_for_denominator_drift(
    accepted: LedgerDenominatorSnapshotV1, current: LedgerDenominatorSnapshotV1
) -> frozenset[LedgerGate]:
    """A changed live census reopens G0 and all potentially affected later gates."""
    try:
        canonical_accepted = LedgerDenominatorSnapshotV1.model_validate(_serialized_python_data(accepted))
        canonical_current = LedgerDenominatorSnapshotV1.model_validate(_serialized_python_data(current))
    except (TypeError, ValueError, ValidationError):
        # This legacy return shape has no blocker channel; reopening every gate
        # is the deterministic fail-closed refusal for invalid serialized data.
        return frozenset(_GATE_ORDER)
    return frozenset(_GATE_ORDER) if _denominator_drift(canonical_accepted, canonical_current) else frozenset()


__all__ = [
    "ACCEPTED_LEDGER_PARITY_PLAN_OWNER",
    "SCHEMA_VERSION",
    "ApplicabilityState",
    "AuthorityDispositionEntryV1",
    "AuthorityDispositionSnapshotV1",
    "AuthorityMigrationHistoryV1",
    "AxisAssessmentV1",
    "AxisProofState",
    "CanonicalSemanticHomeV1",
    "CapabilityAnnotation",
    "CapabilityFindingV1",
    "CensusStreamObservationV1",
    "DenominatorEntryV1",
    "DenominatorSourceKind",
    "EvidenceCoordinateV1",
    "EvidenceKind",
    "EvidenceRole",
    "EvidenceSubjectSnapshotV1",
    "GateAssessmentV1",
    "InitialCliOwnership",
    "LedgerCampaignControlsV1",
    "LedgerCapabilityAxis",
    "LedgerCapabilityIdentityV1",
    "LedgerCapabilityMatrixV1",
    "LedgerCapabilityRowV1",
    "LedgerDenominatorSnapshotV1",
    "LedgerGapClass",
    "LedgerGate",
    "LedgerLiveCensusReportV1",
    "LedgerMatrixAcceptanceAttestationV1",
    "ReviewRuling",
    "SurfaceCapabilityState",
    "evaluate_ledger_capability_gate",
    "evaluate_ledger_capability_gates",
    "reopened_gates_for_denominator_drift",
    "validate_ledger_matrix_currentness",
]
