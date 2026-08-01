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
    from ....adapters.inbound.tui import (
        StatusAuthView,
        StatusFactRow,
        StatusPageData,
        StatusProfileRow,
        StatusRecoveryView,
    )
    from ....application.workflow import WorkflowState
    from ....domain.user_profile import UserProfileRecord


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
    return StatusPageData(
        active_profile_label=active_label,
        facts=_build_fact_rows(_read_active_record(state)),
        profiles=_build_profile_rows(active_uuid),
        auth=_build_auth_view(state),
        recovery=_build_recovery_view(),
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


def _build_auth_view(state: WorkflowState | None) -> StatusAuthView:
    """Project the workflow auth state, degrading to an empty view when absent."""
    from ....adapters.inbound.tui import StatusAuthView

    if state is None:
        return StatusAuthView()
    auth = state.auth
    return StatusAuthView(
        provider=auth.provider,
        login_ready=auth.authenticated_at is not None,
        subject=auth.subject,
        certificate_source=auth.active_certificate_source,
    )


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


def _build_fact_rows(record: UserProfileRecord | None) -> tuple[StatusFactRow, ...]:
    """Project the active profile record into masked/labelled fact rows.

    Labels resolve through the profile schema's per-field description; a
    path with no schema field falls back to the raw dotted path.

    The masking decision is delegated to ``mask_profile_field``, the one
    authority the profile overview also uses. This surface previously
    carried its own keyword policy, which omitted ``credential`` and so
    printed the Cl@ve credential inputs (``auth.dni_nie``,
    ``auth.numero_soporte``, ``auth.fecha_validez``) in clear while the
    overview masked them.
    """
    from ....adapters.inbound.tui import StatusFactRow
    from ....application.user_profile import mask_profile_field, record_to_path_values
    from ....domain.user_profile import (
        UserProfileError,
        load_user_profile_schema,
    )

    if record is None:
        return ()
    values = record_to_path_values(record)
    if not values:
        return ()
    schema = load_user_profile_schema()

    rows: list[StatusFactRow] = []
    for path in sorted(values):
        value = values[path]
        try:
            field_def = schema.field(path)
        except UserProfileError:
            label = path
            masked = mask_profile_field(path=path, label=path, sensitivity=None)
        else:
            label = field_def.description or path
            masked = mask_profile_field(
                path=path,
                label=label,
                sensitivity=field_def.sensitivity,
            )
        rows.append(StatusFactRow(label=label, value=value, masked=masked))
    return tuple(rows)


__all__ = ["build_status_page_data", "present_status_tui"]
