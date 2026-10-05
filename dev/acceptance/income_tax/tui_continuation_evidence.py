"""Validate persisted-state fingerprints and sequential frontend continuation evidence."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, Literal

from .scenario import AcceptanceOutcome
from .tui_contracts import ContinuationCheckpoint, ContinuationEvidence, ContinuationStateEvidence, TuiJourneyError

if TYPE_CHECKING:
    pass


_SHA256_HEX: Final = re.compile(r"[0-9a-f]{64}")


def _assert_continuation_counts(state: ContinuationStateEvidence) -> None:
    """Continuation counts."""
    for label, value in (
        ("transactions", state.transactions),
        ("invoices", state.invoices),
        ("links", state.links),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TuiJourneyError(f"continuation state has invalid {label} count")


def _assert_continuation_lists(state: ContinuationStateEvidence) -> None:
    """Continuation lists."""
    for label, values in (
        ("work_periods", state.work_periods),
        ("calculated_periods", state.calculated_periods),
        ("verified_periods", state.verified_periods),
        ("locally_filed_periods", state.locally_filed_periods),
        ("export_ready_modelos", state.export_ready_modelos),
        ("exported_modelos", state.exported_modelos),
    ):
        if any(not value for value in values):
            raise TuiJourneyError(f"continuation state has invalid {label}")
        if values != tuple(sorted(set(values))):
            raise TuiJourneyError(f"continuation state must use sorted unique {label}")


def canonical_financial_value_fingerprint(*, values: Mapping[str, str]) -> str:
    """Fingerprint independently normalized financial readback without retaining it.

    Callers must supply canonical, value-only strings such as normalized
    casilla amounts.  The resulting digest is safe to place in the durable
    receipt and lets the CLI and TUI demonstrate equal financial meaning
    without copying their financial readback into a checkpoint.
    """
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key or not isinstance(value, str):
            raise TuiJourneyError("canonical financial fingerprint requires non-empty string keys and string values")
        normalized[key] = value
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_continuation_checkpoint(
    *,
    frontend_path: Literal["cli_to_tui", "tui_to_cli"],
    state: ContinuationStateEvidence,
) -> ContinuationCheckpoint:
    """Record a non-final workflow that the other frontend must reopen.

    Empty records, a mere screen open, and a fully completed export are not
    useful continuation starts.  This gate makes the first frontend leave
    real persisted financial work for the second frontend without allowing a
    private-store handoff assertion to stand in for public readback.
    """
    _validate_continuation_state(state)
    handoff_frontend, resume_frontend = _continuation_frontends(frontend_path)
    if not state.profile_complete or not all((state.transactions, state.invoices, state.links)):
        raise TuiJourneyError("continuation handoff has no meaningful persisted financial capture")
    if not state.work_periods:
        raise TuiJourneyError("continuation handoff has no persisted declaration work")
    if _is_completion_state(state):
        raise TuiJourneyError("continuation handoff is already complete")
    return ContinuationCheckpoint(
        frontend_path=frontend_path,
        handoff_frontend=handoff_frontend,
        resume_frontend=resume_frontend,
        state=state,
        state_sha256=state.state_sha256(),
    )


def validate_continuation_readback(
    *,
    checkpoint: ContinuationCheckpoint,
    frontend: Literal["cli", "tui"],
    state: ContinuationStateEvidence,
) -> str:
    """Require the receiving frontend to reproduce the exact handoff state."""
    if frontend != checkpoint.resume_frontend:
        raise TuiJourneyError(
            f"continuation {checkpoint.frontend_path} must resume through {checkpoint.resume_frontend}"
        )
    _validate_continuation_state(state)
    if state != checkpoint.state or state.state_sha256() != checkpoint.state_sha256:
        raise TuiJourneyError("receiving frontend did not reproduce the persisted continuation state")
    return checkpoint.state_sha256


def prove_continuation(
    *,
    checkpoint: ContinuationCheckpoint,
    frontend: Literal["cli", "tui"],
    resumed_state: ContinuationStateEvidence,
    completion_state: ContinuationStateEvidence,
) -> ContinuationEvidence:
    """Validate readback and completion without treating an already-done run as a handoff."""
    resumed_state_sha256 = validate_continuation_readback(
        checkpoint=checkpoint,
        frontend=frontend,
        state=resumed_state,
    )
    _validate_continuation_state(completion_state)
    if completion_state.authority_generation != checkpoint.state.authority_generation:
        raise TuiJourneyError("continuation completion used a different authority generation")
    if completion_state.canonical_value_fingerprint != checkpoint.state.canonical_value_fingerprint:
        raise TuiJourneyError("continuation completion changed canonical financial meaning")
    if completion_state.state_sha256() == checkpoint.state_sha256:
        raise TuiJourneyError("receiving frontend did not advance the persisted workflow")
    if not _is_completion_state(completion_state):
        raise TuiJourneyError("continuation completion lacks required four-period local lifecycle and annual export")
    return ContinuationEvidence(
        frontend_path=checkpoint.frontend_path,
        checkpoint=checkpoint,
        resumed_state_sha256=resumed_state_sha256,
        completion_state=completion_state,
        outcome=AcceptanceOutcome.PROVEN,
    )


def _continuation_frontends(
    frontend_path: Literal["cli_to_tui", "tui_to_cli"],
) -> tuple[Literal["cli", "tui"], Literal["cli", "tui"]]:
    """Return the only valid writer/readback order for a continuation path."""
    if frontend_path == "cli_to_tui":
        return "cli", "tui"
    if frontend_path == "tui_to_cli":
        return "tui", "cli"
    raise TuiJourneyError(f"unsupported continuation path: {frontend_path}")


def _validate_continuation_state(state: ContinuationStateEvidence) -> None:
    """Reject ambiguous, unordered, or value-carrying boundary descriptions."""
    if not _SHA256_HEX.fullmatch(state.authority_generation):
        raise TuiJourneyError("continuation state has no SHA-256 authority generation")
    if not _SHA256_HEX.fullmatch(state.canonical_value_fingerprint):
        raise TuiJourneyError("continuation state has no SHA-256 canonical value fingerprint")
    _assert_continuation_counts(state)
    _assert_continuation_lists(state)
    work_periods = set(state.work_periods)
    if not set(state.calculated_periods).issubset(work_periods):
        raise TuiJourneyError("continuation state calculates a declaration with no persisted work")
    if not set(state.verified_periods).issubset(state.calculated_periods):
        raise TuiJourneyError("continuation state verifies a declaration that was not calculated")
    if not set(state.locally_filed_periods).issubset(state.verified_periods):
        raise TuiJourneyError("continuation state files a declaration that was not verified")


def _is_completion_state(state: ContinuationStateEvidence) -> bool:
    """Recognize the campaign's four-period local lifecycle plus M100 export."""
    quarters = {"1T", "2T", "3T", "4T"}
    return (
        quarters.issubset(state.work_periods)
        and quarters.issubset(state.calculated_periods)
        and quarters.issubset(state.verified_periods)
        and quarters.issubset(state.locally_filed_periods)
        and "100" in state.export_ready_modelos
        and "100" in state.exported_modelos
    )
