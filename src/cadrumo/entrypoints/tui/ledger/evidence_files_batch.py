"""Add documents in bulk: every document directly inside one folder, read on this machine.

The operator types the folder and the direction every document is filed under.
The batch is reviewed before it runs, and its outcome lists each document as
the operation reported it; a batch that stored only part of its documents says
so. Only each document's own name is shown.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, cast, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Select, Static

from ....application.ledger.batch_ingest import BatchItemStatus
from ....application.ledger.evidence_ingestion_contracts import (
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ....application.operations.host_path_name import host_path_file_name
from ....core.i18n.render import tr
from ....core.operations import OperationEffect
from ....domain.iva.schema import InvoiceKind
from ..components.language import localized
from ..components.workspace_host import replace_workspace_body
from ..setup.offer import setup_item_for_action
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .evidence_files_common import EvidenceFilesToolScreen, blank_to_none, shown
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .evidence_files_write import (
    EvidenceFilesOutcomeRowV1,
    EvidenceFilesOutcomeV1,
    EvidenceFilesWordingV1,
    LedgerEvidenceFilesWriteScreen,
)
from .workspace_presentation import door_refusal_text, ledger_workspace_page

_KIND_LOCALE_KEYS: Final[dict[InvoiceKind, str]] = {
    InvoiceKind.RECEIVED: "tui.ledger.invoice.kind.received",
    InvoiceKind.ISSUED: "tui.ledger.invoice.kind.issued",
}
_STATUSES: Final[tuple[BatchItemStatus, ...]] = ("ingested", "no_op", "pending_review", "paused", "refused")
_STATUS_LOCALE_KEYS: Final[dict[BatchItemStatus, str]] = {
    "ingested": "tui.ledger.evidence_files.batch.status.ingested",
    "no_op": "tui.ledger.evidence_files.batch.status.no_op",
    "pending_review": "tui.ledger.evidence_files.batch.status.pending_review",
    "paused": "tui.ledger.evidence_files.batch.status.paused",
    "refused": "tui.ledger.evidence_files.batch.status.refused",
}


def _status_label(status: BatchItemStatus) -> str:
    return tr(_STATUS_LOCALE_KEYS[status])


def batch_outcome(projection: LedgerEvidenceBatchProjection) -> EvidenceFilesOutcomeV1:
    """Word a settled batch: one row per document, counts per outcome, and whether it was partial."""
    run = projection.run
    counts = {status: sum(1 for item in run.items if item.status == status) for status in _STATUSES}
    lines = [
        tr(
            "tui.ledger.evidence_files.batch.outcome.counts",
            ingested=counts["ingested"],
            no_op=counts["no_op"],
            pending=counts["pending_review"],
            paused=counts["paused"],
            refused=counts["refused"],
            unreadable=len(run.unresolved),
        ),
        tr("tui.ledger.evidence_files.batch.outcome.writes", count=projection.write_count),
    ]
    pause = run.inference_pause
    setup_item = None if pause is None else setup_item_for_action(pause.precondition_verdict.action_id)
    if pause is not None:
        # The pause names the local AI's setup when setting it up would let the paused documents be read.
        lines.append(
            tr("tui.ledger.evidence_files.batch.outcome.paused_local_ai_not_ready")
            if setup_item is not None
            else tr("tui.ledger.evidence_files.batch.outcome.paused")
        )
    if projection.effect is OperationEffect.PARTIAL:
        lines.append(tr("tui.ledger.evidence_files.batch.outcome.partial"))
    rows: list[EvidenceFilesOutcomeRowV1] = [
        (item.identity, (shown(item.source_name), _status_label(item.status), shown(item.refusal_code)))
        for item in run.items
    ]
    rows.extend(
        (
            f"unresolved:{index}",
            (
                shown(host_path_file_name(row.source_name)),
                tr("tui.ledger.evidence_files.batch.status.unreadable"),
                row.refusal_code,
            ),
        )
        for index, row in enumerate(run.unresolved)
    )
    return EvidenceFilesOutcomeV1(
        lines=tuple(lines),
        partial=projection.effect is OperationEffect.PARTIAL,
        columns=(
            tr("tui.ledger.evidence_files.column.document"),
            tr("tui.ledger.evidence_files.column.outcome"),
            tr("tui.ledger.evidence_files.column.reason"),
        ),
        rows=tuple(rows),
        setup_item=setup_item,
    )


class LedgerEvidenceFilesBatchScreen(EvidenceFilesToolScreen):
    """Stage a bulk intake of one folder's documents under one direction."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEvidenceFilesDoorsV1) -> None:
        """Open over the injected doors."""
        super().__init__(controller, doors, id="ledger-evidence-files-batch-screen")

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(tr("tui.ledger.evidence_files.batch.title"), "tui.ledger.evidence_files.batch.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.batch.prompt"), markup=False),
                "tui.ledger.evidence_files.batch.prompt",
            )
            yield localized(
                Static(tr("tui.ledger.evidence_files.batch.directory"), markup=False),
                "tui.ledger.evidence_files.batch.directory",
            )
            yield localized(
                Input(
                    placeholder=tr("tui.ledger.evidence_files.batch.directory_placeholder"),
                    id="evidence-files-batch-directory",
                ),
                "tui.ledger.evidence_files.batch.directory_placeholder",
            )
            yield localized(
                Static(tr("tui.ledger.evidence_files.batch.direction"), markup=False),
                "tui.ledger.evidence_files.batch.direction",
            )
            yield Select[str](
                tuple((tr(_KIND_LOCALE_KEYS[kind]), kind.value) for kind in InvoiceKind),
                value=InvoiceKind.RECEIVED.value,
                allow_blank=False,
                id="evidence-files-batch-direction",
            )
            with Horizontal(classes="evidence-files-actions"):
                yield localized(
                    Button(
                        tr("tui.ledger.evidence_files.batch.review"),
                        id="evidence-files-batch-review",
                        variant="primary",
                    ),
                    "tui.ledger.evidence_files.batch.review",
                )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)

    def on_mount(self) -> None:
        """Show the shell with the folder field ready for typing."""
        self.populate_navigation()
        self.query_one("#evidence-files-batch-directory", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Stage the typed folder and direction for review."""
        if event.button.id == "evidence-files-batch-review":
            self._stage()

    def _stage(self) -> None:
        directory = blank_to_none(self.query_one("#evidence-files-batch-directory", Input).value)
        if directory is None:
            self.refuse(tr("tui.ledger.evidence_files.batch.directory_required"))
            return
        direction = InvoiceKind(
            str(cast("Select[str]", self.query_one("#evidence-files-batch-direction", Select)).value)
        )
        try:
            request = LedgerEvidenceBatchRequest(
                profile_id=self.doors.profile_id,
                sources=(directory,),
                source_directory=directory,
                direction=direction,
            )
        except ValidationError as error:
            self.refuse(door_refusal_text(error))
            return

        def review() -> tuple[str, ...]:
            return (
                tr(
                    "tui.ledger.evidence_files.batch.stage",
                    directory=directory,
                    direction=tr(_KIND_LOCALE_KEYS[direction]),
                ),
                tr("tui.ledger.evidence_files.batch.stage_local"),
            )

        doors = self.doors

        async def submit() -> EvidenceFilesWordingV1:
            projection = await doors.batch(request)
            return lambda: batch_outcome(projection)

        replace_workspace_body(
            self.app,
            LedgerEvidenceFilesWriteScreen(
                self.controller,
                title=lambda: tr("tui.ledger.evidence_files.batch.title"),
                review=review,
                destructive=False,
                submit=submit,
                origin=self._origin(),
                origin_area=self.back_area,
            ),
        )

    def _origin(self) -> Callable[[LedgerWorkspaceController], LedgerWorkspaceScreen]:
        doors = self.doors

        def build(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
            return LedgerEvidenceFilesBatchScreen(controller, doors)

        return build

    @override
    def clear_private_view(self) -> None:
        self.query_one("#evidence-files-batch-directory", Input).value = ""


__all__ = ["LedgerEvidenceFilesBatchScreen", "batch_outcome"]
