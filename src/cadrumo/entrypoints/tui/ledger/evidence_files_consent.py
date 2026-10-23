"""Consent history: which documents were sent off this machine to be read, and when.

A read-only view of the consent survey: every recorded dispatch, every draft a
hosted reader produced, and the survey's own statement that sent bytes cannot
be recalled. Nothing here grants, withdraws or changes a consent.
"""

from __future__ import annotations

from collections import Counter
from typing import cast, override

from textual.app import ComposeResult
from textual.widgets import Button, DataTable, Static

from ....application.ledger.evidence_followup_contracts import (
    CloudDerivedArtefactProjection,
    ConsentedDispatchProjection,
    LedgerEvidenceConsentListRequest,
)
from ....core.i18n.render import tr
from ..components.language import localized, repaint_tables
from ..components.widgets import ContentDataTable
from .controller import LedgerWorkspaceController
from .evidence_files_common import (
    EvidenceFilesPager,
    EvidenceFilesToolScreen,
    paging_controls,
    paint_paging,
    short_identity,
    shown,
)
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .workspace_presentation import ledger_workspace_page


def _unique_keys(keys: list[str]) -> list[str]:
    """Keep two identical history rows apart without reordering them."""
    seen: Counter[str] = Counter()
    unique: list[str] = []
    for key in keys:
        seen[key] += 1
        unique.append(key if seen[key] == 1 else f"{key}#{seen[key]}")
    return unique


def dispatch_key(row: ConsentedDispatchProjection) -> str:
    """The identity of one recorded dispatch: what was sent, when, and to which reader."""
    return "|".join((row.evidence_content_address, row.recorded_at.isoformat(), row.provider, row.model, row.surface))


def artefact_key(row: CloudDerivedArtefactProjection) -> str:
    """The identity of one hosted-reader draft: its evidence and when it was drafted."""
    return "|".join((row.evidence_reference, row.drafted_at.isoformat(), row.provenance_stamp))


class LedgerEvidenceFilesConsentScreen(EvidenceFilesToolScreen):
    """Read-only consent history: dispatches and hosted-reader drafts, one page at a time each."""

    def __init__(self, controller: LedgerWorkspaceController, doors: LedgerEvidenceFilesDoorsV1) -> None:
        """Open over the injected doors."""
        super().__init__(controller, doors, id="ledger-evidence-files-consent-screen")
        self.dispatches: EvidenceFilesPager[ConsentedDispatchProjection] = EvidenceFilesPager()
        self.artefacts: EvidenceFilesPager[CloudDerivedArtefactProjection] = EvidenceFilesPager()
        self.read_once = False

    @override
    def compose(self) -> ComposeResult:
        yield self.banner(tr("tui.ledger.evidence_files.consent.title"), "tui.ledger.evidence_files.consent.title")
        with ledger_workspace_page() as navigation:
            yield navigation
            yield localized(
                Static(tr("tui.ledger.evidence_files.consent.prompt"), markup=False),
                "tui.ledger.evidence_files.consent.prompt",
            )
            yield Static("", id="ledger-flow-status", markup=False)
            yield Static("", id="ledger-refusal", classes="ledger-refusal", markup=False)
            yield localized(
                Static(tr("tui.ledger.evidence_files.consent.dispatches"), classes="cadrumo-heading", markup=False),
                "tui.ledger.evidence_files.consent.dispatches",
            )
            yield ContentDataTable[str](id="evidence-files-dispatches", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-dispatches")
            yield localized(
                Static(tr("tui.ledger.evidence_files.consent.artefacts"), classes="cadrumo-heading", markup=False),
                "tui.ledger.evidence_files.consent.artefacts",
            )
            yield ContentDataTable[str](id="evidence-files-artefacts", cursor_type="row", zebra_stripes=True)
            yield from paging_controls("evidence-files-artefacts")
            yield Static("", id="evidence-files-consent-statement", classes="evidence-files-detail", markup=False)

    def on_mount(self) -> None:
        """Show the shell, then read the survey off the event loop."""
        self._paint()
        self.start(self._load)

    @override
    async def refresh_language(self) -> None:
        await super().refresh_language()
        repaint_tables(self, self._paint)

    def _paint(self) -> None:
        self.populate_navigation()
        self._paint_dispatches()
        self._paint_artefacts()
        self._paint_statement()

    def _paint_dispatches(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-dispatches", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence_files.column.recorded"), key="recorded")
        table.add_column(tr("tui.ledger.evidence_files.column.document"), key="document")
        table.add_column(tr("tui.ledger.evidence_files.column.provider"), key="provider")
        table.add_column(tr("tui.ledger.evidence_files.column.model"), key="model")
        table.add_column(tr("tui.ledger.evidence_files.column.surface"), key="surface")
        page = self.dispatches.page()
        for row, key in zip(page, _unique_keys([dispatch_key(row) for row in page]), strict=True):
            table.add_row(
                row.recorded_at.strftime("%Y-%m-%d %H:%M"),
                short_identity(row.evidence_content_address),
                row.provider,
                row.model,
                row.surface,
                key=key,
            )
        paint_paging(self, "evidence-files-dispatches", self.dispatches)

    def _paint_artefacts(self) -> None:
        table = cast("DataTable[str]", self.query_one("#evidence-files-artefacts", DataTable))
        table.clear(columns=True)
        table.add_column(tr("tui.ledger.evidence_files.column.drafted"), key="drafted")
        table.add_column(tr("tui.ledger.evidence_files.column.record"), key="record")
        table.add_column(tr("tui.ledger.evidence_files.column.stamp"), key="stamp")
        table.add_column(tr("tui.ledger.evidence_files.column.transport"), key="transport")
        page = self.artefacts.page()
        for row, key in zip(page, _unique_keys([artefact_key(row) for row in page]), strict=True):
            table.add_row(
                row.drafted_at.strftime("%Y-%m-%d %H:%M"),
                short_identity(row.evidence_reference),
                row.provenance_stamp,
                shown(row.transport),
                key=key,
            )
        paint_paging(self, "evidence-files-artefacts", self.artefacts)

    def _paint_statement(self) -> None:
        statement = self.query_one("#evidence-files-consent-statement", Static)
        if not self.read_once:
            statement.update("")
            return
        lines = []
        if not self.dispatches.items:
            lines.append(tr("tui.ledger.evidence_files.consent.no_dispatches"))
        if not self.artefacts.items:
            lines.append(tr("tui.ledger.evidence_files.consent.no_artefacts"))
        lines.append(tr("tui.ledger.evidence_files.consent.unrecallable"))
        statement.update("\n".join(lines))

    async def _load(self) -> None:
        self.status(tr("tui.ledger.evidence_files.loading"))
        result = await self.ask(
            self.doors.consent_list(LedgerEvidenceConsentListRequest(profile_id=self.doors.profile_id))
        )
        if result is None:
            return
        self.read_once = True
        self.dispatches.load(result.survey.consented_dispatches)
        self.artefacts.load(result.survey.cloud_derived_artefacts)
        self._paint_dispatches()
        self._paint_artefacts()
        self._paint_statement()
        self.status("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Page either history table."""
        match event.button.id:
            case "evidence-files-dispatches-previous":
                self.dispatches.previous()
                self._paint_dispatches()
            case "evidence-files-dispatches-next":
                self.dispatches.next()
                self._paint_dispatches()
            case "evidence-files-artefacts-previous":
                self.artefacts.previous()
                self._paint_artefacts()
            case "evidence-files-artefacts-next":
                self.artefacts.next()
                self._paint_artefacts()
            case _:
                return

    @override
    def clear_private_view(self) -> None:
        self.read_once = False
        self.dispatches.clear()
        self.artefacts.clear()
        self._paint_dispatches()
        self._paint_artefacts()
        self._paint_statement()


__all__ = ["LedgerEvidenceFilesConsentScreen", "artefact_key", "dispatch_key"]
