"""CLI commands for the ``aeat config profile archive`` subcommand group.

Provides ``reconcile``: a local-only, on-demand sweep that
resolves crash-interrupted portable profile-bundle publications. The export
service already reconciles before every publication, so an operator who keeps
exporting never needs this verb. It exists for the case that trigger
structurally cannot reach -- a crash followed by no further export -- where the
orphan journal and, in the pre-replace window, a ``0o600`` cleartext
``.export-tmp`` holding the whole profile bundle would otherwise sit on disk
indefinitely against ``sensitive-financial-data-secure-storage-only``.

The verb never contacts AEAT and performs no network call. It reads the
credential-free journals under the local storage root, and for an export that
did durably publish it writes the owed ``PROFILE_EXPORTED`` audit event into
encrypted local secure-object storage.

This module is the transport adapter over
:func:`~application.user_profile.reconcile_prepared_exports`. It emits
:class:`~entrypoints.cli.config._archive_reconcile_payloads.ProfileBundleReconcileResult`
through :func:`emit_envelope`, and reports both halves of the outcome through
the typed :class:`Notice` channel per
``aeat-cli-contract``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ....application.operator_actions.models import ActionReference
from ....core.external_constants import OutputLanguage
from ....core.i18n import tr
from ....core.json_contract import Notice, NoticeSeverity
from .._common import activate_subcommand_output_language as _activate_subcommand_output_language
from .._common import emit_envelope, resolve_notice_action
from ._archive_reconcile_payloads import (
    ProfileBundleReconcileResult,
    ReconciledProfileExportPayload,
    UnreconciledProfileExportPayload,
)

if TYPE_CHECKING:
    from ....application.user_profile.bundle_export import ProfileBundleExportReconciliation


def profile_archive_reconcile(
    ctx: typer.Context,
    output_language: OutputLanguage | None = None,
) -> None:
    """Resolve crash-interrupted portable profile-bundle publications."""
    from ....application.user_profile.bundle_export import reconcile_prepared_exports

    _activate_subcommand_output_language(ctx, output_language)
    outcome = reconcile_prepared_exports()

    result = ProfileBundleReconcileResult(
        reconciled_count=len(outcome.reconciled),
        failed_count=len(outcome.failures),
        reconciled=[
            ReconciledProfileExportPayload(
                operation_id=operation.operation_id,
                destination=operation.destination,
                purpose=operation.purpose,
            )
            for operation in outcome.reconciled
        ],
        failed=[
            UnreconciledProfileExportPayload(
                journal_id=failure.journal_id,
                destination=failure.destination,
                reason=failure.reason,
            )
            for failure in outcome.failures
        ],
    )
    notices = _reconcile_notices(outcome)
    emit_envelope(
        ctx,
        command="config.profile.archive.reconcile",
        result=result,
        lines=(
            f"reconciled\t{result.reconciled_count}",
            f"failed\t{result.failed_count}",
            *(f"cleared\t{row.destination}" for row in result.reconciled),
            *(f"kept\t{row.journal_id}\t{row.reason}" for row in result.failed),
            *(f"{notice.severity.value.upper()}\t{notice.message}" for notice in notices),
        ),
        notices=notices,
    )


def _reconcile_notices(outcome: ProfileBundleExportReconciliation) -> tuple[Notice, ...]:
    """Build the typed notices describing one reconciliation sweep.

    A clean sweep that found nothing still says so: silence would leave the
    operator unable to tell "nothing to recover" from "the verb did not run".
    An isolated failure is a WARNING rather than a refusal, because the rest of
    the sweep did succeed and the failed operation keeps its journal for the
    next attempt -- but it is surfaced loudly, since a journal left behind may
    still describe cleartext bundle bytes on disk.
    """
    notices: list[Notice] = []
    if not outcome.reconciled and not outcome.failures:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.profile.archive.reconcile.nothing_to_reconcile",
                message=tr("cli.config.profile.archive.reconcile_none_info"),
            ),
        )
    if outcome.reconciled:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="config.profile.archive.reconcile.cleared",
                message=tr(
                    "cli.config.profile.archive.reconcile_cleared_info",
                    count=str(len(outcome.reconciled)),
                ),
                context={"reconciled_count": str(len(outcome.reconciled))},
            ),
        )
    if outcome.failures:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="config.profile.archive.reconcile.failures",
                message=tr(
                    "cli.config.profile.archive.reconcile_failures_warning",
                    count=str(len(outcome.failures)),
                ),
                action=resolve_notice_action(action=ActionReference(action_id="operator.profile.archive.reconcile")),
                context={
                    "failed_count": str(len(outcome.failures)),
                    "journal_ids": ",".join(failure.journal_id for failure in outcome.failures),
                },
            ),
        )
    return tuple(notices)


__all__ = ["profile_archive_reconcile"]
