from __future__ import annotations

from ...application.overview import OverviewStatusReport
from ...core.i18n import tr


def render_cli_overview_status_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Render overview status as operator-facing CLI text."""

    lines: list[str] = [
        tr("cli.overview.status.title"),
        "",
        _profile_line(report),
        _transactions_line(report),
        _invoices_line(report),
        _drafts_line(report),
        _work_units_line(report),
        *_storage_lines(report),
        "",
        tr("cli.overview.status.next_heading"),
        tr("cli.overview.status.next_import_command"),
        tr("cli.overview.status.next_review_command"),
        tr("cli.overview.status.next_landing_command"),
    ]
    return tuple(lines)


def _work_units_line(report: OverviewStatusReport) -> str:
    if report.work_units == 0:
        return tr(
            "cli.overview.status.work_units_empty",
            default="No modelo work units have been started yet.",
        )
    return tr(
        "cli.overview.status.work_units_present",
        default="%{count} modelo work unit(s) exist in this local storage.",
        count=report.work_units,
    )


def _profile_line(report: OverviewStatusReport) -> str:
    if report.active_profile is None:
        return tr("cli.overview.status.profile_missing")
    # The prose line names the operator-chosen display name only; the
    # immutable bucket UUID is structured-payload noise in prose and is
    # carried solely on the JSON / secondary `profile_id` field. Fall
    # back to the UUID alone when the manifest carried no display name.
    name = report.active_profile_name
    if name:
        return tr("cli.overview.status.profile_active", profile=name)
    return tr("cli.overview.status.profile_active", profile=report.active_profile)


def _transactions_line(report: OverviewStatusReport) -> str:
    if report.transactions == 0:
        return tr("cli.overview.status.transactions_empty")
    return tr("cli.overview.status.transactions_present", count=report.transactions)


def _invoices_line(report: OverviewStatusReport) -> str:
    if report.invoices == 0:
        return tr("cli.overview.status.invoices_empty")
    return tr("cli.overview.status.invoices_present", count=report.invoices)


def _drafts_line(report: OverviewStatusReport) -> str:
    if report.drafts == 0:
        return tr("cli.overview.status.drafts_empty")
    return tr("cli.overview.status.drafts_present", count=report.drafts)


def _storage_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    if report.unreadable_rows == 0:
        return (tr("cli.overview.status.storage_ok"),)
    return (
        tr("cli.overview.status.storage_warning", count=report.unreadable_rows),
        tr("cli.overview.status.integrity_next"),
    )


__all__ = ["render_cli_overview_status_lines"]
