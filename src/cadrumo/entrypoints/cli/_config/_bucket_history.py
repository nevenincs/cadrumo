"""Profile event-history behavior handler for ``aeat config profile history``.

The history command reads :class:`BucketEventHistoryRepository` and filters the
active profile bucket's append-only events.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.time import coerce_utc_aware
from ....domain.buckets import BucketEvent, BucketEventType
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope

if TYPE_CHECKING:
    from .._config_bucket_history_payloads import BucketHistoryEventPayload


def profile_history(
    ctx: typer.Context,
    profile: str | None = None,
    event_type: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    object_id: str | None = None,
    actor: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Browse the active profile's append-only event history."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
    from ....adapters.persistence.storage import secure_object_repository_for_bucket
    from .._config_bucket_history_payloads import BucketHistoryResult

    profile_label, bucket_id = _resolve_profile_history_target(profile, ctx=ctx)
    selected = _parse_bucket_event_types(event_type)
    since_dt = _parse_bucket_history_instant(since, flag="--since")
    until_dt = _parse_bucket_history_instant(until, flag="--until")
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise typer.BadParameter(tr("cli.config.profile.history.since_after_until"))
    object_id_token = object_id.strip() if object_id else None
    actor_token = actor.strip() if actor else None

    catalogue = BucketEventHistoryRepository(
        objects=secure_object_repository_for_bucket(bucket_id),
    ).load()
    events = tuple(
        event
        for event in catalogue.for_bucket(bucket_id, event_types=selected)
        if _bucket_history_event_matches(
            event,
            since_dt=since_dt,
            until_dt=until_dt,
            object_id_token=object_id_token,
            actor_token=actor_token,
        )
    )

    bucket_result = BucketHistoryResult(
        operation="config.bucket.history",
        bucket_id=bucket_id,
        event_types=list(selected) if selected else None,
        since=since_dt,
        until=until_dt,
        object_id=object_id_token,
        actor=actor_token,
        events=[_bucket_history_event_payload(event) for event in events],
    )
    lines = ["operation\tconfig.profile.history", f"profile\t{profile_label}", f"event_count\t{len(events)}"] + [
        f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_type.value}\t{e.object_id}\t{e.actor}"
        for e in events
    ]
    emit_envelope(ctx, command="config.bucket.history", result=bucket_result, lines=lines)


def _resolve_profile_history_target(profile: str | None, *, ctx: typer.Context | None = None) -> tuple[str, str]:
    """Resolve an explicit profile token or the active profile for history reads."""
    from ....application.workflow import ProfileLabelAmbiguousError, resolve_profile_bucket
    from ....core import resolve_active_bucket_id
    from .._common import _no_active_profile_refusal

    if profile is not None:
        if ctx is None:
            raise RuntimeError("explicit profile history target requires parsed dispatch context")
        from .._profile_authentication_gate import resolved_command_profile_target

        pointer = resolved_command_profile_target(ctx)
        if pointer is None:
            raise RuntimeError("explicit profile history target was not resolved by parsed dispatch")
        return pointer.label, pointer.bucket_id
    selected = resolve_active_bucket_id()
    if selected is None:
        raise _no_active_profile_refusal()
    token = selected.strip()
    try:
        pointer = resolve_profile_bucket(token)
    except ProfileLabelAmbiguousError as exc:
        raise typer.BadParameter(tr("errors.refused.refused_profile_label_ambiguous")) from exc
    except ValueError as exc:
        raise typer.BadParameter(tr("cli.config.profile.unknown_profile", name=token)) from exc
    if pointer is None:
        raise typer.BadParameter(tr("cli.config.profile.unknown_profile", name=token))
    return pointer.label, pointer.bucket_id


def _parse_bucket_event_types(event_type: list[str] | None) -> tuple[BucketEventType, ...] | None:
    """Parse the ``--event-type`` flag tuple, raising :class:`typer.BadParameter` on unknown values."""
    if not event_type:
        return None

    parsed: list[BucketEventType] = []
    for value in event_type:
        token = value.strip()
        try:
            parsed.append(BucketEventType(token))
        except ValueError as exc:
            raise typer.BadParameter(
                tr(
                    "cli.config.profile.history.invalid_event_type",
                    value=token,
                    valid=", ".join(member.value for member in BucketEventType),
                ),
            ) from exc
    return tuple(parsed)


def _parse_bucket_history_instant(raw: str | None, *, flag: str) -> datetime | None:
    """Parse one ``--since`` / ``--until`` value into a :class:`datetime`, or ``None`` when absent."""
    if not raw:
        return None

    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr("cli.config.profile.history.invalid_timestamp", flag=flag, raw=raw),
        ) from exc
    # Bucket events stamp ``occurred_at`` as timezone-aware UTC; a bare ``--since
    # 2026-01-01`` parses naive and would raise ``TypeError`` on comparison. Coerce a
    # naive operator instant to UTC (central helper) so the filter compares cleanly.
    return coerce_utc_aware(parsed)


def _bucket_history_event_matches(
    event: BucketEvent,
    *,
    since_dt: datetime | None,
    until_dt: datetime | None,
    object_id_token: str | None,
    actor_token: str | None,
) -> bool:
    """Return True when ``event`` passes every active history filter."""
    if since_dt is not None and event.occurred_at < since_dt:
        return False
    if until_dt is not None and event.occurred_at > until_dt:
        return False
    if object_id_token is not None and event.object_id != object_id_token:
        return False
    return not (actor_token is not None and event.actor != actor_token)


def _bucket_history_event_payload(event: BucketEvent) -> BucketHistoryEventPayload:
    """Project one bucket event onto its typed JSON payload row."""
    from .._config_bucket_history_payloads import BucketHistoryEventPayload

    return BucketHistoryEventPayload(
        event_id=event.event_id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        actor=event.actor,
        object_type=event.object_type,
        object_id=event.object_id,
        payload_version=event.payload_version,
        payload=dict(event.payload),
    )


__all__ = ["_parse_bucket_event_types", "profile_history"]
