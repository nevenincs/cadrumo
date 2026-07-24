"""Capability-selecting presenter for the read-only status page.

This entry-point seam lets ``aeat config profile status`` render the
full-screen read-only status surface on a capable interactive console
while leaving the machine contract untouched: a ``--format json`` caller
and any non-interactive (piped / dumb-terminal / CI) host fall straight
through to the existing envelope path. The adapter tier may name Textual
but must not reach the application layer, so this entry-point module
gathers the view-model from the application authorities — the active
profile record, the profile bucket scan, the workflow auth state, and the
recovery-wrapper status — and injects the assembled
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
    from ....adapters.inbound.tui import StatusFactRow, StatusPageData
    from ....domain.user_profile import UserProfileRecord


_MASK_KEYWORDS: frozenset[str] = frozenset(
    {
        "password",
        "passphrase",
        "secret",
        "secreto",
        "contraseña",
        "clave",
        "private_key",
        "private key",
        "token",
        "api_key",
        "apikey",
    },
)


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
    """Assemble the read-only :class:`StatusPageData` from application authorities."""
    from ....adapters.inbound.tui import (
        StatusAuthView,
        StatusPageData,
        StatusProfileRow,
        StatusRecoveryView,
    )
    from ....adapters.persistence.storage import SecretStoreError
    from ....application.user_profile import inspect_recovery_status
    from ....application.workflow import (
        list_profile_buckets,
        read_profile_bucket_by_id,
        workflow_state_repository,
    )
    from ....core import resolve_active_bucket_id
    from ....domain.user_profile import UserProfileError

    active_uuid = resolve_active_bucket_id()
    active_pointer = read_profile_bucket_by_id(active_uuid) if active_uuid else None
    active_label = active_pointer.label if active_pointer is not None else active_uuid

    state = workflow_state_repository().load()
    # A locked or corrupt active bucket must not blank the whole surface: the
    # facts zone degrades to empty while the buckets, auth, and recovery zones
    # still render from their own authorities.
    try:
        record = state.active_profile_record()
    except (SecretStoreError, UserProfileError):
        record = None
    facts = _build_fact_rows(record)

    profiles = tuple(
        StatusProfileRow(
            label=pointer.label,
            status=str(pointer.status.value),
            active=pointer.bucket_id == active_uuid,
        )
        for pointer in sorted(
            list_profile_buckets(include_tombstoned=True).values(),
            key=lambda pointer: pointer.label.casefold(),
        )
    )

    auth = state.auth
    auth_view = StatusAuthView(
        provider=auth.provider,
        login_ready=auth.authenticated_at is not None,
        subject=auth.subject,
        certificate_source=auth.active_certificate_source,
    )

    recovery = inspect_recovery_status()
    recovery_view = StatusRecoveryView(
        enrolled=recovery.recovery_enrolled,
        fingerprint=recovery.recovery_fingerprint,
    )

    return StatusPageData(
        active_profile_label=active_label,
        facts=facts,
        profiles=profiles,
        auth=auth_view,
        recovery=recovery_view,
    )


def _build_fact_rows(record: UserProfileRecord | None) -> tuple[StatusFactRow, ...]:
    """Project the active profile record into masked/labelled fact rows.

    Labels resolve through the profile schema's per-field description; a
    path with no schema field falls back to the raw dotted path. A fact is
    masked when its schema field is ``SECRET``-classed or its path/label is
    password/key-like, so no secret-shaped value reaches the screen.
    """
    from ....adapters.inbound.tui import StatusFactRow
    from ....application.user_profile import record_to_path_values
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
            masked = _is_masked(path=path, label=path, sensitivity=None)
        else:
            label = field_def.description or path
            masked = _is_masked(path=path, label=label, sensitivity=field_def.sensitivity)
        rows.append(StatusFactRow(label=label, value=value, masked=masked))
    return tuple(rows)


def _is_masked(*, path: str, label: str, sensitivity: object | None) -> bool:
    """Decide whether a fact value must be masked on screen."""
    from ....core.classification import SensitivityClass

    if sensitivity is SensitivityClass.SECRET:
        return True
    haystack = f"{path} {label}".casefold()
    return any(keyword in haystack for keyword in _MASK_KEYWORDS)


__all__ = ["build_status_page_data", "present_status_tui"]
