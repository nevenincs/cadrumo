"""Profile event-history command registration for ``aeat config profile history``.

Use of :class:`BucketEventHistoryRepository` for compliance.
"""

from __future__ import annotations

import typing
from collections.abc import Mapping
from datetime import datetime

import typer

from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....domain.buckets import BucketEvent, BucketEventType
from .._common import _emit_envelope
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language


def register_bucket_history_commands(profile_app: typer.Typer) -> None:
    """Register the ``config profile history`` event-history command on ``profile_app``."""

    @profile_app.command("history", help=tr("cli.config.profile.history_help"))
    def profile_history(
        ctx: typer.Context,
        profile: typing.Annotated[
            str,
            typer.Argument(help=tr("cli.config.profile.history_bucket_id_help")),
        ],
        event_type: typing.Annotated[
            list[str] | None,
            typer.Option(
                "--event-type",
                help=tr("cli.config.profile.history_event_type_help"),
            ),
        ] = None,
        since: typing.Annotated[
            str | None,
            typer.Option(
                "--since",
                help=tr("cli.config.profile.history_since_help"),
            ),
        ] = None,
        until: typing.Annotated[
            str | None,
            typer.Option(
                "--until",
                help=tr("cli.config.profile.history_until_help"),
            ),
        ] = None,
        object_id: typing.Annotated[
            str | None,
            typer.Option(
                "--object-id",
                help=tr("cli.config.profile.history_object_id_help"),
            ),
        ] = None,
        actor: typing.Annotated[
            str | None,
            typer.Option(
                "--actor",
                help=tr("cli.config.profile.history_actor_help"),
            ),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Browse the active profile's append-only event history."""
        _activate_subcommand_output_language(ctx, output_language)
        from ....domain.buckets import BucketEventHistoryRepository
        from .._config_payloads import BucketHistoryResult

        profile_label, bucket_id = _resolve_profile_history_target(profile)
        selected = _parse_bucket_event_types(event_type)
        since_dt = _parse_bucket_history_instant(since, flag="--since")
        until_dt = _parse_bucket_history_instant(until, flag="--until")
        if since_dt is not None and until_dt is not None and since_dt > until_dt:
            raise typer.BadParameter(tr("cli.config.profile.history.since_after_until"))
        object_id_token = object_id.strip() if object_id else None
        actor_token = actor.strip() if actor else None

        catalogue = BucketEventHistoryRepository().load()
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
            event_types=[t.value for t in selected] if selected else None,
            since=since_dt.isoformat() if since_dt else None,
            until=until_dt.isoformat() if until_dt else None,
            object_id=object_id_token,
            actor=actor_token,
            events=[dict(_bucket_history_event_payload(event)) for event in events],
        )
        lines = ["operation\tconfig.profile.history", f"profile\t{profile_label}", f"event_count\t{len(events)}"] + [
            f"{e.occurred_at.isoformat()}\t{e.event_type.value}\t{e.object_type.value}\t{e.object_id}\t{e.actor}"
            for e in events
        ]
        _emit_envelope(ctx, command="config.bucket.history", result=bucket_result, lines=lines)


def _resolve_profile_history_target(profile: str) -> tuple[str, str]:
    """Resolve an operator profile token to ``(label, bucket_id)`` for history reads."""
    from ....application.workflow import ProfileLabelAmbiguousError, read_profile_bucket, read_profile_bucket_by_id

    token = profile.strip()
    try:
        pointer = read_profile_bucket(token)
    except ProfileLabelAmbiguousError as exc:
        raise typer.BadParameter(tr("errors.refused.refused_profile_label_ambiguous")) from exc
    except ValueError as exc:
        raise typer.BadParameter(tr("cli.config.profile.unknown_profile", name=token)) from exc
    if pointer is None:
        pointer = read_profile_bucket_by_id(token)
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
        return datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise typer.BadParameter(
            tr("cli.config.profile.history.invalid_timestamp", flag=flag, raw=raw),
        ) from exc


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


def _bucket_history_event_payload(event: BucketEvent) -> Mapping[str, object]:
    """Project one bucket event onto its JSON payload row."""
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": event.actor,
        "object_type": event.object_type.value,
        "object_id": event.object_id,
        "payload": dict(event.payload),
    }


__all__ = ["_parse_bucket_event_types", "register_bucket_history_commands"]
