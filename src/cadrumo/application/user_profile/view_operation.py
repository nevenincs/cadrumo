"""Bounded, revision-pinned pages of the active profile's canonical views."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self, TypedDict, cast
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, model_validator

from ...core.config import override_settings
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
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.user_profile.values import ProfileSetupState
from ..modelo.profile_readiness_gate import (
    modelo_work_profile_baseline_missing_paths,
    modelo_work_profile_baseline_validation_issues,
)
from ..operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from ..wizard.catalogue import build_setup_flow
from ..wizard.persistence import project_answers
from ..workflow.profile_bucket_scan import read_profile_bucket_by_id
from ..workflow.profile_health import ProfileHealthStatus, assess_profile_record_health
from .commands import ProfileValidationIssue
from .overview import ProfileFieldView, build_profile_overview
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_path_values
from .validation import COMPLETENESS_ISSUE_CODES, ProfileValidationService

PROFILE_VIEW_OPERATION_DEFINITION_ID = "user-profile.view"
PROFILE_VIEW_PHASES = ("user-profile.view.read", "user-profile.view.project")
PROFILE_VIEW_MAX_ITEMS = 32
# The result is nested in a settled-operation response and then a runtime frame.
# Keep generous space beneath that frame's 64 KiB ceiling for both envelopes.
PROFILE_VIEW_MAX_RESULT_BYTES = 20_000
_STATUS_FACT_PATHS = frozenset({"identity.tax_id", "activities.description", "iva.regime", "tax_residence.ccaa"})


class _ProfileViewCommon(TypedDict):
    profile_id: UUID
    page_kind: ProfileViewPageKind
    record_revision: int
    content_digest: ContentDigest
    setup_state: ProfileSetupState
    schema_version: int
    valid: bool
    cursor: int


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
            if self.refusal_code is None or self.items or self.next_cursor is not None:
                raise ValueError("refused profile view cannot carry page items or completion")
        else:
            if self.refusal_code is not None or self.cursor + len(self.items) > self.total_items:
                raise ValueError("invalid profile view page")
            if self.cursor < self.total_items and not self.items:
                raise ValueError("profile view cannot claim progress without an item")
            expected_next = self.cursor + len(self.items)
            if self.next_cursor != (expected_next if expected_next < self.total_items else None):
                raise ValueError("profile view continuation does not match page items")
            allowed = {
                ProfileViewPageKind.FACTS: {"fact"},
                ProfileViewPageKind.ISSUES: {"issue"},
                ProfileViewPageKind.READINESS_ISSUES: {"issue"},
                ProfileViewPageKind.OVERVIEW: {"section", "field", "missing", "notice"},
                ProfileViewPageKind.STATUS: {"status"},
            }[self.page_kind]
            if any(item.kind not in allowed for item in self.items):
                raise ValueError("profile view page contains another stream's item")
            if self.page_kind is ProfileViewPageKind.STATUS and (
                self.total_items != 1 or self.cursor != 0 or len(self.items) != 1 or self.next_cursor is not None
            ):
                raise ValueError("profile status must be one complete item")
            if self.page_kind is ProfileViewPageKind.STATUS and any(
                not isinstance(item, ProfileViewStatusItem) or item.health.active_profile != str(self.profile_id)
                for item in self.items
            ):
                raise ValueError("profile status health must match the result profile")
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


def read_profile_view_page(
    request: ProfileViewOperationRequest, *, authority_operation: PinnedAuthorityOperation
) -> ProfileViewOperationResult:
    """Build one bounded page from the exact current encrypted record."""
    profile_decode_context = authority_operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(
        str(request.profile_id), profile_decode_context=profile_decode_context
    ).load(str(request.profile_id))
    with override_settings(cadrumo_output_language=request.output_language.value):
        report = ProfileValidationService(schema=profile_decode_context.schema).validate_record(record)
        require_complete = record.setup_state is ProfileSetupState.COMPLETE
        valid = not any(
            issue.severity.value == "error" and (require_complete or issue.code not in COMPLETENESS_ISSUE_CODES)
            for issue in report.issues
        )
        common: _ProfileViewCommon = {
            "profile_id": request.profile_id,
            "page_kind": request.page_kind,
            "record_revision": record.record_revision,
            "content_digest": record.content_digest,
            "setup_state": record.setup_state,
            "schema_version": report.schema_version,
            "valid": valid,
            "cursor": request.cursor,
        }
        if request.expected_revision is not None and (
            request.expected_revision != record.record_revision
            or request.expected_content_digest != record.content_digest
        ):
            return ProfileViewOperationResult(
                **common,
                outcome="refused",
                refusal_code=ProfileViewRefusalCode.STALE_REVISION,
                total_items=0,
            )
        if request.page_kind is ProfileViewPageKind.FACTS:
            source: tuple[ProfileViewItem, ...] = tuple(
                ProfileViewFactItem(path=path, value=str(value))
                for path, value in sorted(record_to_path_values(record).items())
            )
        elif request.page_kind in {ProfileViewPageKind.ISSUES, ProfileViewPageKind.READINESS_ISSUES}:
            issues = report.issues
            if request.page_kind is ProfileViewPageKind.READINESS_ISSUES:
                seen: set[tuple[str, str | None]] = set()
                distinct: list[ProfileValidationIssue] = []
                for issue in (*report.issues, *modelo_work_profile_baseline_validation_issues(record)):
                    key = (issue.code, issue.path)
                    if key not in seen:
                        seen.add(key)
                        distinct.append(issue)
                issues = tuple(distinct)
            source = tuple(
                ProfileViewIssueItem(
                    severity=issue.severity,
                    code=issue.code,
                    path=issue.path,
                    message=issue.message,
                )
                for issue in issues
            )
        elif request.page_kind is ProfileViewPageKind.STATUS:
            committed = read_profile_bucket_by_id(str(request.profile_id))
            if committed is None or committed.bucket_id != str(request.profile_id):
                return ProfileViewOperationResult(
                    **common,
                    outcome="refused",
                    refusal_code=ProfileViewRefusalCode.PROJECTION_UNAVAILABLE,
                    total_items=0,
                )
            values = record_to_path_values(record)
            health = assess_profile_record_health(
                record,
                source="env_override",
                label=committed.label,
                operation=authority_operation,
            )
            if health.active_profile != str(request.profile_id):
                return ProfileViewOperationResult(
                    **common,
                    outcome="refused",
                    refusal_code=ProfileViewRefusalCode.PROJECTION_UNAVAILABLE,
                    total_items=0,
                )
            if health.status is ProfileHealthStatus.READY:
                status = ProfileHealthStatus.READY
            elif health.status is ProfileHealthStatus.INCOMPLETE:
                status = ProfileHealthStatus.INCOMPLETE
            else:
                return ProfileViewOperationResult(
                    **common,
                    outcome="refused",
                    refusal_code=ProfileViewRefusalCode.PROJECTION_UNAVAILABLE,
                    total_items=0,
                )
            try:
                public_verdict = (
                    None
                    if health.precondition_verdict is None
                    else ProfileViewPreconditionVerdict.from_verdict(health.precondition_verdict)
                )
            except (ValueError, ValidationError):
                return ProfileViewOperationResult(
                    **common,
                    outcome="refused",
                    refusal_code=ProfileViewRefusalCode.PROJECTION_UNAVAILABLE,
                    total_items=0,
                )
            baseline_ready = not modelo_work_profile_baseline_missing_paths(record)
            projection_valid = False
            if health.status is ProfileHealthStatus.READY and baseline_ready:
                try:
                    project_answers(build_setup_flow(authority_operation), values)
                except ValidationError:
                    pass
                else:
                    projection_valid = True
            source = (
                ProfileViewStatusItem(
                    display_name=committed.label,
                    health=ProfileViewHealth(
                        active_profile=str(request.profile_id),
                        status=status,
                        missing_required=health.missing_required,
                        precondition_verdict=public_verdict,
                    ),
                    baseline_ready=baseline_ready,
                    projection_valid=projection_valid,
                    facts=tuple(
                        ProfileViewFactItem(path=path, value=str(values[path]))
                        for path in sorted(_STATUS_FACT_PATHS)
                        if path in values
                    ),
                ),
            )
        else:
            overview = build_profile_overview(record, schema=profile_decode_context.schema)
            if any(notice.action is not None for notice in overview.notices):
                return ProfileViewOperationResult(
                    **common,
                    outcome="refused",
                    refusal_code=ProfileViewRefusalCode.PROJECTION_UNAVAILABLE,
                    total_items=0,
                )
            source = (
                tuple(
                    item
                    for section in overview.sections
                    for item in (
                        ProfileViewSectionItem(
                            key=section.key,
                            title=section.title,
                            summary=section.summary,
                            repeatable=section.repeatable,
                        ),
                        *(ProfileViewFieldItem(section_key=section.key, field=field) for field in section.fields),
                    )
                )
                + tuple(ProfileViewMissingItem(path=path) for path in overview.missing_required)
                + tuple(
                    ProfileViewNoticeItem(
                        severity=notice.severity,
                        code=notice.code,
                        message=notice.message,
                        context=(
                            None
                            if notice.context is None
                            else tuple(
                                ProfileViewNoticeContextEntry(key=key, value=value)
                                for key, value in sorted(notice.context.items())
                            )
                        ),
                    )
                    for notice in overview.notices
                )
            )
        if request.cursor > len(source):
            # An out-of-range cursor cannot masquerade as a completed page.
            return ProfileViewOperationResult(
                **common,
                outcome="refused",
                refusal_code=ProfileViewRefusalCode.STALE_REVISION,
                total_items=len(source),
            )
        selected: list[ProfileViewItem] = []
        for item in source[request.cursor : request.cursor + request.limit]:
            candidate = (*selected, item)
            next_cursor = request.cursor + len(candidate)
            page = ProfileViewOperationResult(
                **common,
                outcome="page",
                total_items=len(source),
                items=candidate,
                next_cursor=next_cursor if next_cursor < len(source) else None,
            )
            if len(page.model_dump_json().encode("utf-8")) > PROFILE_VIEW_MAX_RESULT_BYTES:
                if not selected:
                    return ProfileViewOperationResult(
                        **common,
                        outcome="refused",
                        refusal_code=ProfileViewRefusalCode.ITEM_TOO_LARGE,
                        total_items=len(source),
                    )
                break
            selected.append(item)
        next_cursor = request.cursor + len(selected)
        return ProfileViewOperationResult(
            **common,
            outcome="page",
            total_items=len(source),
            items=tuple(selected),
            next_cursor=next_cursor if next_cursor < len(source) else None,
        )
