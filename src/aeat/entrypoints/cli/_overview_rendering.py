"""Text rendering and notice projection for ``overview status``.

This module consumes an application-built
:class:`~aeat.application.overview.OverviewStatusReport` and turns it into
localized text lines plus :class:`~aeat.core.json_contract.Notice` objects for the
:class:`~aeat.core.json_contract.SchemaEnvelope` notice channel.  It is
presentation-only: active-profile discovery, storage reads, and status assembly
stay upstream in :mod:`~aeat.application.overview` and
:mod:`~aeat.entrypoints.cli._overview`.
"""

from __future__ import annotations

from ...application.overview import OverviewStatusReport
from ...core import Modelo
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity


def overview_next_step_notices(report: OverviewStatusReport) -> list[Notice]:
    """Surface the workspace-state next-step guidance as :class:`~aeat.core.json_contract.Notice` values.

    Mirrors the text-mode ``_next_step_lines`` guidance so JSON consumers
    receive the same forward guidance the text surface already shows,
    through the uniform envelope ``notices`` channel rather than a bespoke
    payload field. Info severity keeps the envelope ``status`` at
    ``success``.
    """
    return [
        Notice(severity=NoticeSeverity.INFO, code="overview.status.next_step", message=line.strip())
        for line in _next_step_lines(report)
        if line.strip()
    ]


def render_cli_overview_status_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Render :class:`~aeat.application.overview.OverviewStatusReport` as operator-facing CLI text.

    The renderer preserves the same next-step decisions used by
    :func:`~aeat.entrypoints.cli._overview_rendering.overview_next_step_notices`,
    so text and JSON-envelope notice output stay aligned.
    """
    lines: list[str] = [
        tr("cli.overview.status.title"),
        "",
        _profile_line(report),
        _transactions_line(report),
        _invoices_line(report),
        _drafts_line(report),
        _work_units_line(report),
        *_storage_lines(report),
        *_filing_obligation_lines(report),
        "",
        tr("cli.overview.status.next_heading"),
        *_next_step_lines(report),
    ]
    return tuple(lines)


def _next_step_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Return next-step guidance that reflects the actual workspace state.

    A workspace with ledger data already recorded must not be told to
    "import a bank statement" — that step is done. The guidance walks
    the operator forward: import when the ledger is empty, classify /
    work-modelo when transactions exist, continue the modelo flow when
    work units are already in progress. Unsupported
    :class:`~aeat.core.Modelo` work-unit creation is diverted to discovery
    guidance instead of a dead command.
    """
    if report.work_units > 0:
        return (
            tr(
                "cli.overview.status.next_work_calculate_command",
                default="  aeat app modelo work list - resume an in-progress modelo work unit.",
            ),
            _modelo_work_create_guidance_line(report),
            tr("cli.overview.status.next_landing_command"),
        )
    if report.transactions > 0 or report.invoices > 0:
        return (
            tr(
                "cli.overview.status.next_review_command",
            ),
            _modelo_work_from_ledger_guidance_line(report),
            tr("cli.overview.status.next_landing_command"),
        )
    return (
        tr("cli.overview.status.next_import_command"),
        tr("cli.overview.status.next_review_command"),
        tr("cli.overview.status.next_landing_command"),
    )


def _modelo_210_unsupported_guidance_line(report: OverviewStatusReport) -> str | None:
    if Modelo.M210.value in report.unsupported_work_create_modelos:
        return tr(
            "cli.overview.status.next_modelo_210_unsupported_command",
            default=(
                "  aeat app modelo describe 210 - Modelo 210 is visible for IRNR discovery, "
                "but local work-unit creation is not supported yet; file through AEAT Sede G320."
            ),
        )
    return None


def _modelo_work_create_guidance_line(report: OverviewStatusReport) -> str:
    return _modelo_210_unsupported_guidance_line(report) or tr(
        "cli.overview.status.next_work_create_command",
        default="  aeat app modelo work create - start a work unit for another modelo.",
    )


def _modelo_work_from_ledger_guidance_line(report: OverviewStatusReport) -> str:
    return _modelo_210_unsupported_guidance_line(report) or tr(
        "cli.overview.status.next_modelo_work_command",
        default="  aeat app modelo work create - start a modelo declaration from your ledger data.",
    )


def _work_units_line(report: OverviewStatusReport) -> str:
    if report.work_units == 0 and report.discarded_work_units == 0:
        return tr(
            "cli.overview.status.work_units_empty",
            default="No modelo work units have been started yet.",
        )
    if report.discarded_work_units > 0:
        # The bare total misleads when some units are discarded: the
        # operator reads "5 work units" and counts abandoned ones as
        # live work. The line states the active / discarded split.
        return tr(
            "cli.overview.status.work_units_present_with_discarded",
            default=(
                "%{count} active modelo work unit(s) (%{discarded} discarded) "
                "in this local storage - your active modelo work is saved; "
                "resume it with `aeat app modelo work list`."
            ),
            count=report.work_units,
            discarded=report.discarded_work_units,
        )
    return tr(
        "cli.overview.status.work_units_present",
        default=(
            "%{count} modelo work unit(s) are in progress in this local storage "
            "- your modelo work is saved; resume it with `aeat app modelo work list`."
        ),
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
        # Two independent operators read the bare "no saved declaration
        # drafts" line - which sits next to the work-units line - as
        # "your work is gone". When work units exist, the line must say
        # so explicitly: declaration drafts and modelo work units are
        # separate stores, and an empty draft store never means lost
        # modelo work.
        if report.work_units > 0:
            return tr(
                "cli.overview.status.drafts_empty_with_work_units",
                default=(
                    "No declaration drafts are saved - this is normal and "
                    "does not affect your modelo work units below."
                ),
            )
        return tr("cli.overview.status.drafts_empty")
    return tr("cli.overview.status.drafts_present", count=report.drafts)


def _storage_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    if report.unreadable_rows == 0:
        return (tr("cli.overview.status.storage_ok"),)
    return (
        tr("cli.overview.status.storage_warning", count=report.unreadable_rows),
        tr("cli.overview.status.integrity_next"),
    )


def _filing_obligation_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Return localized filing-obligation advisory lines from the report."""
    if not report.filing_obligation_advisories:
        return ()
    lines: list[str] = [""]
    for key in report.filing_obligation_advisories:
        lines.append(tr(key))
    return tuple(lines)


__all__ = ["render_cli_overview_status_lines"]
