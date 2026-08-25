"""Frontend-neutral immutable projection for profile status surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from ...core.presentation import NoticePresentation

if TYPE_CHECKING:
    from cadrumo.application.workflow.state_models import WorkflowState
    from ...core.json_contract import Notice
    from ...domain.user_profile import ProfileFieldView, ProfileSchemaDefinition, UserProfileRecord


@dataclass(frozen=True, slots=True)
class StatusFactRow:
    """One safe resolved profile fact prepared for presentation."""

    label: str
    value: str
    masked: bool = False


@dataclass(frozen=True, slots=True)
class StatusProfileRow:
    """One registered profile bucket prepared for presentation."""

    label: str
    setup_state: str | None = None
    active: bool = False


@dataclass(frozen=True, slots=True)
class StatusAuthView:
    """Authentication and unlocked-session facts prepared for presentation."""

    provider: str | None = None
    login_ready: bool = False
    subject: str | None = None
    certificate_source: str | None = None
    idle_deadline: datetime | None = None
    absolute_deadline: datetime | None = None


@dataclass(frozen=True, slots=True)
class StatusPageData:
    """Complete read-only status projection shared by entrypoints."""

    active_profile_label: str | None = None
    facts: tuple[StatusFactRow, ...] = ()
    profiles: tuple[StatusProfileRow, ...] = ()
    auth: StatusAuthView = field(default_factory=StatusAuthView)
    notices: tuple[NoticePresentation, ...] = ()


def build_status_page_data() -> StatusPageData:
    """Assemble the safe read-only status projection from application authorities.

    Each zone fails independently. A missing active profile, unreadable record,
    or unavailable live session therefore leaves only that zone unavailable;
    the projection never turns an operator-facing status read into a traceback.
    """
    from .presentation import notice_presentation

    active_uuid, active_label = _resolve_active_identity()
    state = _load_workflow_state()
    record = _read_active_record(state)
    return StatusPageData(
        active_profile_label=active_label,
        facts=_build_fact_rows(record),
        profiles=_build_profile_rows(active_uuid, record=record),
        auth=_build_auth_view(state, active_uuid=active_uuid),
        notices=(
            tuple(notice_presentation(notice) for notice in build_active_profile_notices(record))
            if active_uuid is not None
            else ()
        ),
    )


def _guarded_read_errors() -> tuple[type[BaseException], ...]:
    """Return the bounded refusal family a read-only status zone may absorb."""
    from sqlalchemy.exc import StatementError

    from ...core.errors import CadrumoError

    return (CadrumoError, OSError, StatementError)


def _resolve_active_identity() -> tuple[str | None, str | None]:
    """Return the active profile identifier and display label, or no identity."""
    from ...core.bucket_pointer import resolve_active_bucket_id
    from cadrumo.application.workflow.profile_bucket_scan import read_profile_bucket_by_id

    try:
        active_uuid = resolve_active_bucket_id()
        if not active_uuid:
            return None, None
        pointer = read_profile_bucket_by_id(active_uuid)
    except _guarded_read_errors():
        return None, None
    return active_uuid, pointer.label if pointer is not None else active_uuid


def _load_workflow_state() -> WorkflowState | None:
    """Load workflow state without turning unavailable custody into a failure."""
    from cadrumo.application.workflow.persistence import workflow_state_repository

    try:
        return workflow_state_repository().load()
    except _guarded_read_errors():
        return None


def _read_active_record(state: WorkflowState | None) -> UserProfileRecord | None:
    """Read the active encrypted profile record when its session permits it."""
    if state is None:
        return None
    try:
        return state.active_profile_record()
    except _guarded_read_errors():
        return None


def _build_profile_rows(
    active_uuid: str | None,
    *,
    record: UserProfileRecord | None = None,
) -> tuple[StatusProfileRow, ...]:
    """Project registered buckets while keeping locked records opaque."""
    from cadrumo.application.workflow.profile_bucket_scan import list_profile_buckets

    try:
        pointers = sorted(list_profile_buckets().values(), key=lambda pointer: pointer.label.casefold())
    except _guarded_read_errors():
        return ()
    return tuple(
        StatusProfileRow(
            label=pointer.label,
            setup_state=(record.setup_state.value if record is not None and pointer.bucket_id == active_uuid else None),
            active=pointer.bucket_id == active_uuid,
        )
        for pointer in pointers
    )


def _build_auth_view(state: WorkflowState | None, *, active_uuid: str | None) -> StatusAuthView:
    """Project application auth state and the live unlock-session deadlines."""
    from ...core.i18n import tr
    from ...domain.user_profile import load_user_profile_schema
    from .overview import profile_field_choices

    idle_deadline, absolute_deadline = _active_profile_session_deadlines(active_uuid)
    if state is None:
        return StatusAuthView(idle_deadline=idle_deadline, absolute_deadline=absolute_deadline)
    provider = None
    if state.auth.provider:
        field = load_user_profile_schema().field("auth.provider")
        provider = next(
            (
                choice.label
                for choice in profile_field_choices(field, path="auth.provider")
                if choice.value == state.auth.provider
            ),
            tr("flows.status.auth.provider_unknown"),
        )
    return StatusAuthView(
        provider=provider,
        login_ready=state.auth.authenticated_at is not None,
        subject=state.auth.subject,
        certificate_source=state.auth.active_certificate_source,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
    )


def _active_profile_session_deadlines(active_uuid: str | None) -> tuple[datetime | None, datetime | None]:
    """Return live-session deadlines only when the session serves this profile."""
    from .login_session_port import profile_current_bucket_session, profile_session_serves_bucket

    if active_uuid is None:
        return None, None
    try:
        session = profile_current_bucket_session()
        if session is None or not profile_session_serves_bucket(session, active_uuid):
            return None, None
    except RuntimeError:
        return None, None
    return session.idle_deadline, session.absolute_deadline


def build_active_profile_notices(record: UserProfileRecord | None) -> tuple[Notice, ...]:
    """Return operator advisories shared by status and profile overview surfaces."""
    if record is None:
        return ()
    from .cotejo_apply import censo_divergence_notice

    notices: list[Notice] = []
    divergence_notice = censo_divergence_notice(record)
    if divergence_notice is not None:
        notices.append(divergence_notice)
    history_notice = _no_aeat_history_notice(record)
    if history_notice is not None:
        notices.append(history_notice)
    return tuple(notices)


def _no_aeat_history_notice(record: UserProfileRecord) -> Notice | None:
    """Read official-history evidence and return the application-owned advisory."""
    from pydantic import ValidationError

    from ...domain.calculations.registry import derive_tax_route
    from ..calculations import CalculationObservationRepository
    from ..overview import no_aeat_history_notice
    from .projections import projection_for_taxpayer

    try:
        tax_route = derive_tax_route(projection_for_taxpayer(record))
    except ValidationError:
        tax_route = None
    try:
        observations = tuple(CalculationObservationRepository().iter_records())
    except _guarded_read_errors():
        return None
    return no_aeat_history_notice(tuple(payload.source_kind for payload in observations), tax_route=tax_route)


def _build_fact_rows(
    record: UserProfileRecord | None,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> tuple[StatusFactRow, ...]:
    """Project facts with the same schema labels and masking as profile overview."""
    from ...domain.user_profile import load_user_profile_schema
    from .overview import build_profile_overview
    from .projections import record_to_path_values

    if record is None:
        return ()
    values = record_to_path_values(record)
    if not values:
        return ()
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    overview = build_profile_overview(record, schema=resolved_schema)
    views = {field.path: field for section in overview.sections for field in section.fields}
    return tuple(_build_fact_row(path=path, view=views.get(path), schema=resolved_schema) for path in sorted(values))


def _build_fact_row(
    *,
    path: str,
    view: ProfileFieldView | None,
    schema: ProfileSchemaDefinition,
) -> StatusFactRow:
    """Render one stored field from its declared label, choice, and sensitivity."""
    from ...core.i18n import tr
    from ...domain.user_profile import UserProfileError, section_field_key
    from .overview import mask_profile_field

    try:
        field_def = schema.field(section_field_key(path))
    except UserProfileError:
        return StatusFactRow(
            label=tr("flows.status.profile.field_unavailable"),
            value=tr("flows.status.profile.value_unavailable"),
            masked=mask_profile_field(path=path, label=path, sensitivity=None),
        )
    masked = mask_profile_field(path=path, label=field_def.description or path, sensitivity=field_def.sensitivity)
    if view is None:
        return StatusFactRow(
            label=tr("flows.status.profile.field_unavailable"),
            value=tr("flows.status.profile.value_unavailable"),
            masked=masked,
        )
    label, value = _status_fact_label_and_value(view)
    return StatusFactRow(label=label, value=value, masked=masked)


def _status_fact_label_and_value(view: ProfileFieldView) -> tuple[str, str]:
    """Return localized display copy for a declared profile field view."""
    from ...core.i18n import tr

    label = view.label
    if view.row_index is not None:
        label = tr("flows.status.profile.repeated_field", label=label, row=view.row_index)
    value = view.value or ""
    if value and view.choices:
        value = next(
            (choice.label for choice in view.choices if choice.value == value),
            tr("flows.status.profile.value_unavailable"),
        )
    return label, value


__all__ = [
    "StatusAuthView",
    "StatusFactRow",
    "StatusPageData",
    "StatusProfileRow",
    "build_active_profile_notices",
    "build_status_page_data",
]
