"""Capability-selecting presenter for the read-only status page.

This entry-point seam lets ``aeat config profile status`` render the
full-screen read-only status surface on a capable interactive console
while leaving the machine contract untouched: a ``--format json`` caller
and any non-interactive (piped / dumb-terminal / CI) host fall straight
through to the existing envelope path. The adapter tier may name Textual
but must not reach the application layer, so this entry-point module
gathers the view-model from the application authorities — the active
profile record (:class:`UserProfileRecord`), the profile bucket scan, the
workflow auth state, and the recovery-wrapper status — masking each fact
by its declared :class:`SensitivityClass` — and injects the assembled
:class:`~cadrumo.adapters.inbound.tui.StatusPageData` into the adapter,
mirroring the setup-wizard frontend seam.

The presenter reads nothing back and mutates nothing: every zone is a
projection of an existing authority, so the surface is read-only by
construction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from .._common import _format_of

if TYPE_CHECKING:
    from datetime import datetime

    from ....adapters.inbound.tui import (
        StatusAuthView,
        StatusFactRow,
        StatusPageData,
        StatusProfileRow,
        StatusRecoveryView,
    )
    from ....application.workflow import WorkflowState
    from ....core.json_contract import Notice
    from ....domain.user_profile import ProfileSchemaDefinition, UserProfileRecord


def present_status_tui(ctx: typer.Context) -> bool:
    """Render the read-only status page when the host and format allow it.

    Returns ``True`` when the full-screen surface was presented (the caller
    then returns without emitting the envelope), and ``False`` when a
    ``--format json`` request or a host that cannot host the full-screen
    application means the caller must fall through to the existing envelope
    path. The machine contract is therefore reached unchanged for every
    non-interactive and JSON caller.
    """
    from ....application.flows import detect_frontend_capability
    from ....core.flows import FrontendCapability

    if _format_of(ctx) == "json":
        return False
    if detect_frontend_capability() is not FrontendCapability.FULL_SCREEN:
        return False

    from ....adapters.inbound.tui import StatusApp

    StatusApp(build_status_page_data()).run()
    return True


def build_status_page_data() -> StatusPageData:
    """Assemble the read-only :class:`StatusPageData` from application authorities.

    The status page is the surface an operator reaches precisely WHEN their
    profile is damaged, so it must never traceback: every zone read is guarded
    independently and degrades to an empty / unavailable projection on failure,
    so a locked active bucket, an unreadable workflow state, or a corrupt
    recovery wrapper blanks only its own zone while the others still render.
    """
    from ....adapters.inbound.tui import StatusPageData

    active_uuid, active_label = _resolve_active_identity()
    state = _load_workflow_state()
    record = _read_active_record(state)
    return StatusPageData(
        active_profile_label=active_label,
        facts=_build_fact_rows(record),
        profiles=_build_profile_rows(active_uuid),
        auth=_build_auth_view(state, active_uuid=active_uuid),
        recovery=_build_recovery_view(),
        notices=build_active_profile_notices(record) if active_uuid is not None else (),
    )


def _guarded_read_errors() -> tuple[type[BaseException], ...]:
    """The zone-read error surface: the domain base plus storage-layer faults.

    ``SecretStoreError``, ``StorageValidationError``, ``UserProfileError``, and
    ``WorkflowError`` all derive from ``CadrumoError``, and a torn on-disk read
    raises ``OSError``. SQLAlchemy additionally wraps a refusal raised inside
    encrypted-column key resolution (e.g. the no-active-session refusal — a
    ``CadrumoError``) into its own ``StatementError`` mid-statement, so that
    wrapper must be guarded too or the exact damaged-host states this page
    exists for would traceback. Catching exactly this trio degrades a zone
    without swallowing an arbitrary programming error the way a bare
    ``except Exception`` would.
    """
    from sqlalchemy.exc import StatementError

    from ....core.errors import CadrumoError

    return (CadrumoError, OSError, StatementError)


def _resolve_active_identity() -> tuple[str | None, str | None]:
    """Return the active profile UUID and its display label, degrading to ``None``."""
    from ....application.workflow import read_profile_bucket_by_id
    from ....core import resolve_active_bucket_id

    try:
        active_uuid = resolve_active_bucket_id()
        if not active_uuid:
            return None, None
        pointer = read_profile_bucket_by_id(active_uuid)
    except _guarded_read_errors():
        return None, None
    label = pointer.label if pointer is not None else active_uuid
    return active_uuid, label


def _load_workflow_state() -> WorkflowState | None:
    """Load the workflow state, or ``None`` when it cannot be read."""
    from ....application.workflow import workflow_state_repository

    try:
        return workflow_state_repository().load()
    except _guarded_read_errors():
        return None


def _read_active_record(state: WorkflowState | None) -> UserProfileRecord | None:
    """Read the active profile record, or ``None`` for a locked / absent bucket."""
    if state is None:
        return None
    try:
        return state.active_profile_record()
    except _guarded_read_errors():
        return None


def _build_profile_rows(active_uuid: str | None) -> tuple[StatusProfileRow, ...]:
    """Project the profile bucket scan into rows, degrading to empty on failure."""
    from ....adapters.inbound.tui import StatusProfileRow
    from ....application.workflow import list_profile_buckets

    try:
        pointers = sorted(
            list_profile_buckets(include_tombstoned=True).values(),
            key=lambda pointer: pointer.label.casefold(),
        )
    except _guarded_read_errors():
        return ()
    return tuple(
        StatusProfileRow(
            label=pointer.label,
            status=str(pointer.status.value),
            active=pointer.bucket_id == active_uuid,
        )
        for pointer in pointers
    )


def _build_auth_view(state: WorkflowState | None, *, active_uuid: str | None) -> StatusAuthView:
    """Project the workflow auth state, degrading to an empty view when absent.

    ``idle_deadline`` / ``absolute_deadline`` come from a second, unrelated
    authority: the process's live :class:`~cadrumo.adapters.persistence.storage.BucketSession`
    for the active bucket — the profile-unlock session ``aeat config
    login`` opened — never the AEAT auth state above. Read only when that
    live session actually serves ``active_uuid``, so a status query run
    against one profile can never report another profile's session
    lifetime.
    """
    from ....adapters.inbound.tui import StatusAuthView
    from ....application.user_profile import profile_field_choices
    from ....core.i18n import tr
    from ....domain.user_profile import load_user_profile_schema

    idle_deadline, absolute_deadline = _active_profile_session_deadlines(active_uuid)
    if state is None:
        return StatusAuthView(idle_deadline=idle_deadline, absolute_deadline=absolute_deadline)
    auth = state.auth
    provider = None
    if auth.provider:
        field = load_user_profile_schema().field("auth.provider")
        provider = next(
            (
                choice.label
                for choice in profile_field_choices(field, path="auth.provider")
                if choice.value == auth.provider
            ),
            tr("flows.status.auth.provider_unknown"),
        )
    return StatusAuthView(
        provider=provider,
        login_ready=auth.authenticated_at is not None,
        subject=auth.subject,
        certificate_source=auth.active_certificate_source,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
    )


def _active_profile_session_deadlines(active_uuid: str | None) -> tuple[datetime | None, datetime | None]:
    """Return the live profile session's idle and absolute deadlines, or ``(None, None)``.

    Reads the in-process :class:`~cadrumo.adapters.persistence.storage.BucketSession`
    directly rather than resolving a session: this is a read-only status
    projection and must never mint, resume, or persist anything. A session
    that does not exist, or belongs to a different bucket, is exactly the
    "not currently unlocked" state this page needs to render as absence,
    never as a traceback.
    """
    from ....adapters.persistence.storage import active_bucket_session_serves, current_active_bucket_session

    if active_uuid is None or not active_bucket_session_serves(active_uuid):
        return None, None
    session = current_active_bucket_session()
    if session is None:
        return None, None
    return session.idle_deadline, session.absolute_deadline


def _build_recovery_view() -> StatusRecoveryView:
    """Project the recovery-wrapper status, degrading to not-enrolled on failure."""
    from ....adapters.inbound.tui import StatusRecoveryView
    from ....application.user_profile import inspect_recovery_status

    try:
        recovery = inspect_recovery_status()
    except _guarded_read_errors():
        return StatusRecoveryView()
    return StatusRecoveryView(
        enrolled=recovery.recovery_enrolled,
        fingerprint=recovery.recovery_fingerprint,
    )


def build_active_profile_notices(record: UserProfileRecord | None) -> tuple[Notice, ...]:
    """Project application advisories for every active-profile surface.

    The status page and manager both report the active profile's health,
    so they consume the same typed
    :class:`~cadrumo.core.json_contract.Notice` values a CLI envelope
    already carries — never a second, TUI-only advisory vocabulary.
    Degrades to no notices for a locked or absent bucket, matching every
    other zone this page builds.
    """
    if record is None:
        return ()
    notices: list[Notice] = []
    from ....application.user_profile import censo_divergence_notice

    divergence_notice = censo_divergence_notice(record)
    if divergence_notice is not None:
        notices.append(divergence_notice)
    history_notice = _no_aeat_history_notice()
    if history_notice is not None:
        notices.append(history_notice)
    return tuple(notices)


def _no_aeat_history_notice() -> Notice | None:
    """Point an operator at the filing-history pull when the bucket holds no AEAT-sourced observation.

    Reads the same persisted calculation observations
    :func:`~cadrumo.application.overview.no_aeat_history_notice` was built
    to judge, gathered across every modelo through
    :meth:`~cadrumo.application.calculations.CalculationObservationRepository.iter_records`
    rather than one modelo at a time — the status page asks about the
    profile as a whole, not one filing.
    """
    from ....application.calculations import CalculationObservationRepository
    from ....application.operator_actions import ActionReference
    from ....application.overview import no_aeat_history_notice
    from .._common import resolve_notice_action

    try:
        observations = tuple(CalculationObservationRepository().iter_records())
    except _guarded_read_errors():
        return None
    notice = no_aeat_history_notice(tuple(payload.source_kind for payload in observations))
    if notice is None:
        return None
    return notice.model_copy(
        update={
            "action": resolve_notice_action(
                action=ActionReference(action_id="operator.live.filed.pull_all"),
            ),
        },
    )


def _build_fact_rows(
    record: UserProfileRecord | None,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> tuple[StatusFactRow, ...]:
    """Project the active profile record into masked/labelled fact rows.

    Labels resolve through ``profile_field_label``, the same catalogue the
    profile manager reads, so one field cannot be named two different
    things on two surfaces. The schema's ``description`` is not a label:
    it is long-form authority prose -- ``auth.provider`` runs to four
    sentences -- and mixed-language by design, so rendering it here gave
    the operator a paragraph in a column, in whichever language its author
    happened to write. It also made the two strings one string: improving
    the documentation silently rewrote the screen, and two commits have
    already oscillated that prose between the two jobs. The catalogue
    falls back to ``description`` for a key it does not carry, so an
    untranslated field renders exactly what it renders today; a path with
    no schema field at all falls back to the raw dotted path.

    The masking decision is delegated to ``mask_profile_field``, the one
    authority the profile overview also uses. This surface previously
    carried its own keyword policy, which omitted ``credential`` and so
    printed the Cl@ve credential inputs (``auth.dni_nie``,
    ``auth.numero_soporte``, ``auth.fecha_validez``) in clear while the
    overview masked them.

    Sharing that authority is not enough on its own, because the two
    surfaces have to reach it with the same answer to "which field is
    this". This walk is fact-driven, so it sees the indexed paths a
    repeated fact is stored under -- ``socios.0.nif``,
    ``censo.divergencia.0.axis`` -- and an indexed path matches no schema
    field, so an exact lookup raised and the row fell through to the
    keyword net. That net is deliberately partial: it is a floor under
    facts the schema does not know, and a declared field it does not
    recognise by name would have been decided by its leaf's spelling
    rather than by its declaration. Reducing the path to the field that
    declares it closes that, and closes it in the direction the masking
    authority already chose -- a declaration is never overridden by
    wording, in either direction.

    Indexed facts keep their schema label and add a localized row marker.
    The stored dotted address remains a table key only; it is never display
    copy.

    Masking reads the schema's ``description``, never the localized
    label, for the reason the overview gives: whether a value is a secret
    is a property of the field, not of the language it is being read in,
    and scanning translated copy would let a field whose label in one
    language omits ``password`` render in the clear while its row in
    another masked.

    Args:
        record: The active profile, or ``None`` for no rows at all.
        schema: Optional schema override; the canonical schema when
            omitted. Injected rather than patched so a caller can state
            the declarations a confidentiality decision is read against —
            the shipped schema classes nothing ``SECRET`` inside a
            repeated fact today, so a guard written against it alone
            would be vacuous.
    """
    from ....adapters.inbound.tui import StatusFactRow
    from ....application.user_profile import (
        build_profile_overview,
        mask_profile_field,
        record_to_path_values,
    )
    from ....core.i18n import tr
    from ....domain.user_profile import (
        UserProfileError,
        load_user_profile_schema,
        section_field_key,
    )

    if record is None:
        return ()
    values = record_to_path_values(record)
    if not values:
        return ()
    resolved_schema = schema if schema is not None else load_user_profile_schema()
    overview = build_profile_overview(record, schema=resolved_schema)
    views = {field.path: field for section in overview.sections for field in section.fields}

    rows: list[StatusFactRow] = []
    for path in sorted(values):
        value = values[path]
        view = views.get(path)
        declared_path = section_field_key(path)
        try:
            field_def = resolved_schema.field(declared_path)
        except UserProfileError:
            label = tr("flows.status.profile.field_unavailable")
            value = tr("flows.status.profile.value_unavailable")
            masked = mask_profile_field(path=path, label=path, sensitivity=None)
        else:
            masked = mask_profile_field(
                path=path,
                label=field_def.description or path,
                sensitivity=field_def.sensitivity,
            )
            if view is None:
                label = tr("flows.status.profile.field_unavailable")
                value = tr("flows.status.profile.value_unavailable")
            else:
                label = view.label
                if view.row_index is not None:
                    label = tr("flows.status.profile.repeated_field", label=label, row=view.row_index)
                value = view.value or ""
                if value and view.choices:
                    value = next(
                        (choice.label for choice in view.choices if choice.value == value),
                        tr("flows.status.profile.value_unavailable"),
                    )
        rows.append(StatusFactRow(label=label, value=value, masked=masked))
    return tuple(rows)


__all__ = ["build_status_page_data", "present_status_tui"]
