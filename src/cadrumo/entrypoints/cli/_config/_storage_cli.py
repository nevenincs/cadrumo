"""``aeat config storage`` — inspect and maintain the local storage tree.

A lifecycle-operations-only noun-group: the member set is fixed by the core
storage taxonomy, so an operator can read the tree, materialise it, and reclaim
what a member's declared lifecycle says is regenerable, but cannot create or
destroy a category.

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

from typing import TYPE_CHECKING, Final

import typer

from ....application.operator_actions import ActionReference
from ....core import StorageCategory
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import _emit_envelope, resolve_notice_action
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language

# Eager import so the @register_schema decorators run on the CLI build path.
from ._storage_payloads import (
    ConfigStorageCheckResult,
    ConfigStorageInitResult,
    ConfigStorageListResult,
    ConfigStorageReclaimResult,
    ConfigStorageShowResult,
    StorageCategoryPayload,
    StorageTreeIssuePayload,
)

if TYPE_CHECKING:
    from ....application.storage_management import StorageInventoryReport, StorageInventoryRow

from ....core.external_constants import OutputLanguage as _OutputLanguage

_ROOT_ENV_VAR: Final[str] = "CADRUMO_LOCAL_STORAGE_ROOT"
"""Environment variable an operator sets to point the tree somewhere else.

Named in the relocation advisory because the advisory's whole job is to hand the
operator the one control that does relocate, having refused to do it for them.
"""

storage_app = typer.Typer(
    name="storage",
    help=tr("cli.config.storage.help", default="Inspect and maintain the local storage tree"),
    no_args_is_help=True,
)


def register_storage_commands(config_app: typer.Typer) -> None:
    """Mount the ``storage`` noun-group on the config ``app``."""
    config_app.add_typer(storage_app, name="storage")


@storage_app.command("list", help=tr("cli.config.storage.list.help"))
def config_storage_list(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Report every declared location, its resolved path, and what it holds."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import collect_storage_inventory

    report = collect_storage_inventory()
    result = ConfigStorageListResult(
        storage_root=str(report.storage_root),
        active_profile_bucket=report.active_bucket_id,
        categories=[_category_payload(row) for row in report.rows],
    )
    lines = [f"storage_root\t{report.storage_root}"]
    if report.active_bucket_id:
        lines.append(f"active_profile_bucket\t{report.active_bucket_id}")
    lines.extend(_row_line(row) for row in report.rows)
    _emit_envelope(
        ctx,
        command="config.storage.list",
        result=result,
        lines=tuple(lines),
        notices=(_relocation_notice(str(report.storage_root)),),
    )


@storage_app.command("show", help=tr("cli.config.storage.show.help"))
def config_storage_show(
    ctx: typer.Context,
    category: StorageCategory = typer.Argument(..., help=tr("cli.config.storage.show.category_help")),
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Report one declared location in full."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import collect_storage_inventory

    report = collect_storage_inventory()
    row = _row_for(report, category)
    result = ConfigStorageShowResult(
        storage_root=str(report.storage_root),
        active_profile_bucket=report.active_bucket_id,
        category=_category_payload(row),
    )
    lines = [
        f"category\t{row.category.value}",
        f"path\t{row.path if row.path is not None else '-'}",
        f"subpath\t{row.subpath}",
        f"node_kind\t{row.node_kind.value}",
        f"scope\t{row.scope.value}",
        f"grouping\t{row.grouping.value}",
        f"lifecycle\t{row.lifecycle.value}",
        f"override_policy\t{row.override_policy.value}",
        f"fingerprint\t{row.fingerprint_participation.value}",
        f"settings_field\t{row.settings_field or '-'}",
        f"occupancy\t{row.occupancy.value}",
        f"entry_count\t{row.entry_count}",
        f"reclaimable\t{'yes' if row.reclaimable else 'no'}",
    ]
    _emit_envelope(ctx, command="config.storage.show", result=result, lines=tuple(lines))


@storage_app.command("check", help=tr("cli.config.storage.check.help"))
def config_storage_check(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Verify the tree on disk against its declaration, repairing nothing."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import inspect_storage_tree

    report = inspect_storage_tree()
    result = ConfigStorageCheckResult(
        storage_root=str(report.storage_root),
        healthy=report.healthy,
        root_mode_enforced=report.root_mode_enforced,
        checked_locations=report.checked_locations,
        issues=[
            StorageTreeIssuePayload(
                kind=issue.kind,
                path=str(issue.path),
                category=issue.category,
                detail=issue.detail,
            )
            for issue in report.issues
        ],
    )
    lines = [
        f"storage_root\t{report.storage_root}",
        f"checked_locations\t{report.checked_locations}",
        f"healthy\t{'yes' if report.healthy else 'no'}",
    ]
    lines.extend(
        f"issue\t{issue.kind.value}\t{issue.category.value if issue.category else '-'}\t{issue.path}\t{issue.detail}"
        for issue in report.issues
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
                    default=(
                        "This platform does not implement POSIX permission bits, so root permissions were not checked."
                    ),
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
                    default="The storage tree does not match its declaration.",
                ),
                action=resolve_notice_action(action=ActionReference(action_id="operator.storage.init")),
                context={"issue_count": str(len(report.issues))},
            ),
        )
    _emit_envelope(ctx, command="config.storage.check", result=result, lines=tuple(lines), notices=tuple(notices))
    if not report.healthy:
        raise typer.Exit(code=2)


@storage_app.command("init", help=tr("cli.config.storage.init.help"))
def config_storage_init(
    ctx: typer.Context,
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Materialise the declared tree, preserving everything already in it."""
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import materialise_storage_tree

    report = materialise_storage_tree()
    result = ConfigStorageInitResult(
        storage_root=str(report.storage_root),
        created=[str(path) for path in report.created],
        already_present=report.already_present,
    )
    lines = [
        f"storage_root\t{report.storage_root}",
        f"already_present\t{report.already_present}",
    ]
    lines.extend(f"created\t{path}" for path in report.created)
    notices: tuple[Notice, ...] = ()
    if not report.created:
        notices = (
            Notice(
                severity=NoticeSeverity.INFO,
                code="storage_tree_already_materialised",
                message=tr(
                    "cli.config.storage.init.already_materialised",
                    default="Every declared directory already existed; nothing was created.",
                ),
                context={"storage_root": str(report.storage_root)},
            ),
        )
    _emit_envelope(ctx, command="config.storage.init", result=result, lines=tuple(lines), notices=notices)


@storage_app.command("reclaim", help=tr("cli.config.storage.reclaim.help"))
def config_storage_reclaim(
    ctx: typer.Context,
    category: StorageCategory = typer.Argument(..., help=tr("cli.config.storage.reclaim.category_help")),
    confirmed: bool = typer.Option(False, "--yes", help=tr("cli.config.storage.reclaim.yes_help")),
    output_language: _OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Delete a category's regenerable contents, refusing where its lifecycle forbids it.

    The service owns both refusals — the lifecycle guard and the confirmation —
    and both are registered errors, so they surface through the shared command
    error boundary naming the resolved path, the entries left untouched, and the
    declared lifecycle that forbade the delete.
    """
    _activate_subcommand_output_language(ctx, output_language)
    from ....application.storage_management import reclaim_storage_category

    report = reclaim_storage_category(category, confirmed=confirmed)
    result = ConfigStorageReclaimResult(
        category=report.category,
        path=str(report.path),
        removed_entries=report.removed_entries,
        retained_entries=report.retained_entries,
    )
    lines = [
        f"category\t{report.category.value}",
        f"path\t{report.path}",
        f"removed_entries\t{report.removed_entries}",
        f"retained_entries\t{report.retained_entries}",
    ]
    notices: tuple[Notice, ...] = ()
    if report.retained_entries:
        notices = (
            Notice(
                severity=NoticeSeverity.WARNING,
                code="storage_reclaim_incomplete",
                message=tr(
                    "cli.config.storage.reclaim.incomplete",
                    default="Some entries could not be removed and are still on disk.",
                ),
                context={
                    "category": report.category.value,
                    "retained_entries": str(report.retained_entries),
                },
            ),
        )
    _emit_envelope(ctx, command="config.storage.reclaim", result=result, lines=tuple(lines), notices=notices)


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
            default=(
                "To move the tree, stop Cadrumo, copy it yourself, then point "
                "%{variable} at the new location. No command moves it, because a copy "
                "that completes for the records but not for the key material leaves neither usable."
            ),
            variable=_ROOT_ENV_VAR,
        ),
        context={"storage_root": storage_root, "variable": _ROOT_ENV_VAR},
    )


def _row_for(report: StorageInventoryReport, category: StorageCategory) -> StorageInventoryRow:
    """Return the single inventory row for ``category``.

    The taxonomy is total over the enum, so a member always has exactly one row;
    a lookup that found none would mean the declaration had gone partial, which
    is worth failing on rather than reporting as an absent category.
    """
    for row in report.rows:
        if row.category is category:
            return row
    raise KeyError(f"storage category {category.value!r} has no declaration")


def _category_payload(row: StorageInventoryRow) -> StorageCategoryPayload:
    """Project one inventory row onto its wire shape."""
    return StorageCategoryPayload(
        category=row.category,
        subpath=row.subpath,
        node_kind=row.node_kind,
        scope=row.scope,
        grouping=row.grouping,
        lifecycle=row.lifecycle,
        override_policy=row.override_policy,
        fingerprint_participation=row.fingerprint_participation,
        settings_field=row.settings_field,
        path=str(row.path) if row.path is not None else None,
        bucket_id=row.bucket_id,
        occupancy=row.occupancy,
        entry_count=row.entry_count,
        reclaimable=row.reclaimable,
    )


def _row_line(row: StorageInventoryRow) -> str:
    """Render one inventory row as a tab-separated text line."""
    return "\t".join(
        (
            "category",
            row.category.value,
            str(row.path) if row.path is not None else "-",
            row.node_kind.value,
            row.grouping.value,
            row.lifecycle.value,
            row.scope.value,
            row.settings_field or "-",
            row.occupancy.value,
            str(row.entry_count),
        ),
    )


__all__ = ["register_storage_commands", "storage_app"]
