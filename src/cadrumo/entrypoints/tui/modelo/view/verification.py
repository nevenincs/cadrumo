"""The ``modelo.workspace.verification`` read destination.

Shows the canonical verification findings, the readiness axes, and the
verification capability's own disposition. It derives NO second readiness
verdict: ``ModeloWorkspaceReadinessV1.ready`` is the answer, produced by the
one canonical readiness producer and passed through unmodified, and this
screen renders the axes beside it rather than recomputing agreement between
them. A screen that recombined the axes could disagree with ``ready`` and
would then be asserting a verdict no producer reached.

Evidence and recovery actions are STATED AS NOT CARRIED rather than shown as
empty columns. ``ModeloWorkspaceCapabilityV1`` and the refusal types declare
``evidence``, ``facts`` and ``recovery_action``, and no producer populates
them on those types -- while the surrounding application layer attaches
``ActionReference`` to comparable verdicts routinely. So the emptiness is an
upstream omission, not a finding that no evidence exists, and two empty
columns would quietly convert the first into the second.

Only the VERIFICATION_READINESS capability is shown here. The complete
denominator belongs to the overview destination; repeating it would put the
same closed set at two addresses, and the row that matters on this screen is
the one naming this screen's own subject.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
)
from .....core.i18n import tr
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from .controller import ModeloWorkspaceReadSession
from .models import capability_row

_FINDING_COLUMN_KEYS: tuple[str, ...] = ("severity", "kind", "casilla")
_READINESS_ROW_KEYS: tuple[str, ...] = (
    "profile_ready",
    "registry_ready",
    "binding_ready",
    "ledger_ready",
    "ready",
)


def _readiness_values(session: ModeloWorkspaceReadSession) -> dict[str, str] | None:
    """Return the readiness axes as displayed strings, or ``None`` when unmeasured.

    ``ready`` is copied, never recomputed from the other four. It is the
    canonical producer's verdict; deriving it here could disagree with the
    value the projection carries.
    """
    readiness = session.projection.readiness
    if readiness is None:
        return None
    unmeasured = tr("flows.modelo_workspace_verification.value.unmeasured")
    return {
        "profile_ready": str(readiness.profile_ready),
        "registry_ready": str(readiness.registry_ready),
        "binding_ready": str(readiness.binding_ready),
        "ledger_ready": unmeasured if readiness.ledger_ready is None else str(readiness.ledger_ready),
        "ready": str(readiness.ready),
    }


class ModeloWorkspaceVerificationScreen(Screen[None]):
    """Findings, readiness axes, and this screen's own capability disposition."""

    BINDINGS: ClassVar = [
        Binding("q", "quit_verification", ""),
        Binding("escape", "quit_verification", ""),
        Binding("f3", "toggle_appearance", "", show=False),
    ]

    def __init__(self, session: ModeloWorkspaceReadSession, *, id: str | None = None) -> None:
        """Store the already-admitted session this destination renders."""
        super().__init__(id=id)
        self._session = session

    @override
    def compose(self) -> ComposeResult:
        yield Static(id="workspace-verification-header", classes="cadrumo-banner")
        with ContentScroll(id="workspace-verification-body", classes="cadrumo-scroll"):
            yield Static(id="workspace-verification-capability")
            yield Static(id="workspace-verification-findings-disposition")
            yield Static(id="workspace-verification-readiness-disposition")
            yield Static(id="workspace-verification-evidence-not-carried")

    def on_mount(self) -> None:
        """Populate the header, the capability line, and each axis or its disposition."""
        self.query_one("#workspace-verification-header", Static).update(
            tr("flows.modelo_workspace_verification.title", modelo=self._session.projection.target.modelo)
        )
        self._mount_capability()
        self._mount_findings()
        self._mount_readiness()
        self.query_one("#workspace-verification-evidence-not-carried", Static).update(
            tr("flows.modelo_workspace_verification.evidence_not_carried")
        )

    def _mount_capability(self) -> None:
        """Show the verification capability's own producer-declared disposition."""
        capability = next(
            capability
            for capability in self._session.projection.capabilities
            if capability.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
        )
        row = capability_row(capability)
        self.query_one("#workspace-verification-capability", Static).update(
            tr(
                "flows.modelo_workspace_verification.capability_line",
                glyph=row.glyph,
                disposition=row.disposition.value,
                producer=f"{row.producer_owner}.{row.producer}",
            )
        )

    def _mount_findings(self) -> None:
        """Mount the canonical findings, or state that none were measured.

        The findings come from the work-review facet through its own
        disposition. An unavailable facet means nobody looked, which is
        different from having looked and found nothing -- so the two cases
        get different text rather than one empty table.
        """
        facet = self._session.projection.work_review
        disposition = self.query_one("#workspace-verification-findings-disposition", Static)
        if facet.disposition is not ModeloWorkspaceCapabilityDisposition.AVAILABLE or facet.review is None:
            disposition.update(tr("flows.modelo_workspace_verification.findings_unmeasured"))
            return
        if not facet.review.findings:
            disposition.update(tr("flows.modelo_workspace_verification.findings_none"))
            return
        disposition.remove()
        body = self.query_one("#workspace-verification-body", ContentScroll)
        table = ContentDataTable(id="workspace-verification-findings-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_verification.section.findings"), collapsed=False)
        )
        for column_key in _FINDING_COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_verification.column.{column_key}"), key=column_key)
        for index, finding in enumerate(facet.review.findings):
            table.add_row(
                finding.severity.value,
                finding.kind.value,
                "" if finding.casilla_id is None else str(finding.casilla_id),
                key=str(index),
            )

    def _mount_readiness(self) -> None:
        """Mount the readiness axes beside the producer's verdict, or state absence."""
        values = _readiness_values(self._session)
        disposition = self.query_one("#workspace-verification-readiness-disposition", Static)
        if values is None:
            disposition.update(tr("flows.modelo_workspace_verification.readiness_unmeasured"))
            return
        disposition.remove()
        body = self.query_one("#workspace-verification-body", ContentScroll)
        table = ContentDataTable(id="workspace-verification-readiness-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_verification.section.readiness"), collapsed=False)
        )
        table.add_column(tr("flows.modelo_workspace_verification.column.axis"), key="axis")
        table.add_column(tr("flows.modelo_workspace_verification.column.value"), key="value")
        for row_key in _READINESS_ROW_KEYS:
            table.add_row(tr(f"flows.modelo_workspace_verification.axis.{row_key}"), values[row_key], key=row_key)

    def action_quit_verification(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.app.exit(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceVerificationScreen"]
