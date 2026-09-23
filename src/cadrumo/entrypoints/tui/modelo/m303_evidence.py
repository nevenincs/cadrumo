"""Explicit ordinary-M303 filing-evidence entry for the Modelo workspace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, override

from pydantic import ValidationError
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from ....application.modelo.operation_definitions import ModeloWorkCalculateOrdinaryM303EvidenceRequestV1
from ....core.i18n.render import tr
from ..components.theme import tokenised

_M303_EVIDENCE_CSS = tokenised("""
OrdinaryM303FilingEvidenceScreen { align: center middle; }
#m303-evidence-dialog {
    border: $cadrumo-radius-overlay $primary;
    background: $surface;
    padding: $cadrumo-space-1 $cadrumo-gutter;
    width: 100%;
    height: auto;
}
#m303-evidence-title { text-style: bold; margin-bottom: $cadrumo-stack; }
#m303-evidence-hint { color: $text-muted; margin-bottom: $cadrumo-stack; }
.m303-evidence-label { margin-top: $cadrumo-tight; }
#m303-evidence-notice { color: $error; height: auto; margin-top: $cadrumo-tight; }
#m303-evidence-actions { height: auto; align-horizontal: right; margin-top: $cadrumo-stack; }
#m303-evidence-actions Button { margin-left: $cadrumo-control-gap; }
""")


@dataclass(frozen=True, slots=True)
class OrdinaryM303FilingEvidenceSubmission:
    """One explicitly completed evidence form, bound to its selected work unit."""

    work_unit_id: str
    joint_return_elected: bool
    annual_volume_nonzero: bool
    existing_evidence: ModeloWorkCalculateOrdinaryM303EvidenceRequestV1 | None = None
    observed_at: datetime | None = None


class OrdinaryM303FilingEvidenceScreen(ModalScreen[OrdinaryM303FilingEvidenceSubmission | None]):
    """Collect the four operator-supplied values before the existing calculation action."""

    DEFAULT_CSS = _M303_EVIDENCE_CSS
    BINDINGS: ClassVar = [Binding("escape", "cancel", "", show=False)]

    def __init__(self, *, work_unit_id: str) -> None:
        """Bind the form to the work unit selected when Calculate was invoked."""
        super().__init__()
        self._work_unit_id = work_unit_id

    @override
    def compose(self) -> ComposeResult:
        with Vertical(id="m303-evidence-dialog"):
            yield Static(tr("tui.modelo.m303_evidence.title"), id="m303-evidence-title", markup=False)
            yield Static(
                tr("tui.modelo.m303_evidence.existing_attestation_hint"), id="m303-evidence-hint", markup=False
            )
            yield Static(
                tr("tui.modelo.m303_evidence.joint_return_elected"), classes="m303-evidence-label", markup=False
            )
            yield Select[str](_yes_no_options(), id="m303-evidence-joint-return-elected")
            yield Static(
                tr("tui.modelo.m303_evidence.annual_volume_nonzero"), classes="m303-evidence-label", markup=False
            )
            yield Select[str](_yes_no_options(), id="m303-evidence-annual-volume-nonzero")
            yield Static(
                tr("tui.modelo.m303_evidence.attestation_attachment_id"), classes="m303-evidence-label", markup=False
            )
            yield Input(id="m303-evidence-attachment-id")
            yield Static(tr("tui.modelo.m303_evidence.attestation_sha256"), classes="m303-evidence-label", markup=False)
            yield Input(id="m303-evidence-sha256")
            yield Static(tr("tui.modelo.m303_evidence.observed_at"), classes="m303-evidence-label", markup=False)
            yield Input(id="m303-evidence-observed-at")
            yield Static(id="m303-evidence-notice", markup=False)
            with Horizontal(id="m303-evidence-actions"):
                yield Button(tr("tui.modelo.m303_evidence.cancel"), id="m303-evidence-cancel")
                yield Button(
                    tr("application.modelo.lifecycle.calculate"), id="m303-evidence-submit", classes="-primary"
                )

    def on_mount(self) -> None:
        """Focus the first declaration, which deliberately starts unselected."""
        self.query_one("#m303-evidence-joint-return-elected", Select).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Cancel without a request, or dismiss with one strictly validated typed form."""
        if event.button.id == "m303-evidence-cancel":
            self.dismiss(None)
            return
        if event.button.id != "m303-evidence-submit":
            return
        submission = self._submission()
        if submission is None:
            self.query_one("#m303-evidence-notice", Static).update(tr("tui.modelo.m303_evidence.required"))
            return
        self.dismiss(submission)

    def action_cancel(self) -> None:
        """Treat Escape as cancellation rather than an implicit filing-fact choice."""
        self.dismiss(None)

    def _submission(self) -> OrdinaryM303FilingEvidenceSubmission | None:
        """Build a request only when both declarations and both secure coordinates are explicit."""
        joint_return_elected = _selected_boolean(self.query_one("#m303-evidence-joint-return-elected", Select))
        annual_volume_nonzero = _selected_boolean(self.query_one("#m303-evidence-annual-volume-nonzero", Select))
        attachment_id = self.query_one("#m303-evidence-attachment-id", Input).value.strip()
        sha256 = self.query_one("#m303-evidence-sha256", Input).value.strip()
        observed_at = self.query_one("#m303-evidence-observed-at", Input).value.strip()
        if joint_return_elected is None or annual_volume_nonzero is None:
            return None
        has_existing_coordinates = bool(attachment_id) and bool(sha256)
        if bool(attachment_id) != bool(sha256) or (has_existing_coordinates and observed_at):
            return None
        try:
            existing_evidence = (
                ModeloWorkCalculateOrdinaryM303EvidenceRequestV1(
                    joint_return_elected=joint_return_elected,
                    annual_volume_nonzero=annual_volume_nonzero,
                    m303_exonerado_390_attachment_id=attachment_id,
                    m303_exonerado_390_sha256=sha256,
                )
                if has_existing_coordinates
                else None
            )
            parsed_observed_at = None if has_existing_coordinates else _parse_observed_at(observed_at)
        except (ValidationError, ValueError):
            return None
        if existing_evidence is None and parsed_observed_at is None:
            return None
        return OrdinaryM303FilingEvidenceSubmission(
            work_unit_id=self._work_unit_id,
            joint_return_elected=joint_return_elected,
            annual_volume_nonzero=annual_volume_nonzero,
            existing_evidence=existing_evidence,
            observed_at=parsed_observed_at,
        )


def _yes_no_options() -> tuple[tuple[str, str], ...]:
    """Render the two explicit answers in the active locale; no option means unanswered."""
    return ((tr("flows.confirm.yes"), "true"), (tr("flows.confirm.no"), "false"))


def _selected_boolean(select: Select[str]) -> bool | None:
    """Convert only a deliberate yes/no selection; blank remains missing, never false."""
    value = select.value
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _parse_observed_at(value: str) -> datetime:
    """Parse the operator's explicit ISO-8601 instant; a local time without an offset is ambiguous."""
    if not value:
        raise ValueError("an attestation observation instant is required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("an attestation observation instant requires a UTC offset")
    return parsed


__all__ = ["OrdinaryM303FilingEvidenceScreen", "OrdinaryM303FilingEvidenceSubmission"]
