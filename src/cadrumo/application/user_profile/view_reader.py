"""Build bounded, revision-pinned pages from the current encrypted profile record.

Core types: :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict
from uuid import UUID

from pydantic import ValidationError

from ...core.config import override_settings
from ...core.identity.digest import ContentDigest
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ..modelo.profile_readiness_gate import (
    modelo_work_profile_baseline_missing_paths,
    modelo_work_profile_baseline_validation_issues,
)
from ..wizard.catalogue import build_setup_flow
from ..wizard.persistence import project_answers
from ..workflow.profile_bucket_scan import read_profile_bucket_by_id
from ..workflow.profile_health import ProfileHealthStatus, assess_profile_record_health
from .commands import ProfileValidationIssue, ProfileValidationReport
from .overview import build_profile_overview
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_path_values
from .question_view import profile_question_items
from .validation import COMPLETENESS_ISSUE_CODES, ProfileValidationService
from .view_operation import (
    PROFILE_VIEW_MAX_RESULT_BYTES,
    ProfileViewFactItem,
    ProfileViewFieldItem,
    ProfileViewHealth,
    ProfileViewIssueItem,
    ProfileViewItem,
    ProfileViewMissingItem,
    ProfileViewNoticeContextEntry,
    ProfileViewNoticeItem,
    ProfileViewOperationRequest,
    ProfileViewOperationResult,
    ProfileViewPageKind,
    ProfileViewPreconditionVerdict,
    ProfileViewRefusalCode,
    ProfileViewSectionItem,
    ProfileViewStatusItem,
)

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


def _refused_page(
    common: _ProfileViewCommon,
    refusal_code: ProfileViewRefusalCode,
    *,
    total_items: int = 0,
) -> ProfileViewOperationResult:
    return ProfileViewOperationResult(
        **common,
        outcome="refused",
        refusal_code=refusal_code,
        total_items=total_items,
    )


def _is_profile_view_valid(record: UserProfileRecord, report: ProfileValidationReport) -> bool:
    setup_state = record.setup_state
    require_complete = setup_state is ProfileSetupState.COMPLETE
    return not any(
        issue.severity.value == "error" and (require_complete or issue.code not in COMPLETENESS_ISSUE_CODES)
        for issue in report.issues
    )


def _build_fact_source(record: UserProfileRecord) -> tuple[ProfileViewItem, ...]:
    return tuple(
        ProfileViewFactItem(path=path, value=value) for path, value in sorted(record_to_path_values(record).items())
    )


def _read_issue_rows(
    request: ProfileViewOperationRequest,
    record: UserProfileRecord,
    report: ProfileValidationReport,
) -> tuple[ProfileValidationIssue, ...]:
    if request.page_kind is not ProfileViewPageKind.READINESS_ISSUES:
        return report.issues
    seen: set[tuple[str, str | None]] = set()
    distinct: list[ProfileValidationIssue] = []
    for issue in (*report.issues, *modelo_work_profile_baseline_validation_issues(record)):
        key = (issue.code, issue.path)
        if key not in seen:
            seen.add(key)
            distinct.append(issue)
    return tuple(distinct)


def _build_issue_source(
    request: ProfileViewOperationRequest,
    record: UserProfileRecord,
    report: ProfileValidationReport,
) -> tuple[ProfileViewItem, ...]:
    return tuple(
        ProfileViewIssueItem(
            severity=issue.severity,
            code=issue.code,
            path=issue.path,
            message=issue.message,
        )
        for issue in _read_issue_rows(request, record, report)
    )


def _public_status_health(
    request: ProfileViewOperationRequest,
    record: UserProfileRecord,
    label: str,
    authority_operation: PinnedAuthorityOperation,
) -> ProfileViewHealth | None:
    health = assess_profile_record_health(
        record,
        source="env_override",
        label=label,
        operation=authority_operation,
    )
    if health.active_profile != str(request.profile_id):
        return None
    if health.status is ProfileHealthStatus.READY:
        status = ProfileHealthStatus.READY
    elif health.status is ProfileHealthStatus.INCOMPLETE:
        status = ProfileHealthStatus.INCOMPLETE
    else:
        return None
    try:
        public_verdict = (
            None
            if health.precondition_verdict is None
            else ProfileViewPreconditionVerdict.from_verdict(health.precondition_verdict)
        )
    except (ValueError, ValidationError):
        return None
    return ProfileViewHealth(
        active_profile=str(request.profile_id),
        status=status,
        missing_required=health.missing_required,
        precondition_verdict=public_verdict,
    )


def _status_projection_is_valid(
    authority_operation: PinnedAuthorityOperation,
    values: Mapping[str, str],
    health: ProfileViewHealth,
    baseline_ready: bool,
) -> bool:
    if health.status is not ProfileHealthStatus.READY or not baseline_ready:
        return False
    try:
        project_answers(build_setup_flow(authority_operation), values)
    except ValidationError:
        return False
    return True


def _build_status_source(
    request: ProfileViewOperationRequest,
    record: UserProfileRecord,
    authority_operation: PinnedAuthorityOperation,
    common: _ProfileViewCommon,
) -> tuple[ProfileViewItem, ...] | ProfileViewOperationResult:
    committed = read_profile_bucket_by_id(str(request.profile_id))
    if committed is None or committed.bucket_id != str(request.profile_id):
        return _refused_page(common, ProfileViewRefusalCode.PROJECTION_UNAVAILABLE)
    values = record_to_path_values(record)
    health = _public_status_health(request, record, committed.label, authority_operation)
    if health is None:
        return _refused_page(common, ProfileViewRefusalCode.PROJECTION_UNAVAILABLE)
    baseline_ready = not modelo_work_profile_baseline_missing_paths(record)
    projection_valid = _status_projection_is_valid(authority_operation, values, health, baseline_ready)
    status_item = ProfileViewStatusItem(
        display_name=committed.label,
        health=health,
        baseline_ready=baseline_ready,
        projection_valid=projection_valid,
        facts=tuple(
            ProfileViewFactItem(path=path, value=values[path]) for path in sorted(_STATUS_FACT_PATHS) if path in values
        ),
    )
    return (status_item,)


def _build_overview_source(
    record: UserProfileRecord,
    common: _ProfileViewCommon,
    schema: ProfileSchemaDefinition,
) -> tuple[ProfileViewItem, ...] | ProfileViewOperationResult:
    overview = build_profile_overview(record, schema=schema)
    if any(notice.action is not None for notice in overview.notices):
        return _refused_page(common, ProfileViewRefusalCode.PROJECTION_UNAVAILABLE)
    section_items = tuple(
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
    missing_items = tuple(ProfileViewMissingItem(path=path) for path in overview.missing_required)
    notice_items = tuple(
        ProfileViewNoticeItem(
            severity=notice.severity,
            code=notice.code,
            message=notice.message,
            context=(
                None
                if notice.context is None
                else tuple(
                    ProfileViewNoticeContextEntry(key=key, value=value) for key, value in sorted(notice.context.items())
                )
            ),
        )
        for notice in overview.notices
    )
    return (*section_items, *missing_items, *notice_items)


def _build_page_source(
    request: ProfileViewOperationRequest,
    record: UserProfileRecord,
    report: ProfileValidationReport,
    authority_operation: PinnedAuthorityOperation,
    common: _ProfileViewCommon,
    schema: ProfileSchemaDefinition,
) -> tuple[ProfileViewItem, ...] | ProfileViewOperationResult:
    if request.page_kind is ProfileViewPageKind.FACTS:
        return _build_fact_source(record)
    if request.page_kind is ProfileViewPageKind.PREFERENCES:
        value = record_to_path_values(record).get(PROFILE_OUTPUT_LANGUAGE_PATH)
        return () if value is None else (ProfileViewFactItem(path=PROFILE_OUTPUT_LANGUAGE_PATH, value=value),)
    if request.page_kind is ProfileViewPageKind.QUESTIONS:
        return profile_question_items(build_setup_flow(authority_operation), record_to_path_values(record))
    if request.page_kind in {ProfileViewPageKind.ISSUES, ProfileViewPageKind.READINESS_ISSUES}:
        return _build_issue_source(request, record, report)
    if request.page_kind is ProfileViewPageKind.STATUS:
        return _build_status_source(request, record, authority_operation, common)
    return _build_overview_source(record, common, schema)


def _paginate_source(
    request: ProfileViewOperationRequest,
    common: _ProfileViewCommon,
    source: tuple[ProfileViewItem, ...],
) -> ProfileViewOperationResult:
    if request.cursor > len(source):
        # An out-of-range cursor cannot masquerade as a completed page.
        return _refused_page(common, ProfileViewRefusalCode.STALE_REVISION, total_items=len(source))
    candidates = source[request.cursor : request.cursor + request.limit]

    def page_for(count: int) -> ProfileViewOperationResult:
        candidate = candidates[:count]
        next_cursor = request.cursor + len(candidate)
        return ProfileViewOperationResult(
            **common,
            outcome="page",
            total_items=len(source),
            items=candidate,
            next_cursor=next_cursor if next_cursor < len(source) else None,
        )

    # Normal pages fit: serialize once, not each increasingly long prefix.
    # For a byte-limited page, find the largest fitting prefix in logarithmic
    # probes. Items and order, the byte ceiling and indivisible refusal remain
    # identical to the sequential collector.
    page = page_for(len(candidates))
    if len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES:
        return page
    low, high = 0, len(candidates) - 1
    best: ProfileViewOperationResult | None = None
    while low < high:
        count = (low + high + 1) // 2
        page = page_for(count)
        if len(page.model_dump_json().encode("utf-8")) <= PROFILE_VIEW_MAX_RESULT_BYTES:
            low, best = count, page
        else:
            high = count - 1
    if low == 0:
        return _refused_page(common, ProfileViewRefusalCode.ITEM_TOO_LARGE, total_items=len(source))
    return best if best is not None else page_for(low)


def read_profile_view_page(
    request: ProfileViewOperationRequest,
    *,
    authority_operation: PinnedAuthorityOperation,
) -> ProfileViewOperationResult:
    """Build one bounded page from the exact current encrypted record."""
    profile_decode_context = authority_operation.profile_decode_context()
    record = ProfileRecordRepository.for_current_session(
        str(request.profile_id), profile_decode_context=profile_decode_context
    ).load(str(request.profile_id))
    with override_settings(cadrumo_output_language=request.output_language.value):
        report = ProfileValidationService(schema=profile_decode_context.schema).validate_record(record)
        valid = _is_profile_view_valid(record, report)
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
            return _refused_page(common, ProfileViewRefusalCode.STALE_REVISION)
        source = _build_page_source(
            request,
            record,
            report,
            authority_operation,
            common,
            profile_decode_context.schema,
        )
        if isinstance(source, ProfileViewOperationResult):
            return source
        return _paginate_source(request, common, source)
