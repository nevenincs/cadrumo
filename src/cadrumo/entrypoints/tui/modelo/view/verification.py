"""The ``modelo.workspace.verification`` read destination.

Shows the canonical verification findings, the readiness axes, and the
verification capability's own disposition. It derives NO second readiness
verdict: ``ProjectionModeloReadiness.ready`` is the answer, produced by the
one canonical readiness producer and passed through unmodified, and this
screen renders the axes beside it rather than recomputing agreement between
them. A screen that recombined the axes could disagree with ``ready`` and
would then be asserting a verdict no producer reached.

Every value leads with the operator's words: the disposition, each
finding's severity, kind and message, and the readiness answers are named
rather than shown as transport tokens or ``True``/``False``. The producer
attribution and each finding's legal references stay reachable in a
collapsed technical-details group.

Evidence and the recovery action are shown as what the verification
capability actually carries: the registry references the revision cited for
this capability's own schema family, and the catalogued next step the
producer attached. When the capability carries neither, the screen says so in
one sentence rather than rendering two empty columns -- an empty column reads
as "there is no evidence", and the honest claim is "this capability cites
none".

Only the VERIFICATION_READINESS capability is shown here. The complete
denominator belongs to the overview destination; repeating it would put the
same closed set at two addresses, and the row that matters on this screen is
the one naming this screen's own subject.
"""

from __future__ import annotations

from typing import ClassVar, override

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from .....application.modelo.workspace_models import (
    ModeloWorkspaceCapabilityDisposition,
    ModeloWorkspaceCapabilityName,
    ModeloWorkspaceCapabilityV1,
)
from .....core.i18n.render import tr
from ...components.account_chrome import AccountChromeScreen
from ...components.theme import toggle_appearance
from ...components.widgets import ContentDataTable, ContentScroll, DisclosureGroup
from .controller import ModeloWorkspaceReadSession
from .models import (
    capability_row,
    disposition_label,
    evidence_reference_label,
    finding_kind_label,
    finding_message,
    finding_severity_label,
    recovery_action_label,
)
from .technical_details import TechnicalDetailRowV1, mount_technical_details, producer_row

_FINDING_COLUMN_KEYS: tuple[str, ...] = ("severity", "kind", "casilla", "message")
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
        "profile_ready": _yes_no(readiness.profile_ready),
        "registry_ready": _yes_no(readiness.registry_ready),
        "binding_ready": _yes_no(readiness.binding_ready),
        "ledger_ready": unmeasured if readiness.ledger_ready is None else _yes_no(readiness.ledger_ready),
        "ready": _yes_no(readiness.ready),
    }


def _yes_no(answer: bool) -> str:
    """Say a readiness answer in words rather than as ``True`` or ``False``."""
    return tr("tui.declarations.value.yes" if answer else "tui.declarations.value.no")


class ModeloWorkspaceVerificationScreen(AccountChromeScreen):
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
            yield Static(id="workspace-verification-evidence")

    def on_mount(self) -> None:
        """Populate the header, the capability line, and each axis or its disposition."""
        self.query_one("#workspace-verification-header", Static).update(
            tr("flows.modelo_workspace_verification.title", modelo=self._session.projection.target.modelo)
        )
        self._mount_capability()
        self._mount_findings()
        self._mount_readiness()
        self._mount_evidence()
        self._mount_technical_details()

    def _mount_capability(self) -> None:
        """Show the verification capability's own producer-declared disposition."""
        row = capability_row(self._verification_capability())
        self.query_one("#workspace-verification-capability", Static).update(
            tr("flows.modelo_workspace_verification.capability_line", disposition=disposition_label(row.disposition))
        )

    def _mount_evidence(self) -> None:
        """Show this capability's cited evidence and its catalogued next step.

        Both come from the capability row itself; neither is derived here. A
        capability citing no reference and naming no addressable step gets one
        sentence saying exactly that, which is a narrower claim than "there is
        no evidence for this verification".
        """
        capability = self._verification_capability()
        parts: list[str] = [evidence_reference_label(reference) for reference in capability.evidence]
        if capability.recovery_action is not None:
            parts.append(recovery_action_label(capability.recovery_action))
        notice = self.query_one("#workspace-verification-evidence", Static)
        if not parts:
            notice.update(tr("flows.modelo_workspace_verification.evidence_none"))
            return
        notice.update(tr("flows.modelo_workspace_verification.evidence_carried", entries="; ".join(parts)))

    def _verification_capability(self) -> ModeloWorkspaceCapabilityV1:
        """Return the one capability row this destination is about."""
        return next(
            capability
            for capability in self._session.projection.capabilities
            if capability.capability is ModeloWorkspaceCapabilityName.VERIFICATION_READINESS
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
        table = ContentDataTable[str](id="workspace-verification-findings-table", cursor_type="row", zebra_stripes=True)
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_verification.section.findings"), collapsed=False)
        )
        for column_key in _FINDING_COLUMN_KEYS:
            table.add_column(tr(f"flows.modelo_workspace_verification.column.{column_key}"), key=column_key)
        for index, finding in enumerate(facet.review.findings):
            table.add_row(
                finding_severity_label(finding.severity),
                finding_kind_label(finding.kind),
                "" if finding.casilla_id is None else str(finding.casilla_id),
                finding_message(finding),
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
        table = ContentDataTable[str](
            id="workspace-verification-readiness-table", cursor_type="row", zebra_stripes=True
        )
        body.mount(
            DisclosureGroup(table, title=tr("flows.modelo_workspace_verification.section.readiness"), collapsed=False)
        )
        table.add_column(tr("flows.modelo_workspace_verification.column.axis"), key="axis")
        table.add_column(tr("flows.modelo_workspace_verification.column.value"), key="value")
        for row_key in _READINESS_ROW_KEYS:
            table.add_row(tr(f"flows.modelo_workspace_verification.axis.{row_key}"), values[row_key], key=row_key)

    def _mount_technical_details(self) -> None:
        """Keep the producer and each finding's legal grounding, collapsed."""
        rows: list[TechnicalDetailRowV1] = [producer_row(capability_row(self._verification_capability()))]
        review = self._session.projection.work_review.review
        for index, finding in enumerate(() if review is None else review.findings):
            rows.append(
                (
                    f"finding.{index}",
                    tr("tui.modelo.technical.finding_refs", position=index + 1),
                    ", ".join((*finding.legal_refs, *finding.source_refs)),
                )
            )
        mount_technical_details(
            self.query_one("#workspace-verification-body", ContentScroll),
            rows,
            id="workspace-verification-technical-table",
        )

    def action_quit_verification(self) -> None:
        """Leave the destination without returning a value; this screen decides nothing."""
        self.dismiss(None)

    def action_toggle_appearance(self) -> None:
        """Switch between the two shipped appearances."""
        toggle_appearance(self.app)


__all__ = ["ModeloWorkspaceVerificationScreen"]
