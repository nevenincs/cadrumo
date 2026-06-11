"""CLI verbs for ``aeat config profile censo {refresh, show, compare, apply}``.

Mounts the operator-facing censo-sync surface on the existing
``config profile`` subgroup. The backend is
:class:`aeat.application.user_profile.CensoSyncService`; this module is the
thin Typer layer that resolves the active profile/bucket, calls the
application service, emits payload + text, and surfaces typed refusals.
Censo lifecycle event enrollment is owned by the application service.

This module uses :class:`BucketEventHistoryRepository` for event recording.

``refresh`` is mounted but refuses with a typed CLI boundary error
until the sede G313 driver lands - the verb is visible in ``--help``
so operators see the canonical name now and get an explicit message
about what is missing rather than a silent absence.

Use of :class:`BucketEventHistoryRepository` for compliance.
"""

from __future__ import annotations

from datetime import date

import typer

from ....core.errors import resolve_error_message
from ....core.i18n import tr
from .._common import _emit_envelope
from .._errors import CliRefusedBoundaryError
from ._profile_censo_payloads import (
    CensoApplyPayload,
    CensoCompareResult,
    CensoRefreshResult,
    CensoShowResult,
)


def _active_pointer() -> tuple[str, str]:
    from ....application.workflow import read_profile_bucket_by_id
    from ....core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.errors.no_active_profile",
        )
    pointer = read_profile_bucket_by_id(active)
    if pointer is None:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.errors.no_active_profile",
        )
    return active, pointer.bucket_id


def _build_service(bucket_id: str):
    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
    from ....application.user_profile import CensoSyncService
    from ....domain.buckets import BucketEventHistoryRepository

    return CensoSyncService(
        bucket_id=bucket_id,
        events=BucketEventHistoryRepository(objects=secure_object_repository_for_bucket(bucket_id)),
    )


def _calendar_summary_after_apply(*, bucket_id: str, profile_id: str) -> dict[str, object]:
    from ....application.overview import OverviewCalendarRange, build_overview_calendar
    from ....application.user_profile import (
        UserProfileLifecycleRepository,
        projection_for_taxpayer,
        record_to_values,
    )

    today = date.today()
    rng = OverviewCalendarRange(
        from_date=date(today.year, 1, 1),
        to_date=date(today.year, 12, 31),
    )
    record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(profile_id)
    calendar = build_overview_calendar(
        projection_for_taxpayer(record),
        rng,
        today=today,
        raw_values=record_to_values(record),
    )
    return {
        "taxpayer_model_declared": calendar.taxpayer_model_declared,
        "calendar_range_from": rng.from_date.isoformat(),
        "calendar_range_to": rng.to_date.isoformat(),
        "calendar_obligation_count": len(calendar.entries),
        "calendar_obligation_modelos": sorted({entry.modelo for entry in calendar.entries}),
        "calendar_warning_codes": [warning.code for warning in calendar.warnings],
        "calendar_defaulted_modelos": list(calendar.completeness.defaulted_modelos),
    }


def _register_censo_refresh(censo_app: typer.Typer) -> None:
    """Register the censo pull transport command."""

    @censo_app.command(
        "pull",
        help=tr(
            "cli.config.profile.censo.pull_help",
            default="Pull your latest censo from AEAT into this profile's snapshot store.",
        ),
    )
    def censo_pull(ctx: typer.Context) -> None:
        import asyncio

        from ....application.user_profile import CensoNotAvailableError

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            snapshot = asyncio.run(service.refresh_censo_from_sede(profile_id=profile_id))
        except CensoNotAvailableError as exc:
            raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc
        typed_refresh = CensoRefreshResult(
            snapshot_id=snapshot.snapshot_id,
            profile_id=snapshot.profile_id,
            captured_at=snapshot.captured_at.isoformat(),
            facts=dict(snapshot.censo_facts),
        )
        lines = [
            f"snapshot_id\t{snapshot.snapshot_id}",
            f"captured_at\t{snapshot.captured_at.isoformat()}",
            f"facts\t{len(snapshot.censo_facts)}",
        ]
        _emit_envelope(ctx, command="config.profile.censo.pull", result=typed_refresh, lines=lines)


def _register_censo_show(censo_app: typer.Typer) -> None:
    """Register the censo show transport command."""

    @censo_app.command(
        "show",
        help=tr(
            "cli.config.profile.censo.show_help",
            default="Show the last censo AEAT reported for this profile.",
        ),
    )
    def censo_show(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.censo.snapshot_id_help",
                default="Show a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.user_profile import CensoNotAvailableError

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            snapshot = service.show_censo(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensoNotAvailableError as exc:
            raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc
        typed_show = CensoShowResult(
            snapshot_id=snapshot.snapshot_id,
            profile_id=snapshot.profile_id,
            captured_at=snapshot.captured_at.isoformat(),
            source_url=snapshot.source_url,
            state=snapshot.state.value,
            facts=dict(snapshot.censo_facts),
        )
        lines = [
            f"snapshot_id\t{snapshot.snapshot_id}",
            f"captured_at\t{snapshot.captured_at.isoformat()}",
            f"state\t{snapshot.state.value}",
        ]
        for path, value in sorted(snapshot.censo_facts.items()):
            lines.append(f"{path}\t{value}")
        _emit_envelope(ctx, command="config.profile.censo.show", result=typed_show, lines=lines)


def _register_censo_compare(censo_app: typer.Typer) -> None:
    """Register the censo compare transport command."""

    @censo_app.command(
        "compare",
        help=tr(
            "cli.config.profile.censo.compare_help",
            default="Show the field-by-field difference between AEAT's censo and this profile.",
        ),
    )
    def censo_compare(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.censo.snapshot_id_help",
                default="Compare against a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.user_profile import CensoNotAvailableError

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            comparison = service.compare_censo_with_profile(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensoNotAvailableError as exc:
            raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc
        comparison_payload = comparison.model_dump(mode="json")
        comparison_payload.update(
            {
                "diverging": [row.model_dump(mode="json") for row in comparison.diverging],
                "censo_only": [row.model_dump(mode="json") for row in comparison.censo_only],
                "profile_only": [row.model_dump(mode="json") for row in comparison.profile_only],
            },
        )
        typed_compare = CensoCompareResult.model_validate(comparison_payload)
        lines = [
            f"snapshot_id\t{comparison.snapshot_id}",
            f"diverging\t{len(comparison.diverging)}",
            f"censo_only\t{len(comparison.censo_only)}",
            f"profile_only\t{len(comparison.profile_only)}",
        ]
        for row in comparison.rows:
            lines.append(
                f"{row.status.value}\t{row.path}\tcenso={row.censo_value or ''}\tprofile={row.profile_value or ''}",
            )
        _emit_envelope(ctx, command="config.profile.censo.compare", result=typed_compare, lines=lines)


def _register_censo_apply(censo_app: typer.Typer) -> None:
    """Register the censo apply transport command."""

    @censo_app.command(
        "apply",
        help=tr(
            "cli.config.profile.censo.apply_help",
            default="Overwrite this profile's censo fields with the AEAT-reported values.",
        ),
    )
    def censo_apply(
        ctx: typer.Context,
        snapshot_id: str = typer.Option(
            "",
            "--snapshot-id",
            help=tr(
                "cli.config.profile.censo.snapshot_id_help",
                default="Apply a specific snapshot id (prefix matches accepted).",
            ),
        ),
    ) -> None:
        from ....application.user_profile import (
            CensoApplyConflictError,
            CensoNotAvailableError,
        )

        profile_id, bucket_id = _active_pointer()
        service = _build_service(bucket_id)
        try:
            result = service.apply_censo_to_profile(
                profile_id=profile_id,
                snapshot_id=snapshot_id or None,
            )
        except CensoNotAvailableError as exc:
            raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc
        except CensoApplyConflictError as exc:
            raise CliRefusedBoundaryError(resolve_error_message(exc)) from exc
        apply_payload = result.model_dump(mode="json")
        apply_payload.update(_calendar_summary_after_apply(bucket_id=bucket_id, profile_id=profile_id))
        typed_apply = CensoApplyPayload.model_validate(apply_payload)
        lines = [
            f"snapshot_id\t{result.snapshot_id}",
            f"written\t{len(result.written_paths)}",
            f"unchanged\t{len(result.unchanged_paths)}",
            f"derived\t{len(result.derived_paths)}",
            f"taxpayer_model_declared\t{str(typed_apply.taxpayer_model_declared).lower()}",
            f"calendar_range\t{typed_apply.calendar_range_from}\t{typed_apply.calendar_range_to}",
            f"calendar_obligations\t{typed_apply.calendar_obligation_count}",
        ]
        if typed_apply.calendar_obligation_modelos:
            lines.append(f"calendar_modelos\t{','.join(typed_apply.calendar_obligation_modelos)}")
        if typed_apply.calendar_warning_codes:
            lines.append(f"calendar_warnings\t{','.join(typed_apply.calendar_warning_codes)}")
        for path in result.written_paths:
            lines.append(f"written\t{path}")
        for path in result.unchanged_paths:
            lines.append(f"unchanged\t{path}")
        for path in result.derived_paths:
            lines.append(f"derived\t{path}")
        _emit_envelope(ctx, command="config.profile.censo.apply", result=typed_apply, lines=lines)


def register(profile_app: typer.Typer) -> None:
    """Attach the censo subgroup to ``profile_app``."""
    censo_app = typer.Typer(
        name="censo",
        help=tr(
            "cli.config.profile.censo.help",
            default="Sync your AEAT 036 censo against this profile.",
        ),
        no_args_is_help=True,
    )
    _register_censo_refresh(censo_app)
    _register_censo_show(censo_app)
    _register_censo_compare(censo_app)
    _register_censo_apply(censo_app)
    profile_app.add_typer(censo_app, name="censo")


__all__ = ["register"]
