"""Typed campaign ledger for Ledger backend, CLI, and TUI capability parity.

This module defines the *contract* for the checked-in Ledger capability matrix.
It deliberately does not discover, classify, or publish rows: those operations
belong to the subsequent denominator, review, and reference-publication steps.
Keeping the contract separate makes a newly observed capability a reviewable
addition rather than an implicit, potentially incomplete, classification.

The contract keeps applicability, implementation state, and proof independent.
For example, a TUI component can exist without being installed, a CLI command
can be present without delegating to the canonical backend owner, and a backend
operation can be implemented without production-behaviour evidence.  None of
those facts may stand in for another when a gate is evaluated.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION: Final[int] = 1
_CAPABILITY_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^ledger(?:\.[a-z][a-z0-9_]*)(?:\.[a-z][a-z0-9_]*)*$")
_EVIDENCE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^evidence\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_FINDING_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^finding\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_PLACEHOLDER_TEXT: Final[frozenset[str]] = frozenset({"", "n/a", "na", "none", "tbd", "todo", "unknown", "unmeasured"})


class LedgerCapabilityAxis(StrEnum):
    """Independent obligations carried by every Ledger capability row."""

    BACKEND = "backend"
    CLI = "cli"
    TUI = "tui"
    COMPOSITION = "composition"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"
    PROOF = "proof"


class ApplicabilityState(StrEnum):
    """Whether an axis applies to a capability, independent of its proof."""

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


class AxisProofState(StrEnum):
    """Evidence maturity for an axis, independent of implementation presence."""

    NOT_APPLICABLE = "not_applicable"
    UNPROVEN = "unproven"
    PARTIAL = "partial"
    PROVEN = "proven"


class SurfaceCapabilityState(StrEnum):
    """Observed implementation/reachability state for a frontend or backend."""

    NOT_APPLICABLE = "not_applicable"
    ABSENT = "absent"
    PARTIAL = "partial"
    PROVEN = "proven"


class CapabilityAnnotation(StrEnum):
    """Non-substitutable ownership and reachability annotations."""

    CLI_OWNED = "cli_owned"
    DELEGATING = "delegating"
    COMPONENT_ONLY = "component_only"
    INSTALLED = "installed"


class LedgerGapClass(StrEnum):
    """Closed taxonomy for work still needed by a capability."""

    AUTHORITY = "authority"
    PRODUCT = "product"
    COMPOSITION = "composition"
    PROOF = "proof"
    REACHABILITY = "reachability"
    ARTIFACT = "artifact"
    PROVENANCE = "provenance"
    REGISTRY = "registry"


class EvidenceKind(StrEnum):
    """The durable source form of a proof coordinate."""

    CODE = "code"
    TEST = "test"
    COMMAND = "command"
    ARTIFACT = "artifact"
    REVIEW = "review"
    REFERENCE = "reference"


class EvidenceRole(StrEnum):
    """The precise claim an evidence coordinate is allowed to support."""

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
    """Ordered campaign gates; no later gate can supersede an earlier one."""

    G0_DENOMINATOR_AND_OWNERSHIP_FREEZE = "g0_denominator_and_ownership_freeze"
    G1_SEMANTIC_AUTHORITY_RECOVERY = "g1_semantic_authority_recovery"
    G2_BACKEND_PRODUCT_COMPLETENESS = "g2_backend_product_completeness"
    G3_CLI_CLEAN_BREAK_AND_COMPLETENESS = "g3_cli_clean_break_and_completeness"
    G4_TUI_ADMISSION_AND_PARITY = "g4_tui_admission_and_parity"


_GATE_ORDER: Final[tuple[LedgerGate, ...]] = (
    LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE,
    LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY,
    LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS,
    LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS,
    LedgerGate.G4_TUI_ADMISSION_AND_PARITY,
)
_SURFACE_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {LedgerCapabilityAxis.BACKEND, LedgerCapabilityAxis.CLI, LedgerCapabilityAxis.TUI},
)
_G2_AXES: Final[frozenset[LedgerCapabilityAxis]] = frozenset(
    {
        LedgerCapabilityAxis.BACKEND,
        LedgerCapabilityAxis.COMPOSITION,
        LedgerCapabilityAxis.ARTIFACT,
        LedgerCapabilityAxis.PROVENANCE,
        LedgerCapabilityAxis.REGISTRY,
        LedgerCapabilityAxis.PROOF,
    },
)
_G2_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {
        LedgerGapClass.PRODUCT,
        LedgerGapClass.COMPOSITION,
        LedgerGapClass.PROOF,
        LedgerGapClass.ARTIFACT,
        LedgerGapClass.PROVENANCE,
        LedgerGapClass.REGISTRY,
    },
)
_G3_GAP_CLASSES: Final[frozenset[LedgerGapClass]] = frozenset(
    {
        LedgerGapClass.AUTHORITY,
        LedgerGapClass.PRODUCT,
        LedgerGapClass.REACHABILITY,
        LedgerGapClass.ARTIFACT,
    },
)


def _require_non_placeholder(value: str, *, field_name: str) -> str:
    if value.strip().lower() in _PLACEHOLDER_TEXT:
        raise ValueError(f"{field_name} must be bounded, not a placeholder")
    return value


def _require_identity(value: str, *, field_name: str, pattern: re.Pattern[str]) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"{field_name} must be a stable dotted identity: {value!r}")
    return value


class LedgerCapabilityIdentityV1(BaseModel):
    """Stable family, operation, and optional sub-operation identifiers."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    capability_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    suboperation_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_identity_hierarchy(self) -> LedgerCapabilityIdentityV1:
        _require_identity(self.capability_id, field_name="capability_id", pattern=_CAPABILITY_ID_PATTERN)
        _require_identity(self.operation_id, field_name="operation_id", pattern=_CAPABILITY_ID_PATTERN)
        _require_identity(self.suboperation_id, field_name="suboperation_id", pattern=_CAPABILITY_ID_PATTERN)
        if self.operation_id == self.capability_id or not self.operation_id.startswith(f"{self.capability_id}."):
            raise ValueError("operation_id must be a child of capability_id")
        if self.suboperation_id != self.operation_id and not self.suboperation_id.startswith(f"{self.operation_id}."):
            raise ValueError("suboperation_id must equal operation_id or be its child")
        return self

    @property
    def row_id(self) -> str:
        """Return the unique, stable row identity."""
        return self.suboperation_id


class CanonicalSemanticHomeV1(BaseModel):
    """Canonical backend owner and its typed command/result contract."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    owner: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    result_type: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_non_placeholder_values(self) -> CanonicalSemanticHomeV1:
        _require_non_placeholder(self.owner, field_name="owner")
        _require_non_placeholder(self.command_type, field_name="command_type")
        _require_non_placeholder(self.result_type, field_name="result_type")
        return self


class EvidenceCoordinateV1(BaseModel):
    """One inspectable evidence location and the claim it supports."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    role: EvidenceRole
    axes: frozenset[LedgerCapabilityAxis] = Field(min_length=1)
    locator: str = Field(min_length=1)
    claim: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_coordinate(self) -> EvidenceCoordinateV1:
        _require_identity(self.evidence_id, field_name="evidence_id", pattern=_EVIDENCE_ID_PATTERN)
        _require_non_placeholder(self.locator, field_name="locator")
        _require_non_placeholder(self.claim, field_name="claim")
        test_only_roles = {
            EvidenceRole.DIRECT_BACKEND_BEHAVIOR,
            EvidenceRole.ADAPTER_DETECTOR,
            EvidenceRole.CLI_SUCCESS,
            EvidenceRole.CLI_REFUSAL,
            EvidenceRole.TUI_PARITY,
            EvidenceRole.TUI_REACHABILITY,
        }
        if self.role in test_only_roles and self.kind is not EvidenceKind.TEST:
            raise ValueError(f"{self.role.value} evidence must coordinate a test")
        return self


class AxisAssessmentV1(BaseModel):
    """Applicability and proof for one axis, never collapsed into one status."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    axis: LedgerCapabilityAxis
    applicability: ApplicabilityState
    proof: AxisProofState
    surface_state: SurfaceCapabilityState | None = None
    evidence: tuple[EvidenceCoordinateV1, ...] = ()

    @model_validator(mode="after")
    def _check_independent_axis_state(self) -> AxisAssessmentV1:
        if self.axis in _SURFACE_AXES and self.surface_state is None:
            raise ValueError(f"{self.axis.value} requires a surface_state")
        if self.axis not in _SURFACE_AXES and self.surface_state is not None:
            raise ValueError(f"{self.axis.value} must not carry a surface_state")
        if self.applicability is ApplicabilityState.NOT_APPLICABLE:
            if self.proof is not AxisProofState.NOT_APPLICABLE:
                raise ValueError("a non-applicable axis must have not_applicable proof")
            if self.surface_state not in {None, SurfaceCapabilityState.NOT_APPLICABLE}:
                raise ValueError("a non-applicable surface must have not_applicable state")
            if self.evidence:
                raise ValueError("a non-applicable axis must not carry evidence")
        else:
            if self.proof is AxisProofState.NOT_APPLICABLE:
                raise ValueError("an applicable axis must carry unproven, partial, or proven proof")
            if self.surface_state is SurfaceCapabilityState.NOT_APPLICABLE:
                raise ValueError("an applicable surface must not have not_applicable state")
            if self.proof is AxisProofState.PROVEN and self.surface_state is SurfaceCapabilityState.ABSENT:
                raise ValueError("an absent surface cannot have proven proof")
        if any(self.axis not in coordinate.axes for coordinate in self.evidence):
            raise ValueError("axis evidence must name the axis it supports")
        if len({coordinate.evidence_id for coordinate in self.evidence}) != len(self.evidence):
            raise ValueError("axis evidence contains duplicate evidence_id values")
        return self


class CapabilityFindingV1(BaseModel):
    """A bounded unresolved issue with a closed gap class and affected axes."""

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


class LedgerCapabilityRowV1(BaseModel):
    """One reviewed capability/sub-operation in the cross-surface matrix."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    identity: LedgerCapabilityIdentityV1
    semantic_home: CanonicalSemanticHomeV1
    assessments: tuple[AxisAssessmentV1, ...]
    annotations: frozenset[CapabilityAnnotation] = frozenset()
    findings: tuple[CapabilityFindingV1, ...] = ()
    applicability_reviewed: bool
    authority_migration_required: bool
    cli_delegates_to_canonical: bool

    @model_validator(mode="after")
    def _check_complete_row_contract(self) -> LedgerCapabilityRowV1:
        if {assessment.axis for assessment in self.assessments} != set(LedgerCapabilityAxis):
            raise ValueError("assessments must contain exactly one assessment for every Ledger capability axis")
        if len({assessment.axis for assessment in self.assessments}) != len(self.assessments):
            raise ValueError("assessments contains duplicate axes")
        if len({finding.finding_id for finding in self.findings}) != len(self.findings):
            raise ValueError("findings contains duplicate finding_id values")

        cli = self.assessment(LedgerCapabilityAxis.CLI)
        tui = self.assessment(LedgerCapabilityAxis.TUI)
        if (
            CapabilityAnnotation.CLI_OWNED in self.annotations
            and cli.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("cli_owned requires an applicable CLI axis")
        if (
            CapabilityAnnotation.DELEGATING in self.annotations
            and cli.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("delegating requires an applicable CLI axis")
        if self.cli_delegates_to_canonical and cli.applicability is not ApplicabilityState.APPLICABLE:
            raise ValueError("cli_delegates_to_canonical requires an applicable CLI axis")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("component_only requires an applicable TUI axis")
        if (
            CapabilityAnnotation.INSTALLED in self.annotations
            and tui.applicability is not ApplicabilityState.APPLICABLE
        ):
            raise ValueError("installed requires an applicable TUI axis")
        if (
            CapabilityAnnotation.COMPONENT_ONLY in self.annotations
            and CapabilityAnnotation.INSTALLED in self.annotations
        ):
            raise ValueError("a TUI capability cannot be both component_only and installed")
        if CapabilityAnnotation.DELEGATING in self.annotations and CapabilityAnnotation.CLI_OWNED in self.annotations:
            raise ValueError("a CLI capability cannot be both cli_owned and delegating")
        return self

    def assessment(self, axis: LedgerCapabilityAxis) -> AxisAssessmentV1:
        """Return the one assessment for ``axis`` after completeness validation."""
        return next(assessment for assessment in self.assessments if assessment.axis is axis)

    def evidence_with_role(self, role: EvidenceRole, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Whether the row has evidence of a role, optionally for one axis."""
        assessments: Iterable[AxisAssessmentV1] = self.assessments
        if axis is not None:
            assessments = (self.assessment(axis),)
        return any(coordinate.role is role for assessment in assessments for coordinate in assessment.evidence)

    def has_gap(self, gap_class: LedgerGapClass, *, axis: LedgerCapabilityAxis | None = None) -> bool:
        """Whether an unresolved finding of a class affects the requested axis."""
        return any(
            finding.gap_class is gap_class and (axis is None or axis in finding.affected_axes)
            for finding in self.findings
        )


class LedgerCampaignControlsV1(BaseModel):
    """Campaign-wide ownership and TUI hold facts required by the gate order."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    sole_ledger_parity_plan_owner: str = Field(min_length=1)
    tui_implementation_hold_recorded: bool
    tui_implementation_hold_active: bool

    @model_validator(mode="after")
    def _check_owner(self) -> LedgerCampaignControlsV1:
        _require_non_placeholder(self.sole_ledger_parity_plan_owner, field_name="sole_ledger_parity_plan_owner")
        return self


class LedgerCapabilityMatrixV1(BaseModel):
    """The complete reviewed matrix and campaign facts used to evaluate gates."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    schema_version: int = Field(ge=1)
    controls: LedgerCampaignControlsV1
    rows: tuple[LedgerCapabilityRowV1, ...]
    campaign_evidence: tuple[EvidenceCoordinateV1, ...] = ()

    @model_validator(mode="after")
    def _check_matrix_identity_and_evidence(self) -> LedgerCapabilityMatrixV1:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported Ledger capability matrix schema version: {self.schema_version}")
        row_ids = tuple(row.identity.row_id for row in self.rows)
        if len(set(row_ids)) != len(row_ids):
            raise ValueError("matrix contains duplicate stable row identities")
        campaign_ids = tuple(coordinate.evidence_id for coordinate in self.campaign_evidence)
        if len(set(campaign_ids)) != len(campaign_ids):
            raise ValueError("campaign_evidence contains duplicate evidence_id values")
        return self

    def has_campaign_evidence(self, role: EvidenceRole) -> bool:
        """Whether a campaign-wide evidence coordinate has the requested role."""
        return any(coordinate.role is role for coordinate in self.campaign_evidence)


class GateAssessmentV1(BaseModel):
    """A deterministic gate result; an empty blocker list is a closed gate."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    gate: LedgerGate
    closed: bool
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _check_blocker_shape(self) -> GateAssessmentV1:
        if self.closed and self.blockers:
            raise ValueError("a closed gate cannot carry blockers")
        if not self.closed and not self.blockers:
            raise ValueError("an open gate must describe at least one blocker")
        return self


def _applicable_rows(matrix: LedgerCapabilityMatrixV1, axis: LedgerCapabilityAxis) -> tuple[LedgerCapabilityRowV1, ...]:
    return tuple(row for row in matrix.rows if row.assessment(axis).applicability is ApplicabilityState.APPLICABLE)


def _assessment_is_proven(row: LedgerCapabilityRowV1, axis: LedgerCapabilityAxis) -> bool:
    return row.assessment(axis).proof is AxisProofState.PROVEN


def _gate_assessment(gate: LedgerGate, blockers: list[str]) -> GateAssessmentV1:
    return GateAssessmentV1(gate=gate, closed=not blockers, blockers=tuple(blockers))


def evaluate_ledger_capability_gate(matrix: LedgerCapabilityMatrixV1, gate: LedgerGate) -> GateAssessmentV1:
    """Evaluate one exact G0--G4 closure predicate against ``matrix``.

    The predicates intentionally do not infer a later gate from an earlier
    one. Callers evaluating campaign progression should use
    :func:`evaluate_ledger_capability_gates`, which retains the ordered gate
    dependency as a separate fact.
    """
    blockers: list[str] = []

    if gate is LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE:
        if not matrix.rows:
            blockers.append("the union denominator has no reviewed capability rows")
        if not matrix.controls.sole_ledger_parity_plan_owner:
            blockers.append("Ledger parity plan ownership is not singular")
        if not matrix.controls.tui_implementation_hold_recorded or not matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold is not recorded and active")
        for row in matrix.rows:
            if not row.applicability_reviewed:
                blockers.append(f"{row.identity.row_id}: applicability has not been reviewed")
            for assessment in row.assessments:
                if (
                    assessment.applicability is ApplicabilityState.APPLICABLE
                    and not assessment.evidence
                    and assessment.proof is not AxisProofState.UNPROVEN
                ):
                    blockers.append(
                        f"{row.identity.row_id}: {assessment.axis.value} lacks baseline evidence "
                        "or explicit unproven state",
                    )
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
            if row.authority_migration_required:
                if not row.evidence_with_role(EvidenceRole.DIRECT_BACKEND_BEHAVIOR, axis=LedgerCapabilityAxis.BACKEND):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks direct backend behavior evidence")
                if not row.evidence_with_role(EvidenceRole.ADAPTER_DETECTOR, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: migrated authority lacks an adapter detector")
                if (
                    row.assessment(LedgerCapabilityAxis.CLI).applicability is ApplicabilityState.APPLICABLE
                    and not row.cli_delegates_to_canonical
                ):
                    blockers.append(f"{row.identity.row_id}: applicable CLI does not delegate to the canonical owner")
        return _gate_assessment(gate, blockers)

    if gate is LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS:
        for row in matrix.rows:
            for axis in _G2_AXES:
                if row.assessment(axis).applicability is ApplicabilityState.APPLICABLE and not _assessment_is_proven(
                    row, axis
                ):
                    blockers.append(f"{row.identity.row_id}: applicable {axis.value} axis is not proven")
            for gap_class in _G2_GAP_CLASSES:
                if row.has_gap(gap_class):
                    blockers.append(f"{row.identity.row_id}: {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)

    if gate is LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS:
        for row in _applicable_rows(matrix, LedgerCapabilityAxis.CLI):
            cli = row.assessment(LedgerCapabilityAxis.CLI)
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
            ).applicability is ApplicabilityState.APPLICABLE and not row.evidence_with_role(EvidenceRole.CLI_ARTIFACT):
                blockers.append(f"{row.identity.row_id}: CLI artifact behavior is not evidenced")
            for gap_class in _G3_GAP_CLASSES:
                if row.has_gap(gap_class, axis=LedgerCapabilityAxis.CLI):
                    blockers.append(f"{row.identity.row_id}: CLI {gap_class.value} finding remains")
        return _gate_assessment(gate, blockers)

    if gate is LedgerGate.G4_TUI_ADMISSION_AND_PARITY:
        if matrix.controls.tui_implementation_hold_active:
            blockers.append("the Ledger TUI implementation hold remains active")
        for row in _applicable_rows(matrix, LedgerCapabilityAxis.TUI):
            tui = row.assessment(LedgerCapabilityAxis.TUI)
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


def evaluate_ledger_capability_gates(matrix: LedgerCapabilityMatrixV1) -> tuple[GateAssessmentV1, ...]:
    """Evaluate ordered gates, blocking later closure until all earlier gates close."""
    assessments: list[GateAssessmentV1] = []
    prior_open = False
    for gate in _GATE_ORDER:
        assessment = evaluate_ledger_capability_gate(matrix, gate)
        if prior_open and assessment.closed:
            assessment = GateAssessmentV1(
                gate=gate,
                closed=False,
                blockers=(f"{gate.value} cannot close while an earlier gate remains open",),
            )
        assessments.append(assessment)
        prior_open = prior_open or not assessment.closed
    return tuple(assessments)


def reopened_gates_for_new_capability(row: LedgerCapabilityRowV1) -> frozenset[LedgerGate]:
    """Return gates a newly discovered row necessarily reopens.

    G0 always reopens.  Later gates reopen only when the new row has an
    applicable obligation governed by their predicate; this is deliberately
    conservative for authority and proof findings because those findings can
    affect a surface even when that surface is presently not applicable.
    """
    reopened: set[LedgerGate] = {LedgerGate.G0_DENOMINATOR_AND_OWNERSHIP_FREEZE}
    if row.authority_migration_required or row.has_gap(LedgerGapClass.AUTHORITY):
        reopened.add(LedgerGate.G1_SEMANTIC_AUTHORITY_RECOVERY)
    if any(row.assessment(axis).applicability is ApplicabilityState.APPLICABLE for axis in _G2_AXES):
        reopened.add(LedgerGate.G2_BACKEND_PRODUCT_COMPLETENESS)
    if row.assessment(LedgerCapabilityAxis.CLI).applicability is ApplicabilityState.APPLICABLE:
        reopened.add(LedgerGate.G3_CLI_CLEAN_BREAK_AND_COMPLETENESS)
    if row.assessment(LedgerCapabilityAxis.TUI).applicability is ApplicabilityState.APPLICABLE:
        reopened.add(LedgerGate.G4_TUI_ADMISSION_AND_PARITY)
    return frozenset(reopened)


__all__ = [
    "SCHEMA_VERSION",
    "ApplicabilityState",
    "AxisAssessmentV1",
    "AxisProofState",
    "CanonicalSemanticHomeV1",
    "CapabilityAnnotation",
    "CapabilityFindingV1",
    "EvidenceCoordinateV1",
    "EvidenceKind",
    "EvidenceRole",
    "GateAssessmentV1",
    "LedgerCampaignControlsV1",
    "LedgerCapabilityAxis",
    "LedgerCapabilityIdentityV1",
    "LedgerCapabilityMatrixV1",
    "LedgerCapabilityRowV1",
    "LedgerGapClass",
    "LedgerGate",
    "SurfaceCapabilityState",
    "evaluate_ledger_capability_gate",
    "evaluate_ledger_capability_gates",
    "reopened_gates_for_new_capability",
]
