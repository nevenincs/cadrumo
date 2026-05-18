"""CLI verbs for ``aeat config profile census {refresh, show, compare, apply}``.

Mounts the operator-facing census-sync surface on the existing
``config profile`` subgroup. The backend is
:class:`aeat.application.profile.CensusSyncService`; this module is the
thin Typer layer that resolves the active profile/bucket, calls the
service, emits payload + text, and surfaces typed refusals.

``refresh`` is mounted but refuses with a typed CLI boundary error
until the sede G313 driver (P03.S27) lands — the verb is visible in
``--help`` so operators see the canonical name now and get an explicit
message about what is missing rather than a silent absence.
"""

from __future__ import annotations

import typer

from ....domain.profile._constants import BucketId, ProfileName
from .._common import _emit
from .._errors import CliRefusedBoundaryError
from ....core.i18n import tr


def _active_pointer() -> tuple[ProfileName, BucketId]:
    from ....application.workflow import workflow_state_repository
    from ....application.workflow._models import resolve_active_bucket_id

    state = workflow_state_repository().load()
    active = resolve_active_bucket_id(state)
    if active is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    pointer = state.profiles.get(active)
    if pointer is None:
        raise CliRefusedBoundaryError(tr("cli.config.errors.no_active_profile"))
    return active, pointer.bucket_id


def _build_service(bucket_id: str):
    from ....application.profile import CensusSyncService

    return CensusSyncService(bucket_id=bucket_id)


def _emit_census_event(*, bucket_id: str, event_type, profile_id: str, snapshot_id: str) -> None:
    from datetime import UTC, datetime

    from ....domain.buckets import (
        BucketEvent,
        BucketEventHistoryRepository,
        BucketEventObjectType,
        append_bucket_event,
        derive_bucket_event_id,
    )

    occurred_at = datetime.now(UTC)
    payload = {"profile_id": profile_id, "snapshot_id": snapshot_id}
    event_id = derive_bucket_event_id(
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor="operator",
        object_type=BucketEventObjectType.PROFILE,
        object_id=profile_id,
        payload=payload,
    )
    repo = BucketEventHistoryRepository()
    catalogue = repo.load()
    repo.save(
        append_bucket_event(
            catalogue,
            BucketEvent(
                event_id=event_id,
                bucket_id=bucket_id,
                event_type=event_type,
                occurred_at=occurred_at,
                actor="operator",
                object_type=BucketEventObjectType.PROFILE,
                object_id=profile_id,
                payload=payload,
                payload_version=1,
            ),
        ),
    )


def register(profile_app: typer.Typer) -> None:
    """Attach the census subgroup to ``profile_app``."""

    census_app = typer.Typer(
        name="census",
        help=tr(
            "cli.config.profile.census.help",
            default="Sync your AEAT 036 census against this profile.",
        ),
        no_args_is_help=True,
    )

    @census_app.command(
        "refresh",
        help=tr(
            "cli.config.profile.census.refresh_help",
            default="Pull your latest census from AEAT into this profile's snapshot store.",
        ),
    )
    def census_refresh(ctx: typer.Context) -> None:
        import asyncio

        from ....application.profile import CensusNotAvailableError
        from ....domain.buckets import BucketEventType

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            snapshot = asyncio.run(service.refresh_census_from_sede(profile_id=profile_id))
        except CensusNotAvailableError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        _emit_census_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.CENSUS_REFRESHED,
            profile_id=profile_id,
            snapshot_id=snapshot.snapshot_id,
        )
        payload = {
            "snapshot_id": snapshot.snapshot_id,
            "profile_id": snapshot.profile_id,
            "captured_at": snapshot.captured_at.isoformat(),
            "facts": dict(snapshot.census_facts),
        }
        lines = [
            f"snapshot_id\t{snapshot.snapshot_id}",
            f"captured_at\t{snapshot.captured_at.isoformat()}",
            f"facts\t{len(snapshot.census_facts)}",
        ]
        _emit(ctx, payload, lines)

    @census_app.command(
        "show",
        help=tr(
            "cli.config.profile.census.show_help",
            default="Show the last census AEAT reported for this profile.",
        ),
    )
    def census_show(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.census.snapshot_id_help",
                default="Show a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.profile import CensusNotAvailableError

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            snapshot = service.show_census(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensusNotAvailableError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        payload = {
            "snapshot_id": snapshot.snapshot_id,
            "profile_id": snapshot.profile_id,
            "captured_at": snapshot.captured_at.isoformat(),
            "source_url": snapshot.source_url,
            "state": snapshot.state.value,
            "facts": dict(snapshot.census_facts),
        }
        lines = [
            f"snapshot_id\t{snapshot.snapshot_id}",
            f"captured_at\t{snapshot.captured_at.isoformat()}",
            f"state\t{snapshot.state.value}",
        ]
        for path, value in sorted(snapshot.census_facts.items()):
            lines.append(f"{path}\t{value}")
        _emit(ctx, payload, lines)

    @census_app.command(
        "compare",
        help=tr(
            "cli.config.profile.census.compare_help",
            default="Show the field-by-field difference between AEAT's census and this profile.",
        ),
    )
    def census_compare(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.census.snapshot_id_help",
                default="Compare against a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.profile import CensusNotAvailableError

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            comparison = service.compare_census_with_profile(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensusNotAvailableError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        payload = comparison.model_dump(mode="json")
        lines = [
            f"snapshot_id\t{comparison.snapshot_id}",
            f"diverging\t{len(comparison.diverging)}",
            f"census_only\t{len(comparison.census_only)}",
            f"profile_only\t{len(comparison.profile_only)}",
        ]
        for row in comparison.rows:
            lines.append(
                f"{row.status.value}\t{row.path}\t"
                f"census={row.census_value or ''}\tprofile={row.profile_value or ''}"
            )
        _emit(ctx, payload, lines)

    @census_app.command(
        "apply",
        help=tr(
            "cli.config.profile.census.apply_help",
            default="Overwrite this profile's census fields with the AEAT-reported values.",
        ),
    )
    def census_apply(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.census.snapshot_id_help",
                default="Apply a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.profile import (
            CensusApplyConflictError,
            CensusNotAvailableError,
        )
        from ....domain.buckets import BucketEventType

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            result = service.apply_census_to_profile(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensusNotAvailableError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        except CensusApplyConflictError as exc:
            raise CliRefusedBoundaryError(str(exc)) from exc
        _emit_census_event(
            bucket_id=bucket_id,
            event_type=BucketEventType.CENSUS_APPLIED,
            profile_id=profile_id,
            snapshot_id=result.snapshot_id,
        )
        payload = result.model_dump(mode="json")
        lines = [
            f"snapshot_id\t{result.snapshot_id}",
            f"written\t{len(result.written_paths)}",
            f"unchanged\t{len(result.unchanged_paths)}",
        ]
        for path in result.written_paths:
            lines.append(f"written\t{path}")
        for path in result.unchanged_paths:
            lines.append(f"unchanged\t{path}")
        _emit(ctx, payload, lines)

    profile_app.add_typer(census_app, name="census")


__all__ = ["register"]
