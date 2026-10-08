"""Typed value-free installed income-tax TUI and continuation evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal, Protocol

from .scenario import AcceptanceOutcome

if TYPE_CHECKING:
    pass


type TerminalCondition = Literal["succeeded", "succeeded_partial", "refused", "failed", "cancelled", "not_completed"]


class TuiJourneyError(RuntimeError):
    """Raised when an acceptance receipt cannot identify a valid run coordinate."""


class _TuiScreen(Protocol):
    """The public Textual screen operation used by the installed adapter."""

    def query_one(self, selector: str) -> object: ...


@dataclass(frozen=True, slots=True)
class TuiOperationBinding:
    """One installed-TUI operation and the controls needed to prove it.

    ``operation_id`` names the shared registered application operation.  The
    remaining values are deliberately absent until the installed composition
    supplies stable controls; an operation definition alone cannot prove that
    a TUI user can activate it, confirm it, or observe its terminal result.

    An operation starts either from a workbench key (``activation_key``) or
    from a button on a dialog the journey has already opened
    (``activation_id``), never both.  A key that runs whatever step the
    workbench offers next names that step in ``offered_step`` (``verify``,
    ``record``), and the driver refuses to press it while the workbench offers
    another one.  ``at_risk_proceed_id`` is pressed only while the
    workbench's pre-recalculation confirmation is the top screen.
    """

    operation_id: str
    activation_key: str | None = None
    activation_id: str | None = None
    offered_step: str | None = None
    at_risk_proceed_id: str | None = None
    confirmation_id: str | None = None
    confirmation_required: bool = False
    terminal_result_id: str | None = None
    refresh_result_id: str | None = None
    refusal_notice_id: str | None = None

    def missing(self, *, label: str) -> tuple[str, ...]:
        """Name required installed controls that are not available yet."""
        values = {
            "activation": self.activation_key or self.activation_id,
            "terminal_result": self.terminal_result_id,
            "refresh_result": self.refresh_result_id,
            "refusal_notice": self.refusal_notice_id,
        }
        missing = [f"{label}.{name}" for name, value in values.items() if value is None]
        if self.confirmation_required and self.confirmation_id is None:
            missing.append(f"{label}.confirmation")
        return tuple(missing)


@dataclass(frozen=True, slots=True)
class InstalledTuiContract:
    """Stable installed controls required by the income journey.

    The contract intentionally captures user-reachable controls rather than
    application services.  It prevents a test from quietly replacing an
    unavailable screen action with a private repository invocation.
    """

    profile_selection_id: str | None = None
    ledger_capture_id: str | None = None
    invoice_link_id: str | None = None
    work_create_id: str | None = None
    work_open_id: str | None = None
    calculate: TuiOperationBinding = TuiOperationBinding("modelo.work.calculate")
    verify: TuiOperationBinding = TuiOperationBinding("modelo.work.verify")
    local_file: TuiOperationBinding = TuiOperationBinding("modelo.work.file")
    export: TuiOperationBinding = TuiOperationBinding("modelo.export")
    apply: TuiOperationBinding = TuiOperationBinding("modelo.edit.apply")

    def missing_controls(self) -> tuple[str, ...]:
        """Return every missing user-facing control in deterministic order."""
        missing = tuple(
            name
            for name, value in (
                ("profile_selection", self.profile_selection_id),
                ("ledger_capture", self.ledger_capture_id),
                ("invoice_link", self.invoice_link_id),
                ("work_create", self.work_create_id),
                ("work_open", self.work_open_id),
            )
            if value is None
        )
        return (
            *missing,
            *self.calculate.missing(label="calculate"),
            *self.verify.missing(label="verify"),
            *self.local_file.missing(label="local_file"),
            *self.export.missing(label="export"),
            *self.apply.missing(label="apply"),
        )


@dataclass(frozen=True, slots=True)
class LifecycleEvidence:
    """Keep local lifecycle outcomes distinct in every frontend receipt."""

    calculation: AcceptanceOutcome
    verification: AcceptanceOutcome
    export_readiness: AcceptanceOutcome
    export_execution: AcceptanceOutcome
    local_filing: AcceptanceOutcome
    submission: AcceptanceOutcome


@dataclass(frozen=True, slots=True)
class TuiTerminalEvidence:
    """One terminal result observed through the public operation modal."""

    operation_id: str
    terminal_condition: TerminalCondition
    outcome: AcceptanceOutcome
    receipt_present: bool
    diagnostic_present: bool


@dataclass(frozen=True, slots=True)
class AcceptanceCaseEvidence:
    """One A1-A10 result with its local lifecycle state preserved."""

    acceptance_id: str
    outcome: AcceptanceOutcome
    lifecycle: LifecycleEvidence
    source_state: str
    diagnostic_code: str | None = None


@dataclass(frozen=True, slots=True)
class LocalXsdValidationEvidence:
    """Sanitized local XSD validation evidence for a Modelo 100 XML export.

    A true ``xsd_valid`` means only that the XML validates against the named
    local schema preparation.  It never represents AEAT transmission or an
    AEAT acceptance result.
    """

    xml_sha256: str
    xml_size: int
    original_schema_sha256: str
    original_schema_size: int
    normalization: str
    normalization_count: int
    effective_validation_schema_sha256: str
    effective_validation_schema_size: int
    xsd_valid: bool
    error_identities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContinuationStateEvidence:
    """Value-free public readback at a frontend continuation boundary.

    The financial values themselves stay in the isolated store.  Each driver
    independently canonicalizes its public readback and records only its
    SHA-256 fingerprint, preventing a durable receipt from becoming a copy of
    taxpayer or invoice payloads.
    """

    authority_generation: str
    profile_complete: bool
    transactions: int
    invoices: int
    links: int
    work_periods: tuple[str, ...]
    calculated_periods: tuple[str, ...]
    verified_periods: tuple[str, ...]
    locally_filed_periods: tuple[str, ...]
    export_ready_modelos: tuple[str, ...]
    exported_modelos: tuple[str, ...]
    canonical_value_fingerprint: str

    def state_sha256(self) -> str:
        """Fingerprint the public continuation state without exposing values."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ContinuationCheckpoint:
    """A meaningful persisted-state boundary for a second frontend."""

    frontend_path: Literal["cli_to_tui", "tui_to_cli"]
    handoff_frontend: Literal["cli", "tui"]
    resume_frontend: Literal["cli", "tui"]
    state: ContinuationStateEvidence
    state_sha256: str


@dataclass(frozen=True, slots=True)
class ContinuationEvidence:
    """Proof that both frontends used and advanced one persisted workflow."""

    frontend_path: Literal["cli_to_tui", "tui_to_cli"]
    checkpoint: ContinuationCheckpoint
    resumed_state_sha256: str
    completion_state: ContinuationStateEvidence
    outcome: AcceptanceOutcome


@dataclass(frozen=True, slots=True)
class TuiJourneyEvidence:
    """Receipt for one installed-TUI or sequential continuation scenario."""

    brief_id: str
    brief_revision: str
    scenario: str
    frontend_path: Literal["tui", "cli_to_tui", "tui_to_cli"]
    year: int
    authority_generation: str
    modelo_130_revisions: tuple[str, ...]
    modelo_100_revision: str
    source_state: str
    contract_missing_controls: tuple[str, ...]
    cases: tuple[AcceptanceCaseEvidence, ...]
    xsd_validation: LocalXsdValidationEvidence | None = None
    continuation: ContinuationEvidence | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable, JSON-safe receipt payload."""
        return dict[str, object](asdict(self))
