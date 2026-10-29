"""Canonical contracts for availability probe outcomes."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .operator_actions.models import PreconditionVerdict

__all__ = [
    "ProbeFactValue",
    "ProbeOutcome",
    "ProbePreconditionCondition",
    "probe_no_recovery_verdict",
    "require_probe_verdict",
]


class ProbePreconditionCondition(StrEnum):
    """Stable failed-condition identities emitted by availability probes."""

    OPTIONAL_EXTRA_IMPORTABLE = "probe.optional_extra.importable"
    PLAYWRIGHT_BROWSER_INSTALLED = "probe.playwright_browser.installed"
    PLAYWRIGHT_BROWSER_MANIFEST_READABLE = "probe.playwright_browser.manifest_readable"
    RUNTIME_REACHABLE = "probe.runtime.reachable"
    """The agent stated whether the local AI server holds a role's model; unstated is unknown, never absent."""
    ROLE_MODEL_INSTALLED = "probe.role_model.installed"
    SELECTED_MODEL_AVAILABLE = "probe.selected_model.available"
    SELECTED_MODEL_READS_IMAGES = "probe.selected_model.reads_images"
    """The selected model is stated to read images, which reading a scanned page needs."""
    LOAD_CAPACITY_AVAILABLE = "probe.load_capacity.available"
    """The agent loaded the selected model with the memory this computer had free."""


ProbeFactValue = str | int | bool
"""Locale-neutral scalar facts emitted by probe outcome records."""


def probe_no_recovery_verdict(
    condition: ProbePreconditionCondition,
    *,
    facts: Mapping[str, ProbeFactValue],
) -> PreconditionVerdict:
    """Return the explicit closed outcome for one probe refusal."""
    from .operator_actions.preconditions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def require_probe_verdict(*, failed: bool, verdict: PreconditionVerdict | None) -> None:
    """Refuse silent probe failure and success records carrying a refusal."""
    if failed and verdict is None:
        raise ValueError("failed probe outcomes require a precondition verdict")
    if not failed and verdict is not None:
        raise ValueError("successful probe outcomes cannot carry a precondition verdict")


class ProbeOutcome(BaseModel):
    """Shared locale-neutral facts and precondition outcome for probe records."""

    model_config = STRICT_FROZEN_CONFIG

    facts: Mapping[str, ProbeFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None
