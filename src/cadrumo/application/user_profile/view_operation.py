"""Bounded, revision-pinned pages of the active profile's canonical views."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self, cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.errors.severity import BaseSeverity
from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.json_contract import NoticeSeverity
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from ...domain.user_profile.values import ProfileSetupState
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..workflow.profile_health import ProfileHealthStatus
from .overview import ProfileFieldView

PROFILE_VIEW_OPERATION_DEFINITION_ID = "user-profile.view"
PROFILE_VIEW_PHASES = ("user-profile.view.read", "user-profile.view.project")
PROFILE_VIEW_MAX_ITEMS = 32
# The result is nested in a settled-operation response and then a runtime frame.
# Keep generous space beneath that frame's 64 KiB ceiling for both envelopes.
PROFILE_VIEW_MAX_RESULT_BYTES = 20_000
_STATUS_FACT_PATHS = frozenset({"identity.tax_id", "activities.description", "iva.regime", "tax_residence.ccaa"})


class ProfileViewPageKind(StrEnum):
    """One independent page stream over a single profile revision."""

    FACTS = "facts"
    ISSUES = "issues"
    READINESS_ISSUES = "readiness_issues"
    OVERVIEW = "overview"
    STATUS = "status"


class ProfileViewOperationRequest(BaseModel):
    """Read one page, optionally pinned to a previously observed revision."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    page_kind: ProfileViewPageKind
    cursor: NonNegativeInt = 0
    limit: int = Field(default=PROFILE_VIEW_MAX_ITEMS, ge=1, le=PROFILE_VIEW_MAX_ITEMS)
    expected_revision: int | None = Field(default=None, ge=1)
    expected_content_digest: ContentDigest | None = None
    output_language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_complete_pin(self) -> Self:
        if (self.expected_revision is None) != (self.expected_content_digest is None):
            raise ValueError("profile view revision and digest must be pinned together")
        if self.cursor and self.expected_revision is None:
            raise ValueError("a continuation requires its exact profile revision and digest")
        return self


class ProfileViewFactItem(BaseModel):
    """One exact stored profile fact."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["fact"] = "fact"
    path: str
    value: str


class ProfileViewEvidenceValue(BaseModel):
    """One supported canonical health evidence value on the public wire."""

    model_config = STRICT_FROZEN_CONFIG

    key: str
    value: str | int | bool


class ProfileViewEvidence(BaseModel):
    """Ordered facts from one canonical failed-condition evidence record."""

    model_config = STRICT_FROZEN_CONFIG

    condition_id: str
    evidence_id: str
    provenance: ActionEvidenceProvenance
    values: tuple[ProfileViewEvidenceValue, ...]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_distinct_ordered_values(self) -> Self:
        keys = tuple(item.key for item in self.values)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("health evidence facts must be distinct and ordered")
        return self


class ProfileViewActionArgument(BaseModel):
    """One supported argument binding from the canonical health verdict."""

    model_config = STRICT_FROZEN_CONFIG

    argument_name: str
    status: ActionArgumentStatus
    value: str | int | bool | None = None
    source: ActionArgumentSource | None = None
    source_key: str | None = None
    source_evidence_id: str | None = None


class ProfileViewPreconditionVerdict(BaseModel):
    """Strict portable shape of the existing application verdict, not a policy evaluator."""

    model_config = STRICT_FROZEN_CONFIG

    failed_condition_id: str
    evidence: tuple[ProfileViewEvidence, ...]
    action: ActionReference | None = None
    argument_bindings: tuple[ProfileViewActionArgument, ...] = ()
    missing_argument_names: tuple[str, ...] = ()
    conditionality: ActionConditionality
    no_recovery_outcome: NoRecoveryOutcome | None = None

    @classmethod
    def from_verdict(cls, verdict: PreconditionVerdict) -> ProfileViewPreconditionVerdict:
        """Copy only supported actual facts, refusing an unrepresentable value."""

        def supported(value: object) -> str | int | bool:
            if type(value) not in {str, int, bool}:
                raise ValueError("health verdict carries an unsupported public value")
            return cast(str | int | bool, value)

        return cls(
            failed_condition_id=verdict.failed_condition_id,
            evidence=tuple(
                ProfileViewEvidence(
                    condition_id=item.condition_id,
                    evidence_id=item.evidence_id,
                    provenance=item.provenance,
                    values=tuple(
                        ProfileViewEvidenceValue(key=key, value=supported(value))
                        for key, value in sorted(item.values.items())
                    ),
                )
                for item in verdict.evidence
            ),
            action=verdict.action,
            argument_bindings=tuple(
                ProfileViewActionArgument(
                    argument_name=item.argument_name,
                    status=item.status,
                    value=None if item.value is None else supported(item.value),
                    source=item.source,
                    source_key=item.source_key,
                    source_evidence_id=item.source_evidence_id,
                )
                for item in verdict.argument_bindings
            ),
            missing_argument_names=verdict.missing_argument_names,
            conditionality=verdict.conditionality,
            no_recovery_outcome=verdict.no_recovery_outcome,
        )

    def to_verdict(self) -> PreconditionVerdict:
        """Revalidate the exact evidence and action through the canonical owner."""
        return PreconditionVerdict(
            failed_condition_id=self.failed_condition_id,
            evidence=tuple(
                ConditionEvidence(
                    condition_id=item.condition_id,
                    evidence_id=item.evidence_id,
                    provenance=item.provenance,
                    values={fact.key: fact.value for fact in item.values},
                )
                for item in self.evidence
            ),
            action=self.action,
            argument_bindings=tuple(
                ActionArgumentBinding(
                    argument_name=item.argument_name,
                    status=item.status,
                    value=item.value,
                    source=item.source,
                    source_key=item.source_key,
                    source_evidence_id=item.source_evidence_id,
                )
                for item in self.argument_bindings
            ),
            missing_argument_names=self.missing_argument_names,
            conditionality=self.conditionality,
            no_recovery_outcome=self.no_recovery_outcome,
        )

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_canonical_verdict(self) -> Self:
        self.to_verdict()
        return self


class ProfileViewHealth(BaseModel):
    """Public subset of the canonical exact-record health verdict."""

    model_config = STRICT_FROZEN_CONFIG

    active_profile: str
    status: Literal[ProfileHealthStatus.READY, ProfileHealthStatus.INCOMPLETE]
    missing_required: tuple[str, ...]
    precondition_verdict: ProfileViewPreconditionVerdict | None = None


class ProfileViewStatusItem(BaseModel):
    """One exact-record health and readiness projection for operator status."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["status"] = "status"
    display_name: str = Field(min_length=1)
    health: ProfileViewHealth
    baseline_ready: bool
    projection_valid: bool
    facts: tuple[ProfileViewFactItem, ...]

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_scoped_facts(self) -> Self:
        paths = tuple(item.path for item in self.facts)
        if paths != tuple(sorted(set(paths))) or any(path not in _STATUS_FACT_PATHS for path in paths):
            raise ValueError("status facts must be distinct, ordered, and scoped")
        return self


class ProfileViewIssueItem(BaseModel):
    """One issue from the canonical validation service."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["issue"] = "issue"
    severity: BaseSeverity
    code: str = Field(min_length=1, max_length=64)
    path: str | None = None
    message: str = Field(max_length=512)


class ProfileViewSectionItem(BaseModel):
    """One overview section header in schema order."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["section"] = "section"
    key: str
    title: str
    summary: str
    repeatable: bool


class ProfileViewFieldItem(BaseModel):
    """One schema field from its overview section."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["field"] = "field"
    section_key: str
    field: ProfileFieldView


class ProfileViewMissingItem(BaseModel):
    """One required path still absent from the overview."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["missing"] = "missing"
    path: str


class ProfileViewNoticeContextEntry(BaseModel):
    """One deterministic non-action notice context pair."""

    model_config = STRICT_FROZEN_CONFIG
    key: str
    value: str


class ProfileViewNoticeItem(BaseModel):
    """One overview notice from the canonical projector."""

    model_config = STRICT_FROZEN_CONFIG
    kind: Literal["notice"] = "notice"
    severity: NoticeSeverity
    code: str
    message: str
    context: tuple[ProfileViewNoticeContextEntry, ...] | None = None


type ProfileViewItem = Annotated[
    ProfileViewFactItem
    | ProfileViewStatusItem
    | ProfileViewIssueItem
    | ProfileViewSectionItem
    | ProfileViewFieldItem
    | ProfileViewMissingItem
    | ProfileViewNoticeItem,
    Field(discriminator="kind"),
]


class ProfileViewRefusalCode(StrEnum):
    """A read that cannot truthfully yield a complete page stream."""

    STALE_REVISION = "stale_revision"
    ITEM_TOO_LARGE = "item_too_large"
    PROJECTION_UNAVAILABLE = "projection_unavailable"


def _validate_refused_page(result: ProfileViewOperationResult) -> None:
    if result.refusal_code is None or result.items or result.next_cursor is not None:
        raise ValueError("refused profile view cannot carry page items or completion")


def _validate_page_item_kinds(result: ProfileViewOperationResult) -> None:
    allowed = {
        ProfileViewPageKind.FACTS: {"fact"},
        ProfileViewPageKind.ISSUES: {"issue"},
        ProfileViewPageKind.READINESS_ISSUES: {"issue"},
        ProfileViewPageKind.OVERVIEW: {"section", "field", "missing", "notice"},
        ProfileViewPageKind.STATUS: {"status"},
    }[result.page_kind]
    if any(item.kind not in allowed for item in result.items):
        raise ValueError("profile view page contains another stream's item")


def _validate_status_page(result: ProfileViewOperationResult) -> None:
    if result.total_items != 1 or result.cursor != 0 or len(result.items) != 1 or result.next_cursor is not None:
        raise ValueError("profile status must be one complete item")
    if any(
        not isinstance(item, ProfileViewStatusItem) or item.health.active_profile != str(result.profile_id)
        for item in result.items
    ):
        raise ValueError("profile status health must match the result profile")


def _validate_successful_page(result: ProfileViewOperationResult) -> None:
    if result.refusal_code is not None or result.cursor + len(result.items) > result.total_items:
        raise ValueError("invalid profile view page")
    if result.cursor < result.total_items and not result.items:
        raise ValueError("profile view cannot claim progress without an item")
    expected_next = result.cursor + len(result.items)
    if result.next_cursor != (expected_next if expected_next < result.total_items else None):
        raise ValueError("profile view continuation does not match page items")
    _validate_page_item_kinds(result)
    if result.page_kind is ProfileViewPageKind.STATUS:
        _validate_status_page(result)


class ProfileViewOperationResult(BaseModel):
    """An encrypted page or an explicit refusal; neither claims a profile effect."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    page_kind: ProfileViewPageKind
    outcome: Literal["page", "refused"]
    refusal_code: ProfileViewRefusalCode | None = None
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest
    setup_state: ProfileSetupState
    schema_version: int = Field(ge=1)
    valid: bool
    cursor: NonNegativeInt
    next_cursor: NonNegativeInt | None = None
    total_items: NonNegativeInt
    items: tuple[ProfileViewItem, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_page(self) -> Self:
        if self.outcome == "refused":
            _validate_refused_page(self)
        else:
            _validate_successful_page(self)
        return self


class ProfileViewOperationProjection(ProfileViewOperationResult):
    """The registered result released only after PROFILE_VALUES disclosure."""


def project_profile_view_result(result: BaseModel, receipt: object, /) -> BaseModel:
    """Release a page only for its exact settled profile subject."""
    from ...core.operations import profile_operation_subject
    from ..operations.models import OperationTerminalReceipt

    if not isinstance(result, ProfileViewOperationResult) or not isinstance(receipt, OperationTerminalReceipt):
        raise TypeError("unexpected profile view result or receipt")
    if (
        receipt.identity.definition_id != PROFILE_VIEW_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
    ):
        raise ValueError("profile view result does not match its settled subject")
    return ProfileViewOperationProjection.model_validate(result.model_dump(mode="python"))
