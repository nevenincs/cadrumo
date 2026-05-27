"""Explicit read-only AEAT live observation CLI commands."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import typer

from ...application.live import (
    FiledDataListingRow,
    IvaCompensationHistoryReport,
    IvaWalletCaptureReport,
    capture_filed_data,
    capture_source_filed_data,
    list_filed_data,
)
from ...core.errors import resolve_error_message
from ...core.i18n import tr
from ._common import _emit

if TYPE_CHECKING:
    from ...application.auth import LiveAuthPreflightReport

_VerifyVerdict = Literal["valid", "invalid", "unknown"]


def _verify_expected(value: str | None) -> _VerifyVerdict | None:
    if value is None:
        return None
    if value == "valid":
        return "valid"
    if value == "invalid":
        return "invalid"
    if value == "unknown":
        return "unknown"
    raise typer.BadParameter(tr("cli.app.live.verify.expected_values_error"))


app = typer.Typer(
    name="live",
    help=tr("cli.app.live.app_help"),
    no_args_is_help=True,
    add_completion=False,
)
filed_app = typer.Typer(
    name="filed",
    help=tr("cli.app.live.filed_app_help"),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(filed_app, name="filed")

iva_wallet_app = typer.Typer(
    name="iva-wallet",
    help=tr(
        "cli.app.live.iva_wallet.app_help",
        default=(
            "AEAT IVA compensation wallet capture (read-only; allows only own-name representation and "
            "the guarded wallet read query)."
        ),
    ),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(iva_wallet_app, name="iva-wallet")


def _metric_line(key: str, value: object) -> str:
    return f"{key}={value}"


def _emit_live_auth_preflight(provider: str | None = None) -> None:
    from ...application.auth import build_live_auth_preflight_report

    report = build_live_auth_preflight_report(provider)
    for line in _live_auth_preflight_lines(report):
        typer.echo(line, err=True)


def _live_auth_preflight_lines(report: LiveAuthPreflightReport) -> tuple[str, ...]:
    return (
        _metric_line("auth_preflight", "redacted"),
        _metric_line("auth_provider", report.provider),
        _metric_line("auth_configured", report.configured),
        _metric_line("auth_available", report.available),
        _metric_line("auth_active_profile", report.active_profile),
        _metric_line("auth_active_profile_status", report.active_profile_status),
        _metric_line("auth_active_profile_registered", report.active_profile_registered),
        _metric_line("auth_active_profile_record_present", report.active_profile_record_present),
        _metric_line("auth_profile_tax_id", "present" if report.profile_tax_id_present else "missing"),
        _metric_line("auth_provider_identity", "present" if report.provider_identity_present else "missing"),
        _metric_line("auth_identity_alignment", report.identity_alignment),
        _metric_line("auth_identity_kind", report.identity_kind),
        _metric_line("auth_mode", report.auth_mode),
        _metric_line("auth_prefer_non_qr", report.prefer_non_qr),
        _metric_line("auth_timeout_ms", report.timeout_ms),
        _metric_line("auth_dni_fecha", "present" if report.dni_fecha_configured else "missing"),
        _metric_line("auth_nie_soporte", "present" if report.nie_soporte_configured else "missing"),
        _metric_line("auth_certificate_path", "present" if report.certificate_path_configured else "missing"),
        _metric_line("auth_certificate_file", "present" if report.certificate_file_present else "missing"),
        _metric_line("auth_certificate_backend", report.certificate_backend),
        _metric_line("auth_persisted_session", "present" if report.persisted_session_present else "missing"),
        _metric_line("auth_persisted_session_expired", report.persisted_session_expired),
        _metric_line("auth_probe_result", report.probe_result),
    )


_IVA_WALLET_LIVE_SAFETY_LINES = (
    _metric_line("safety_policy", "read_only_fail_closed"),
    _metric_line("representation_gate_policy", "own_name_only_no_represented_taxpayer_choice"),
    _metric_line(
        "aeat_form_submission_policy",
        "wallet_execute_read_query_only_no_filing_or_represented_taxpayer_data",
    ),
)


@iva_wallet_app.command(
    "pull",
    help=tr(
        "cli.app.live.iva_wallet.pull_help",
        default=(
            "Live-fetch and persist AEAT's IVA compensation wallet. The only AEAT form action allowed is "
            "the guarded wallet read query; representation gates only continue in own-name mode."
        ),
    ),
)
def iva_wallet_pull_cmd(
    ctx: typer.Context,
    year: Annotated[
        int,
        typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help")),
    ],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help"))],
    taxpayer_nif: Annotated[
        str | None,
        typer.Option(
            "--taxpayer-nif",
            help=tr(
                "cli.app.live.iva_wallet.taxpayer_nif_help",
                default="Taxpayer NIF; defaults to authenticated identity.",
            ),
        ),
    ] = None,
) -> None:
    """Pull the authenticated AEAT IVA compensation wallet.

    This is a live read. It refuses unless `AEAT_LIVE_TESTS_ENABLED=1`
    is set and can trigger the configured authentication provider,
    including Cl@ve Móvil manual approval.
    """

    from ...application.live import capture_iva_compensation_wallet

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_iva_compensation_wallet(
            target_year=year,
            target_period=period,
            taxpayer_nif=taxpayer_nif,
        )
    )
    _emit(ctx, report, _iva_wallet_pull_lines(report))


def _iva_wallet_pull_lines(report: IvaWalletCaptureReport) -> tuple[str, ...]:
    return (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        *(
            _metric_line("taxpayer_ref", report.taxpayer_ref),
            _metric_line("target_year", report.target_year),
            _metric_line("target_period", report.target_period),
            _metric_line("row_count", report.row_count),
            _metric_line("total_pending", report.total_pending),
            _metric_line("selected_authority", report.selected_authority),
            _metric_line("selected_amount", report.selected_amount),
            _metric_line("local_recurrence_amount", report.local_recurrence_amount),
            _metric_line("divergence", report.divergence),
            _metric_line("blocked", report.blocked),
            _metric_line("captured_at", report.captured_at.isoformat()),
            _metric_line("observation_path", report.observation_path),
        ),
    )


@iva_wallet_app.command(
    "history",
    help=tr(
        "cli.app.live.iva_wallet.history_help",
        default=(
            "List secure local IVA compensation history, carry-forward lots, and persisted wallet "
            "authority decisions derived from Modelo 303 captures."
        ),
    ),
)
def iva_wallet_history_cmd(
    ctx: typer.Context,
    as_of_year: Annotated[
        int | None,
        typer.Option("--as-of-year", min=2000, max=2099, help=tr("cli.app.live.iva_wallet.as_of_year_help")),
    ] = None,
) -> None:
    """List the profile-local IVA compensation history without contacting AEAT."""

    from ...application.live import list_iva_compensation_history

    report = list_iva_compensation_history(as_of_year=as_of_year)
    _emit(ctx, report, _iva_wallet_history_lines(report))


def _iva_wallet_history_lines(report: IvaCompensationHistoryReport) -> tuple[str, ...]:
    lines = [
        _metric_line("row_count", report.row_count),
        _metric_line("as_of_year", report.as_of_year),
        _metric_line("carry_forward_lot_count", report.carry_forward_lot_count),
        _metric_line("unallocated_applied_amount", report.unallocated_applied_amount),
        _metric_line("authority_decision_count", report.authority_decision_count),
    ]
    for row in report.rows:
        lines.append(
            _metric_line(
                "row",
                "\t".join(
                    (
                        str(row.year),
                        row.period,
                        row.status,
                        f"prior={row.prior_pending_amount}",
                        f"applied={row.applied_amount}",
                        f"pending_later={row.pending_for_later_amount}",
                        f"period_result={row.period_result_amount}",
                        f"final_result={row.final_result_amount}",
                        f"generated={row.generated_amount}",
                        f"available_end={row.available_end_amount}",
                    )
                ),
            )
        )
    for lot in report.carry_forward_lots:
        lines.append(
            _metric_line(
                "carry_forward_lot",
                "\t".join(
                    (
                        str(lot.source_filing_year),
                        lot.source_period,
                        f"generated={lot.generated_amount}",
                        f"applied={lot.applied_amount}",
                        f"remaining={lot.remaining_amount}",
                        f"age_years={lot.age_years}",
                        f"expiry_review_state={lot.expiry_review_state}",
                        f"source={lot.source_observation_key}",
                        f"taxpayer_ref={lot.taxpayer_ref}",
                    )
                ),
            )
        )
    for decision in report.authority_decisions:
        lines.append(
            _metric_line(
                "authority_decision",
                "\t".join(
                    (
                        str(decision.target_year),
                        decision.target_period,
                        f"selected_authority={decision.selected_authority}",
                        f"selected_amount={decision.selected_amount}",
                        f"wallet_amount={decision.wallet_amount}",
                        f"local_recurrence_amount={decision.local_recurrence_amount}",
                        f"override_amount={decision.override_amount}",
                        f"divergence={decision.divergence}",
                        f"blocked={decision.blocked}",
                        f"stale_wallet={decision.stale_wallet}",
                        f"taxpayer_ref={decision.taxpayer_ref}",
                    )
                ),
            )
        )
        for source in decision.authority_sources:
            lines.append(
                _metric_line("authority_source", f"{decision.target_year}\t{decision.target_period}\t{source}")
            )
    return tuple(lines)


@iva_wallet_app.command(
    "capture-history",
    help=tr(
        "cli.app.live.iva_wallet.capture_history_help",
        default=(
            "Live-capture filed Modelo 303 history and persist secure IVA compensation state. "
            "No AEAT filing or wallet form choices are submitted."
        ),
    ),
)
def iva_wallet_capture_history_cmd(
    ctx: typer.Context,
    year_from: Annotated[
        int,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ],
    year_to: Annotated[
        int,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/live/iva-compensation-history"),
) -> None:
    """Pull multi-year Modelo 303 filing history and verify secure reload."""

    from ...application.live import capture_iva_compensation_history

    _emit_live_auth_preflight()
    report = asyncio.run(
        capture_iva_compensation_history(
            year_from=year_from,
            year_to=year_to,
            output_root=output_root,
        )
    )
    lines = (
        *_IVA_WALLET_LIVE_SAFETY_LINES,
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("captured_count", report.captured_count),
        _metric_line("calculation_observation_count", report.calculation_observation_count),
        _metric_line("reloaded_history_count", report.reloaded_history_count),
        _metric_line("output_root", report.output_root),
    )
    _emit(ctx, report, lines)


@filed_app.command("list", help=tr("cli.app.live.filed.list_help"))
def filed_list_cmd(
    ctx: typer.Context,
    modelo: Annotated[str | None, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))] = None,
    year_from: Annotated[
        int | None,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ] = None,
    year_to: Annotated[
        int | None,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ] = None,
) -> None:
    """List filed-declaration rows without downloading justificantes or submitted files.

    All filters are optional refinements. When ``--modelo`` is omitted the
    listing iterates every modelo configured in the registry. When
    ``--from-year`` / ``--to-year`` are omitted they default to the current
    calendar year.
    """

    from datetime import date as _date

    from ...core.resources import resources

    resolved_from = year_from if year_from is not None else _date.today().year
    resolved_to = year_to if year_to is not None else _date.today().year
    modelos = tuple(str(m.id) for m in resources().modelos.all()) if modelo is None else (modelo,)
    all_rows: list[FiledDataListingRow] = []
    total_count = 0
    for code in modelos:
        report = asyncio.run(
            list_filed_data(
                modelo=code,
                year_from=resolved_from,
                year_to=resolved_to,
            )
        )
        total_count += report.row_count
        all_rows.extend(report.rows)
    lines = [_metric_line("row_count", total_count)]
    for row in all_rows:
        lines.append(
            _metric_line(
                "row",
                "\t".join(
                    (
                        row.modelo,
                        str(row.year),
                        row.period,
                        row.expediente_id,
                        row.status,
                        row.presented_at.isoformat(),
                        f"submitted_file={row.has_submitted_file}",
                        f"declaration_copy={row.has_declaration_copy}",
                        f"justificante={row.has_justificante}",
                    )
                ),
            )
        )
    payload = {
        "modelo_filter": modelo,
        "year_from": resolved_from,
        "year_to": resolved_to,
        "row_count": total_count,
        "rows": [row.model_dump(mode="json") for row in all_rows],
    }
    _emit(ctx, payload, lines)


@filed_app.command("capture", help=tr("cli.app.live.filed.capture_help"))
def filed_capture_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year: Annotated[int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    period: Annotated[str | None, typer.Option("--period", help=tr("cli.app.live.period_help"))] = None,
    expediente_id: Annotated[str | None, typer.Option("--expediente", help=tr("cli.app.live.expediente_help"))] = None,
    limit: Annotated[int | None, typer.Option("--limit", min=1, help=tr("cli.app.live.limit_help"))] = None,
) -> None:
    """Capture filed-declaration data from the authenticated AEAT register."""

    report = asyncio.run(
        capture_filed_data(
            modelo=modelo,
            year=year,
            output_root=output_root,
            period=period,
            expediente_id=expediente_id,
            limit=limit,
        )
    )
    _emit(
        ctx,
        report,
        (
            _metric_line("captured_count", report.captured_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("calculation_observation_count", report.calculation_observation_count),
            _metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
            _metric_line("observation_paths", ",".join(report.observation_paths)),
            _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        ),
    )


@filed_app.command("capture-sources", help=tr("cli.app.live.filed.capture_sources_help"))
def filed_capture_sources_cmd(
    ctx: typer.Context,
    modelo: Annotated[str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help"))],
    year: Annotated[int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help"))],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help"))],
    output_root: Annotated[
        Path,
        typer.Option(
            "--output-root",
            file_okay=False,
            dir_okay=True,
            writable=True,
            help=tr("cli.app.live.output_root_help"),
        ),
    ] = Path("var/aeat/filed-declarations"),
    registry_root: Annotated[
        Path | None,
        typer.Option(
            "--registry-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.registry_root_help"),
        ),
    ] = None,
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--source-root",
            file_okay=False,
            dir_okay=True,
            readable=True,
            help=tr("cli.app.live.source_root_help"),
        ),
    ] = None,
) -> None:
    """Capture filed observations required by a target filing's dependencies."""

    report = asyncio.run(
        capture_source_filed_data(
            modelo=modelo,
            year=year,
            period=period,
            output_root=output_root,
            registry_root=registry_root,
            source_root=source_root,
        )
    )
    _emit(
        ctx,
        report,
        (
            _metric_line("captured_count", report.captured_count),
            _metric_line("casilla_count", report.casilla_count),
            _metric_line("calculation_observation_count", report.calculation_observation_count),
            _metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
            _metric_line("observation_paths", ",".join(report.observation_paths)),
            _metric_line("artefact_refs", ",".join(report.artefact_refs)),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────
# Notifications subgroup
# ─────────────────────────────────────────────────────────────────────────
# list and show read persisted DEHú notification snapshots from the
# active bucket. They are local-only reads (no AEAT contact); the
# capture verb (not shipped here) would invoke require_live_read.

notifications_app = typer.Typer(
    name="notifications",
    help=tr("cli.app.live.notifications.app_help", default="DEHú notification snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(notifications_app, name="notifications")


def _active_bucket_id() -> str:
    from ...application.workflow._models import active_bucket_id_or_raise

    try:
        return active_bucket_id_or_raise()
    except Exception as exc:
        raise typer.BadParameter(tr("cli.config.errors.no_active_profile")) from exc


@notifications_app.command(
    "capture",
    help=tr(
        "cli.app.live.notifications.capture_help",
        default="Live-fetch DEHú notifications and persist a bucket-scoped snapshot.",
    ),
)
def notifications_capture(ctx: typer.Context) -> None:
    """Drive the live DEHú fetch + persist flow.

    Refuses unless ``AEAT_LIVE_TESTS_ENABLED=1`` is set in the operator's
    shell. Will trigger the configured auth provider (e.g. Cl@ve Móvil push
    or certificate handshake) when no live session is present.
    """

    from ...application.live import capture_notifications

    bucket_id = _active_bucket_id()
    persisted = asyncio.run(capture_notifications(bucket_id=bucket_id))
    payload = {
        "bucket_id": bucket_id,
        "snapshot_id": persisted.snapshot_id,
        "captured_at": persisted.captured_at.isoformat(),
        "persisted_at": persisted.persisted_at.isoformat(),
        "row_count": len(persisted.rows),
        "source_url": persisted.source_url,
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
        f"row_count\t{len(persisted.rows)}",
        f"source_url\t{persisted.source_url}",
    ]
    _emit(ctx, payload, lines)


@notifications_app.command(
    "list",
    help=tr(
        "cli.app.live.notifications.list_help",
        default="List persisted DEHú notification snapshots in the active bucket.",
    ),
)
def notifications_list(ctx: typer.Context) -> None:
    from ...application.live._notifications import NotificationsService

    bucket_id = _active_bucket_id()
    rows = NotificationsService().list_snapshots(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "count": len(rows),
        "rows": [
            {
                "snapshot_id": r.snapshot_id,
                "captured_at": r.captured_at.isoformat(),
                "row_count": len(r.rows),
            }
            for r in rows
        ],
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.snapshot_id}\t{r.captured_at.isoformat()}\trows={len(r.rows)}")
    _emit(ctx, payload, lines)


@notifications_app.command(
    "view", help=tr("cli.app.live.notifications.view_help", default="View one DEHú notification snapshot.")
)
def notifications_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr("cli.app.live.notifications.snapshot_id_help", default="Snapshot id (or unambiguous prefix).")
        ),
    ],
) -> None:
    from ...application.live._notifications import NotificationsService

    bucket_id = _active_bucket_id()
    record = NotificationsService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    payload = {
        "bucket_id": bucket_id,
        "snapshot_id": record.snapshot_id,
        "captured_at": record.captured_at.isoformat(),
        "source_url": record.source_url,
        "row_count": len(record.rows),
        "rows": [r.model_dump(mode="json") for r in record.rows],
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"row_count\t{len(record.rows)}",
    ]
    for r in record.rows:
        lines.append("\t".join(f"{k}={v}" for k, v in r.model_dump(mode="json").items()))
    _emit(ctx, payload, lines)


# ─────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────
# Portals subgroup
# ─────────────────────────────────────────────────────────────────────────
# Portals list and show are local-only catalogue reads. They do NOT call
# AEAT and therefore do not invoke require_live_read; the
# subgroup lives under aeat app live for operator-discovery convenience.

portals_app = typer.Typer(
    name="portals",
    help=tr("cli.app.live.portals.app_help", default="Local AEAT portal registry catalogue (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(portals_app, name="portals")


def _portal_row(metadata) -> Mapping[str, object]:
    # `metadata.label` and `metadata.purpose` are Translatable
    # translation keys (e.g. `entries.portal_sede_root.label`). A bare
    # `str()` dumps the raw key path at the operator; route them
    # through `tr()` so the resolved label is emitted instead.
    return {
        "portal": metadata.portal.value,
        "category": metadata.category.value,
        "subdomain": metadata.subdomain.value,
        "url": str(metadata.url),
        "auth_methods": ",".join(sorted(method.value for method in metadata.auth_methods)),
        "url_stability": metadata.url_stability.value,
        "label": tr(str(metadata.label)),
        "purpose": tr(str(metadata.purpose)),
        "active": metadata.active,
    }


@portals_app.command(
    "list", help=tr("cli.app.live.portals.list_help", default="List portal-registry entries (optionally filtered).")
)
def portals_list(
    ctx: typer.Context,
    category: Annotated[
        str | None,
        typer.Option(
            "--category", help=tr("cli.app.live.portals.category_help", default="Filter to one PortalCategory value.")
        ),
    ] = None,
    modelo: Annotated[
        str | None,
        typer.Option(
            "--modelo",
            help=tr(
                "cli.app.live.portals.modelo_help", default="Filter to portals bound to one modelo code (e.g. 303)."
            ),
        ),
    ] = None,
) -> None:
    from ...domain.portals import PORTAL_REGISTRY, PortalCategory, portals_by_category, portals_for_modelo

    if category and modelo:
        raise typer.BadParameter(tr("cli.app.live.portals.category_modelo_exclusive"))
    if category:
        try:
            cat = PortalCategory(category)
        except ValueError as exc:
            raise typer.BadParameter(
                tr("cli.app.live.portals.unknown_category", category=category)
            ) from exc
        entries = portals_by_category(cat)
    elif modelo:
        entries = portals_for_modelo(modelo)
    else:
        entries = tuple(PORTAL_REGISTRY.values())

    rows = [_portal_row(m) for m in entries]
    payload = {"count": len(rows), "rows": rows}
    lines = [f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row['portal']}\t{row['category']}\t{row['url_stability']}\t{row['label']}")
    _emit(ctx, payload, lines)


@portals_app.command(
    "view", help=tr("cli.app.live.portals.view_help", default="View one portal-registry entry by Portal id.")
)
def portals_show(
    ctx: typer.Context,
    portal_id: Annotated[
        str, typer.Argument(help=tr("cli.app.live.portals.portal_id_help", default="Portal enum value."))
    ],
) -> None:
    from ...domain.portals import UnknownPortalError, get_portal

    try:
        metadata = get_portal(portal_id)
    except UnknownPortalError as exc:
        raise typer.BadParameter(resolve_error_message(exc)) from exc
    payload = _portal_row(metadata)
    lines = [f"{key}\t{value}" for key, value in payload.items() if value != ""]
    _emit(ctx, payload, lines)


# ─────────────────────────────────────────────────────────────────────────
# Expedientes subgroup
# ─────────────────────────────────────────────────────────────────────────
# list / show / latest are local-only reads over the bucket-scoped
# expedientes snapshot store. Capture is reserved for the live-driver
# flow which invokes require_live_read before remote contact.

expedientes_app = typer.Typer(
    name="expedientes",
    help=tr("cli.app.live.expedientes.app_help", default="AEAT expedientes snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(expedientes_app, name="expedientes")


def _expedientes_row(snapshot) -> Mapping[str, object]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "captured_at": snapshot.captured_at.isoformat(),
        "source_url": snapshot.source_url,
        "declaration_count": len(snapshot.declarations),
    }


@expedientes_app.command(
    "capture",
    help=tr(
        "cli.app.live.expedientes.capture_help",
        default="Live-walk the AEAT declaration register and persist a bucket-scoped snapshot.",
    ),
)
def expedientes_capture(
    ctx: typer.Context,
    modelo: Annotated[
        str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help", default="Modelo code (e.g. 100)."))
    ],
    year: Annotated[
        int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help", default="Filing year."))
    ],
) -> None:
    from ...application.live import capture_expedientes

    bucket_id = _active_bucket_id()
    persisted = asyncio.run(capture_expedientes(bucket_id=bucket_id, modelo=modelo, year=year))
    payload = {
        "bucket_id": bucket_id,
        "snapshot_id": persisted.snapshot_id,
        "captured_at": persisted.captured_at.isoformat(),
        "persisted_at": persisted.persisted_at.isoformat(),
        "declaration_count": len(persisted.declarations),
        "source_url": persisted.source_url,
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
        f"declaration_count\t{len(persisted.declarations)}",
        f"source_url\t{persisted.source_url}",
    ]
    _emit(ctx, payload, lines)


@expedientes_app.command(
    "list",
    help=tr(
        "cli.app.live.expedientes.list_help",
        default="List persisted expedientes snapshots in the active bucket.",
    ),
)
def expedientes_list(ctx: typer.Context) -> None:
    from ...application.live._expedientes import ExpedientesService

    bucket_id = _active_bucket_id()
    rows = ExpedientesService().list_snapshots(bucket_id=bucket_id)
    payload = {
        "bucket_id": bucket_id,
        "count": len(rows),
        "rows": [_expedientes_row(r) for r in rows],
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.snapshot_id}\t{r.captured_at.isoformat()}\tdeclarations={len(r.declarations)}")
    _emit(ctx, payload, lines)


@expedientes_app.command(
    "view",
    help=tr(
        "cli.app.live.expedientes.view_help",
        default="View one expedientes snapshot.",
    ),
)
def expedientes_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.expedientes.snapshot_id_help",
                default="Snapshot id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    from ...application.live._expedientes import ExpedientesService

    bucket_id = _active_bucket_id()
    record = ExpedientesService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    payload = {
        "bucket_id": bucket_id,
        **_expedientes_row(record),
        "declarations": [d.model_dump(mode="json") for d in record.declarations],
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"declaration_count\t{len(record.declarations)}",
    ]
    for d in record.declarations:
        lines.append(
            f"{d.expediente_id}\t{d.modelo}\t{d.ejercicio}\t{d.period}\t{d.estado}\t{d.presented_at.isoformat()}"
        )
    _emit(ctx, payload, lines)


@expedientes_app.command(
    "latest",
    help=tr(
        "cli.app.live.expedientes.latest_help",
        default="Show the most recent expedientes snapshot in the active bucket.",
    ),
)
def expedientes_latest(ctx: typer.Context) -> None:
    from ...application.live._expedientes import ExpedientesService

    bucket_id = _active_bucket_id()
    record = ExpedientesService().latest(bucket_id=bucket_id)
    if record is None:
        payload = {"bucket_id": bucket_id, "snapshot_id": None}
        _emit(ctx, payload, [f"bucket\t{bucket_id}", "snapshot_id\t-"])
        return
    payload = {
        "bucket_id": bucket_id,
        **_expedientes_row(record),
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"declaration_count\t{len(record.declarations)}",
    ]
    _emit(ctx, payload, lines)


# ─────────────────────────────────────────────────────────────────────────
# Verify subgroup
# ─────────────────────────────────────────────────────────────────────────
# Read-only audit log over NIF-IVA (VIES) and TGVI verify observations.
# Recording a fresh observation requires the live driver; the surface
# here exposes the persisted audit trail.

verify_app = typer.Typer(
    name="verify",
    help=tr("cli.app.live.verify.app_help", default="NIF verify audit log (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(verify_app, name="verify")


def _verify_row(observation) -> Mapping[str, object]:
    return {
        "observation_id": observation.observation_id,
        "surface": observation.surface.value,
        "nif": observation.nif,
        "verdict": observation.verdict,
        "expected": observation.expected,
        "matched_expectation": observation.matched_expectation,
        "checked_at": observation.checked_at.isoformat(),
    }


@verify_app.command(
    "list",
    help=tr(
        "cli.app.live.verify.list_help",
        default="List persisted verify observations (optionally filter by surface or NIF).",
    ),
)
def verify_list(
    ctx: typer.Context,
    surface: Annotated[
        str | None,
        typer.Option(
            "--surface",
            help=tr(
                "cli.app.live.verify.surface_help",
                default="Filter to one surface: nif_iva or tgvi.",
            ),
        ),
    ] = None,
    nif: Annotated[
        str | None,
        typer.Option("--nif", help=tr("cli.app.live.verify.nif_help", default="Filter to one NIF.")),
    ] = None,
) -> None:
    from ...application.live._verify import VerifyService, VerifySurface

    bucket_id = _active_bucket_id()
    resolved_surface: VerifySurface | None = None
    if surface is not None:
        try:
            resolved_surface = VerifySurface(surface)
        except ValueError as exc:
            raise typer.BadParameter(
                tr("cli.app.live.verify.unknown_surface", surface=surface),
            ) from exc
    rows = VerifyService().list_observations(
        bucket_id=bucket_id,
        surface=resolved_surface,
        nif=nif,
    )
    payload = {
        "bucket_id": bucket_id,
        "count": len(rows),
        "rows": [_verify_row(r) for r in rows],
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.observation_id}\t{r.surface.value}\t{r.nif}\t{r.verdict}\t{r.checked_at.isoformat()}")
    _emit(ctx, payload, lines)


@verify_app.command(
    "view",
    help=tr("cli.app.live.verify.view_help", default="View one persisted verify observation."),
)
def verify_show(
    ctx: typer.Context,
    observation_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.verify.observation_id_help",
                default="Observation id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    from ...application.live._verify import VerifyService

    bucket_id = _active_bucket_id()
    record = VerifyService().show(bucket_id=bucket_id, observation_id=observation_id)
    payload = {"bucket_id": bucket_id, **_verify_row(record)}
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit(ctx, payload, lines)


@verify_app.command(
    "latest",
    help=tr(
        "cli.app.live.verify.latest_help",
        default="Show the most recent observation for a (surface, NIF) pair.",
    ),
)
def verify_latest(
    ctx: typer.Context,
    surface: Annotated[
        str,
        typer.Option(
            "--surface",
            help=tr(
                "cli.app.live.verify.latest_surface_help",
                default="Verify surface: nif_iva or tgvi.",
            ),
        ),
    ],
    nif: Annotated[
        str,
        typer.Option("--nif", help=tr("cli.app.live.verify.latest_nif_help", default="NIF to look up.")),
    ],
) -> None:
    from ...application.live._verify import VerifyService, VerifySurface

    bucket_id = _active_bucket_id()
    try:
        resolved_surface = VerifySurface(surface)
    except ValueError as exc:
        raise typer.BadParameter(
            tr("cli.app.live.verify.unknown_surface", surface=surface),
        ) from exc
    record = VerifyService().latest_for_nif(
        bucket_id=bucket_id,
        surface=resolved_surface,
        nif=nif,
    )
    if record is None:
        payload = {"bucket_id": bucket_id, "surface": surface, "nif": nif, "observation_id": None}
        _emit(
            ctx,
            payload,
            [
                f"bucket\t{bucket_id}",
                f"surface\t{surface}",
                f"nif\t{nif}",
                "observation_id\t-",
            ],
        )
        return
    payload = {"bucket_id": bucket_id, **_verify_row(record)}
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit(ctx, payload, lines)


@verify_app.command(
    "nif-iva",
    help=tr(
        "cli.app.live.verify.nif_iva_help",
        default="Live-check one intra-community NIF-IVA via AEAT IXVI and persist the observation.",
    ),
)
def verify_nif_iva(
    ctx: typer.Context,
    nif: Annotated[
        str,
        typer.Argument(help=tr("cli.app.live.verify.nif_iva_arg_help", default="NIF-IVA value (e.g. ESB12345678).")),
    ],
    expected: Annotated[
        str | None,
        typer.Option(
            "--expected",
            help=tr("cli.app.live.verify.expected_help", default="Optional expected verdict (valid|invalid|unknown)."),
        ),
    ] = None,
) -> None:
    from datetime import UTC, datetime

    from ...adapters.outbound.aeat.sede._nif_iva_check import NifIvaCheckSedeDriver
    from ...application.live._verify import VerifyService, VerifySurface
    from ...core.access_gate import AeatAccessGate
    from ...core.config import load_settings

    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    nif_key = nif.strip().upper()
    expected_verdict = _verify_expected(expected)
    driver = NifIvaCheckSedeDriver(settings=settings)
    result = driver.collect(b"", expected={nif_key: (expected_verdict or "unknown")})
    if not result.observations:
        raise typer.BadParameter(tr("cli.app.live.verify.no_observation_for_nif", nif=nif))
    observation = result.observations[0]
    bucket_id = _active_bucket_id()
    record = VerifyService(settings=settings).record(
        bucket_id=bucket_id,
        surface=VerifySurface.NIF_IVA,
        nif=observation.nif,
        verdict=observation.verdict,
        checked_at=datetime.now(tz=UTC),
        expected=expected_verdict,
        raw_evidence_locator=observation.raw_evidence_locator,
    )
    payload = {"bucket_id": bucket_id, **_verify_row(record)}
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit(ctx, payload, lines)


@verify_app.command(
    "tgvi",
    help=tr(
        "cli.app.live.verify.tgvi_help",
        default="Live-check one Spanish NIF's ROI/VIES (GROI) registration and persist the observation.",
    ),
)
def verify_tgvi(
    ctx: typer.Context,
    nif: Annotated[
        str, typer.Argument(help=tr("cli.app.live.verify.tgvi_arg_help", default="Spanish NIF/NIE to check."))
    ],
    expected: Annotated[
        str | None,
        typer.Option(
            "--expected",
            help=tr("cli.app.live.verify.expected_help", default="Optional expected verdict (valid|invalid|unknown)."),
        ),
    ] = None,
) -> None:
    from datetime import UTC, datetime

    from ...adapters.outbound.aeat.sede._groi_check import GroiSedeDriver
    from ...application.live._verify import VerifyService, VerifySurface
    from ...core.access_gate import AeatAccessGate
    from ...core.config import load_settings

    settings = load_settings()
    AeatAccessGate(settings).require_live_read()
    nif_key = nif.strip().upper()
    expected_verdict = _verify_expected(expected)
    driver = GroiSedeDriver(settings=settings)
    result = driver.collect(b"", expected={nif_key: (expected_verdict or "unknown")})
    if not result.observations:
        raise typer.BadParameter(tr("cli.app.live.verify.no_observation_for_nif", nif=nif))
    observation = result.observations[0]
    bucket_id = _active_bucket_id()
    record = VerifyService(settings=settings).record(
        bucket_id=bucket_id,
        surface=VerifySurface.TGVI,
        nif=observation.nif,
        verdict=observation.verdict,
        checked_at=datetime.now(tz=UTC),
        expected=expected_verdict,
        raw_evidence_locator=observation.raw_evidence_locator,
    )
    payload = {"bucket_id": bucket_id, **_verify_row(record)}
    lines = [f"bucket\t{bucket_id}"] + [f"{k}\t{v}" for k, v in _verify_row(record).items()]
    _emit(ctx, payload, lines)


# ─────────────────────────────────────────────────────────────────────────
# Borrador 100 subgroup
# ─────────────────────────────────────────────────────────────────────────
# Bucket-scoped read surface over Modelo 100 datos-fiscales pre-fill
# snapshots. The live-fetch verb is reserved for the live driver
# flow (which invokes require_live_read); list, show, and latest operate
# purely on local state.

borrador_app = typer.Typer(
    name="borrador",
    help=tr("cli.app.live.borrador.app_help", default="Modelo 100 borrador snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(borrador_app, name="borrador")
borrador_100_app = typer.Typer(
    name="100",
    help=tr("cli.app.live.borrador.modelo_100_help", default="Modelo 100 borrador subgroup."),
    no_args_is_help=True,
    add_completion=False,
)
borrador_app.add_typer(borrador_100_app, name="100")


def _borrador_row(snapshot) -> Mapping[str, object]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "filing_year": snapshot.filing_year,
        "period": snapshot.period,
        "captured_at": snapshot.captured_at.isoformat(),
        "source_url": snapshot.source_url,
        "binding_count": len(snapshot.binding_values),
        "state": snapshot.state.value,
    }


@borrador_100_app.command(
    "list",
    help=tr(
        "cli.app.live.borrador.list_help",
        default="List persisted Modelo 100 borrador snapshots.",
    ),
)
def borrador_100_list(
    ctx: typer.Context,
    state: Annotated[
        str,
        typer.Option(
            "--state",
            help=tr(
                "cli.app.live.borrador.state_help",
                default="Snapshot state filter: active, superseded, discarded, or all.",
            ),
        ),
    ] = "active",
) -> None:
    from ...application.live import Borrador100SnapshotService, SnapshotLifecycleState

    bucket_id = _active_bucket_id()
    try:
        state_filter = None if state == "all" else SnapshotLifecycleState(state)
    except ValueError as exc:
        raise typer.BadParameter(tr("cli.app.live.borrador.invalid_state")) from exc
    rows = Borrador100SnapshotService(bucket_id=bucket_id).list_snapshots(
        state=state_filter,
    )
    payload = {
        "bucket_id": bucket_id,
        "count": len(rows),
        "rows": [_borrador_row(r) for r in rows],
    }
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(
            f"{r.snapshot_id}\t{r.filing_year}\t{r.period}\t{r.captured_at.isoformat()}\t"
            f"bindings={len(r.binding_values)}\t{r.state.value}"
        )
    _emit(ctx, payload, lines)


@borrador_100_app.command(
    "view",
    help=tr(
        "cli.app.live.borrador.view_help",
        default="View one Modelo 100 borrador snapshot.",
    ),
)
def borrador_100_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.borrador.snapshot_id_help",
                default="Snapshot id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    from ...application.live import Borrador100SnapshotService

    bucket_id = _active_bucket_id()
    record = Borrador100SnapshotService(bucket_id=bucket_id).show(snapshot_id)
    payload = {
        "bucket_id": bucket_id,
        **_borrador_row(record),
        "binding_values": dict(record.binding_values),
    }
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"binding_count\t{len(record.binding_values)}",
        f"state\t{record.state.value}",
    ]
    _emit(ctx, payload, lines)


@borrador_100_app.command(
    "latest",
    help=tr(
        "cli.app.live.borrador.latest_help",
        default="Show the most recent active snapshot for a filing year.",
    ),
)
def borrador_100_latest(
    ctx: typer.Context,
    filing_year: Annotated[
        int,
        typer.Option(
            "--filing-year",
            min=2000,
            max=2099,
            help=tr("cli.app.live.borrador.filing_year_help", default="Filing year (e.g. 2024)."),
        ),
    ],
) -> None:
    from ...application.live import Borrador100SnapshotService

    bucket_id = _active_bucket_id()
    record = Borrador100SnapshotService(bucket_id=bucket_id).latest_for_year(filing_year=filing_year)
    if record is None:
        payload = {"bucket_id": bucket_id, "filing_year": filing_year, "snapshot_id": None}
        _emit(
            ctx,
            payload,
            [
                f"bucket\t{bucket_id}",
                f"filing_year\t{filing_year}",
                "snapshot_id\t-",
            ],
        )
        return
    payload = {"bucket_id": bucket_id, **_borrador_row(record)}
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"binding_count\t{len(record.binding_values)}",
    ]
    _emit(ctx, payload, lines)


__all__ = [
    "app",
    "borrador_100_app",
    "borrador_app",
    "expedientes_app",
    "filed_app",
    "filed_capture_cmd",
    "filed_capture_sources_cmd",
    "filed_list_cmd",
    "iva_wallet_app",
    "iva_wallet_capture_history_cmd",
    "iva_wallet_history_cmd",
    "iva_wallet_pull_cmd",
    "portals_app",
    "portals_list",
    "portals_show",
    "verify_app",
]
