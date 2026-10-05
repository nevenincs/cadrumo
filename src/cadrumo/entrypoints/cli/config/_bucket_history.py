"""Profile event-history behavior handler for ``aeat config profile history``."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import typer

from ....core.errors.hierarchy import InternalInvariantError
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.time.utc import coerce_utc_aware
from ....domain.buckets.event import BucketEvent, BucketEventType
from ..common import activate_subcommand_output_language as _activate_subcommand_output_language
from ..common import emit_envelope
from ..runtime_profile_binding import bound_profile_client, require_profile_client
from ..runtime_profile_history import read_profile_history_for_cli

if TYPE_CHECKING:
    from .._config_bucket_history_payloads import BucketHistoryEventPayload


def _resolve_bucket_history_filters(
    *,
    event_type: list[str] | None,
    since: str | None,
    until: str | None,
    object_id: str | None,
    actor: str | None,
) -> tuple[
    tuple[BucketEventType, ...] | None,
    datetime | None,
    datetime | None,
    str | None,
    str | None,
]:
    """Parse and validate the filters owned by the history read surface."""
    selected = _parse_bucket_event_types(event_type)
    since_dt = _parse_bucket_history_instant(since, flag="--since")
    until_dt = _parse_bucket_history_instant(until, flag="--until")
    if since_dt is not None and until_dt is not None and since_dt > until_dt:
        raise typer.BadParameter(tr("cli.config.profile.history.since_after_until"))
    return selected, since_dt, until_dt, object_id.strip() if object_id else None, actor.strip() if actor else None


def _bucket_history_lines(*, profile_label: str, events: tuple[BucketEvent, ...]) -> list[str]:
    """Render history rows in the catalogue's existing deterministic order."""
    return [
        "operation\tconfig.profile.history",
        f"profile\t{profile_label}",
        f"event_count\t{len(events)}",
        *(
            f"{event.occurred_at.isoformat()}\t{event.event_type.value}\t{event.object_type.value}"
            f"\t{event.object_id}\t{event.actor}"
            for event in events
        ),
    ]


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
    """Browse the authenticated profile's append-only event history."""
    _activate_subcommand_output_language(ctx, output_language)

    profile_label, profile_id = _resolve_profile_history_target(profile, ctx=ctx)
    selected, since_dt, until_dt, object_id_token, actor_token = _resolve_bucket_history_filters(
        event_type=event_type,
        since=since,
        until=until,
        object_id=object_id,
        actor=actor,
    )
    from ....application.user_profile.history_contracts import ProfileHistoryRequest

    projection = read_profile_history_for_cli(
        ctx,
        request=ProfileHistoryRequest(
            profile_id=profile_id,
            event_types=selected,
            since=since_dt,
            until=until_dt,
            object_id=object_id_token,
            actor=actor_token,
        ),
    )
    from .._config_bucket_history_payloads import BucketHistoryResult

    events = tuple(event.to_event() for event in projection.events)
    bucket_result = BucketHistoryResult(
        operation="config.bucket.history",
        bucket_id=str(projection.profile_id),
        event_types=list(projection.event_types) if projection.event_types is not None else None,
        since=projection.since,
        until=projection.until,
        object_id=projection.object_id,
        actor=projection.actor,
        events=[_bucket_history_event_payload(event) for event in events],
    )
    lines = _bucket_history_lines(profile_label=profile_label, events=events)
    emit_envelope(ctx, command="config.bucket.history", result=bucket_result, lines=lines)


def _resolve_profile_history_target(profile: str | None, *, ctx: typer.Context) -> tuple[str, UUID]:
    """Bind history to the parsed profile target or the authenticated client."""
    from ....application.workflow.profile_bucket_scan import read_profile_bucket_by_id
    from .._profile_authentication_gate import resolved_command_profile_target

    client = bound_profile_client(ctx)
    pointer = resolved_command_profile_target(ctx)
    if pointer is None:
        if profile is not None:
            raise InternalInvariantError("explicit profile history target was not resolved by parsed dispatch")
        pointer = read_profile_bucket_by_id(str(client.profile_id))
        if pointer is None or pointer.bucket_id != str(client.profile_id):
            raise InternalInvariantError("authenticated profile history target has no matching profile projection")
    client = require_profile_client(ctx, expected_profile_id=UUID(str(pointer.bucket_id)))
    return pointer.label, client.profile_id


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


__all__ = ["_parse_bucket_event_types", "_parse_bucket_history_instant", "profile_history"]
