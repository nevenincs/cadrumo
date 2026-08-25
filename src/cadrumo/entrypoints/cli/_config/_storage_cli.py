"""``aeat config storage`` — inspect and maintain the local storage tree.

A lifecycle-operations-only noun-group: the internal member set is fixed by the
core taxonomy, while operators see four stable aggregate areas.

There is deliberately no verb that moves data or relocates the root. Asked where
the tree is, ``list`` answers and names the environment variable that points at
it; moving it is the operator's own copy followed by re-pointing that variable.
The tree holds encrypted taxpayer records, the key material that opens them, and
the audit trail over both, and a cross-filesystem copy that completes for the
records while failing for the keystore leaves neither usable.

Refusals raised by the service are registered :class:`CadrumoError` subclasses
and propagate to the shared command error boundary unchanged, so ``reclaim``'s
refusal reaches the operator with its registered code, its rendered reason, and
its follow-up suggestion rather than a re-worded copy made here.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from textwrap import TextWrapper
from typing import TYPE_CHECKING, Final

import typer

from ....application.operator_actions import ActionReference
from ....application.storage_management import StorageCheckIssueKind, StorageTreeIssueKind
from ....core import StorageArea
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from ._storage_payloads import (
    ConfigStorageCheckResult,
    ConfigStorageInitResult,
    ConfigStorageListResult,
    ConfigStorageReclaimResult,
    ConfigStorageShowResult,
    StorageAreaIssuePayload,
    StorageAreaPayload,
)

if TYPE_CHECKING:
    from ....application.storage_management import StorageAreaInventoryReport, StorageAreaInventoryRow

from ....core.external_constants import OutputLanguage as _OutputLanguage

_ROOT_ENV_VAR: Final[str] = "CADRUMO_LOCAL_STORAGE_ROOT"
"""Environment variable an operator sets to point the tree somewhere else.

Named in the relocation advisory because the advisory's whole job is to hand the
operator the one control that does relocate, having refused to do it for them.
"""


def config_storage_list(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Report every declared location, its resolved path, and what it holds."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import collect_storage_area_inventory

    report = collect_storage_area_inventory()
    result = ConfigStorageListResult(
        storage_root=str(report.storage_root),
        areas=[_area_payload(row) for row in report.rows],
    )
    notices = (_relocation_notice(str(report.storage_root)),)
    lines = _inventory_lines(report)
    lines.extend(_notice_lines(notices))
    emit_envelope(
        ctx,
        command="config.storage.list",
        result=result,
        lines=tuple(lines),
        notices=notices,
    )


def config_storage_show(
    ctx: typer.Context,
    area: StorageArea,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Report one declared location in full."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import collect_storage_area_inventory

    report = collect_storage_area_inventory()
    row = _row_for(report, area)
    result = ConfigStorageShowResult(
        storage_root=str(report.storage_root),
        area=_area_payload(row),
    )
    lines = _field_lines(
        (
            (_label("area", "Area"), _value_label("area", row.area.value)),
            (_label("occupancy", "Occupancy"), _value_label("occupancy", row.occupancy.value)),
            (_label("lifecycle", "Lifecycle"), _value_label("lifecycle", row.disposition.value)),
            (_label("resolved_paths", "Resolved paths"), str(row.resolved_paths)),
            (_label("entry_count", "Entry count"), str(row.entry_count)),
            (_label("footprint", "Footprint"), _format_bytes(row.footprint_bytes)),
            (_label("reclaimable", "Reclaimable"), _boolean_label(row.reclaimable)),
        ),
    )
    emit_envelope(ctx, command="config.storage.show", result=result, lines=tuple(lines))


def config_storage_check(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Verify the tree on disk against its declaration, repairing nothing."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import inspect_storage_tree

    report = inspect_storage_tree()
    result = ConfigStorageCheckResult(
        storage_root=str(report.storage_root),
        healthy=report.healthy,
        root_mode_enforced=report.root_mode_enforced,
        checked_areas=len(StorageArea),
        issues=[
            StorageAreaIssuePayload(
                kind=_public_issue_kind(issue.kind),
                path=str(report.storage_root),
                area=issue.area,
                detail=_public_issue_detail(issue.kind),
            )
            for issue in report.issues
        ],
    )
    lines = _field_lines(
        (
            (_label("storage_root", "Storage root"), str(report.storage_root)),
            (_label("checked_areas", "Checked areas"), str(len(StorageArea))),
            (_label("healthy", "Healthy"), _boolean_label(report.healthy)),
        ),
    )
    if report.issues:
        lines.extend(("", f"{_label('issues', 'Issues')} ({len(report.issues)}):"))
        for issue in report.issues:
            lines.extend(
                (
                    f"  - {_public_issue_kind(issue.kind).value}",
                    f"    {_label('area', 'Area')}: {_value_label('area', issue.area.value) if issue.area else '-'}",
                    f"    {_label('path', 'Path')}: {report.storage_root}",
                    f"    {_label('detail', 'Detail')}: {_public_issue_detail(issue.kind)}",
                ),
            )

    notices: list[Notice] = []
    if not report.root_mode_enforced:
        # An empty issue list on such a host means the permission axis was not
        # examined, which is a different claim from examined-and-clean.
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="storage_root_mode_unenforced",
                message=tr(
                    "cli.config.storage.check.mode_unenforced",
                ),
                context={"storage_root": str(report.storage_root)},
            ),
        )
    if not report.healthy:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="storage_tree_drifted",
                message=tr(
                    "cli.config.storage.check.drifted",
                ),
                action=resolve_notice_action(action=ActionReference(action_id="operator.storage.init")),
                context={"issue_count": str(len(report.issues))},
            ),
        )
    lines.extend(_notice_lines(notices))
    emit_envelope(ctx, command="config.storage.check", result=result, lines=tuple(lines), notices=tuple(notices))
    if not report.healthy:
        raise typer.Exit(code=2)


def config_storage_init(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Materialise the declared tree, preserving everything already in it."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import materialise_storage_tree

    report = materialise_storage_tree()
    result = ConfigStorageInitResult(
        storage_root=str(report.storage_root),
        created_count=len(report.created),
        already_present=report.already_present,
    )
    lines = _field_lines(
        (
            (_label("storage_root", "Storage root"), str(report.storage_root)),
            (_label("already_present", "Already present"), str(report.already_present)),
            (_label("created", "Created"), str(len(report.created))),
        ),
    )
    notices: tuple[Notice, ...] = ()
    if not report.created:
        notices = (
            Notice(
                severity=NoticeSeverity.INFO,
                code="storage_tree_already_materialised",
                message=tr(
                    "cli.config.storage.init.already_materialised",
                ),
                context={"storage_root": str(report.storage_root)},
            ),
        )
    lines.extend(_notice_lines(notices))
    emit_envelope(ctx, command="config.storage.init", result=result, lines=tuple(lines), notices=notices)


def config_storage_reclaim(
    ctx: typer.Context,
    area: StorageArea,
    confirmed: bool = False,
    output_language: _OutputLanguage | None = None,
) -> None:
    """Delete an area's regenerable contents after the derived preflight.

    The service owns both refusals — the lifecycle guard and the confirmation —
    and both are registered errors, so they surface through the shared command
    error boundary naming the resolved path, the entries left untouched, and the
    declared lifecycle that forbade the delete.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import reclaim_storage_area

    report = reclaim_storage_area(area, confirmed=confirmed)
    result = ConfigStorageReclaimResult(
        area=report.area,
        target_count=report.target_count,
        removed_entries=report.removed_entries,
        retained_entries=report.retained_entries,
    )
    lines = _field_lines(
        (
            (_label("area", "Area"), _value_label("area", report.area.value)),
            (_label("targets", "Targets"), str(report.target_count)),
            (_label("removed_entries", "Removed entries"), str(report.removed_entries)),
            (_label("retained_entries", "Retained entries"), str(report.retained_entries)),
        ),
    )
    notices: tuple[Notice, ...] = ()
    if report.retained_entries:
        notices = (
            Notice(
                severity=NoticeSeverity.WARNING,
                code="storage_reclaim_incomplete",
                message=tr(
                    "cli.config.storage.reclaim.incomplete",
                ),
                context={
                    "area": report.area.value,
                    "retained_entries": str(report.retained_entries),
                },
            ),
        )
    lines.extend(_notice_lines(notices))
    emit_envelope(ctx, command="config.storage.reclaim", result=result, lines=tuple(lines), notices=notices)


def _relocation_notice(storage_root: str) -> Notice:
    """Return the standing advisory that relocation is the operator's own move.

    ``list`` is where an operator asks "where is my data", and the next question
    is invariably "can I move it". This answers both at once rather than waiting
    for a relocation verb that will not exist.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code="storage_root_relocation_is_manual",
        message=tr(
            "cli.config.storage.list.relocation_is_manual",
            variable=_ROOT_ENV_VAR,
        ),
        context={"storage_root": storage_root, "variable": _ROOT_ENV_VAR},
    )


def _row_for(report: StorageAreaInventoryReport, area: StorageArea) -> StorageAreaInventoryRow:
    """Return the single aggregate row for ``area``."""
    for row in report.rows:
        if row.area is area:
            return row
    raise KeyError(f"storage area {area.value!r} has no aggregate")


def _area_payload(row: StorageAreaInventoryRow) -> StorageAreaPayload:
    """Project one aggregate row onto its topology-neutral wire shape."""
    return StorageAreaPayload(
        area=row.area,
        occupancy=row.occupancy,
        disposition=row.disposition,
        resolved_paths=row.resolved_paths,
        entry_count=row.entry_count,
        footprint_bytes=row.footprint_bytes,
        reclaimable=row.reclaimable,
    )


def _inventory_lines(report: StorageAreaInventoryReport) -> list[str]:
    """Render the inventory as a compact table with paths on readable lines."""
    lines = _field_lines(
        ((_label("storage_root", "Storage root"), str(report.storage_root)),),
    )
    lines.extend(("", f"{_label('areas', 'Areas')} ({len(report.rows)}):"))
    rows = [
        (
            _value_label("area", row.area.value),
            _value_label("lifecycle", row.disposition.value),
            _value_label("occupancy", row.occupancy.value),
            str(row.entry_count),
            _format_bytes(row.footprint_bytes),
        )
        for row in report.rows
    ]
    table = _table_lines(
        (
            _label("area", "Area"),
            _label("lifecycle", "Lifecycle"),
            _label("occupancy", "Occupancy"),
            _label("entries", "Entries"),
            _label("footprint", "Footprint"),
        ),
        rows,
    )
    lines.extend(table)
    return lines


def _public_issue_kind(kind: StorageTreeIssueKind) -> StorageCheckIssueKind:
    """Collapse internal node diagnoses into a topology-neutral public kind."""
    if kind is StorageTreeIssueKind.MISSING_DIRECTORY:
        return StorageCheckIssueKind.MISSING_PATH
    if kind is StorageTreeIssueKind.ROOT_PERMISSIONS_DRIFTED:
        return StorageCheckIssueKind.PERMISSIONS_DRIFTED
    return StorageCheckIssueKind.PATH_TYPE_MISMATCH


def _public_issue_detail(kind: StorageTreeIssueKind) -> str:
    """Describe a check failure without revealing internal node topology."""
    public = _public_issue_kind(kind)
    if public is StorageCheckIssueKind.MISSING_PATH:
        return tr("cli.config.storage.check.issue.missing_path")
    if public is StorageCheckIssueKind.PERMISSIONS_DRIFTED:
        return tr("cli.config.storage.check.issue.permissions_drifted")
    return tr("cli.config.storage.check.issue.path_type_mismatch")


def _label(name: str, default: str) -> str:
    """Return one localized text-mode label."""
    return tr(f"cli.config.storage.labels.{name}")


def _boolean_label(value: bool) -> str:
    """Render a boolean in the selected output language."""
    return _label("yes", "yes") if value else _label("no", "no")


def _value_label(axis: str, value: str) -> str:
    """Render a closed report value in the selected output language."""
    return tr(f"cli.config.storage.values.{axis}.{value}")


def _format_bytes(value: int) -> str:
    """Render an exact byte footprint without hiding the unit."""
    return f"{value} B"


def _field_lines(fields: Sequence[tuple[str, str]]) -> list[str]:
    """Render labelled values with one stable, human-readable alignment."""
    width = max(len(label) for label, _ in fields)
    return [f"{label:<{width}}  {value}" for label, value in fields]


def _table_lines(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> list[str]:
    """Render a plain table that remains legible in redirected output."""
    materialised = list(rows)
    widths = [max(len(header), *(len(row[index]) for row in materialised)) for index, header in enumerate(headers)]

    def render(row: tuple[str, ...]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(row)).rstrip()

    return [render(headers), render(tuple("-" * width for width in widths)), *(render(row) for row in materialised)]


def _notice_lines(notices: Sequence[Notice]) -> list[str]:
    """Render typed notices visibly in text mode as well as JSON mode."""
    lines: list[str] = []
    for notice in notices:
        prefix = f"{_label(f'notice_{notice.severity.value}', notice.severity.value.title())}: "
        lines.extend(
            TextWrapper(
                width=96,
                initial_indent=prefix,
                subsequent_indent=" " * len(prefix),
                break_long_words=False,
                break_on_hyphens=False,
            ).wrap(notice.message),
        )
    return ["", *lines] if lines else []


__all__ = [
    "config_storage_check",
    "config_storage_init",
    "config_storage_list",
    "config_storage_reclaim",
    "config_storage_show",
]
