"""Canonical contracts for local-model provisioning outcomes."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from .operator_actions.models import ActionReference, ConditionEvidence, PreconditionVerdict

__all__ = [
    "LOCAL_AI_PROVISION_ACTION_ID",
    "ProvisioningFactValue",
    "ProvisioningOutcome",
    "ProvisioningPreconditionCondition",
    "provisioning_no_recovery_verdict",
    "provisioning_setup_verdict",
    "require_provisioning_verdict",
]

LOCAL_AI_PROVISION_ACTION_ID = "operator.provision.local_ai"
"""The operator action that names the local AI's setup, which only the desktop app performs.

Every surface words it as a pointer to the desktop; none runs a command for it.
"""


class ProvisioningPreconditionCondition(StrEnum):
    """Stable failed-condition identities emitted by provisioning policy."""

    OPTIONAL_EXTRA_IMPORTABLE = "provisioning.optional_extra.importable"
    PLAYWRIGHT_BROWSER_INSTALLED = "provisioning.playwright_browser.installed"
    PLAYWRIGHT_BROWSER_MANIFEST_READABLE = "provisioning.playwright_browser.manifest_readable"
    RUNTIME_REACHABLE = "provisioning.runtime.reachable"
    """The agent stated whether the local AI server holds a role's model; unstated is unknown, never absent."""
    RUNTIME_INSTALLED = "provisioning.runtime.installed"
    """The components role reports the local AI program set up and usable."""
    ROLE_MODEL_INSTALLED = "provisioning.role_model.installed"
    HARDWARE_FLOOR_MET = "provisioning.hardware_floor.met"
    SELECTED_MODEL_AVAILABLE = "provisioning.selected_model.available"
    LOAD_CAPACITY_AVAILABLE = "provisioning.load_capacity.available"
    """The agent loaded the selected model with the memory this computer had free."""


ProvisioningFactValue = str | int | bool
"""Locale-neutral scalar facts emitted by provisioning outcome records."""


def provisioning_no_recovery_verdict(
    condition: ProvisioningPreconditionCondition,
    *,
    facts: Mapping[str, ProvisioningFactValue],
) -> PreconditionVerdict:
    """Return the explicit closed outcome for one provisioning refusal."""
    from .operator_actions.preconditions import no_action_precondition_verdict

    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def provisioning_setup_verdict(
    condition: ProvisioningPreconditionCondition,
    *,
    facts: Mapping[str, ProvisioningFactValue],
    action_id: str,
) -> PreconditionVerdict:
    """Return the refusal for a component that setup can supply, recovered by ``action_id``."""
    return PreconditionVerdict(
        failed_condition_id=condition.value,
        evidence=(
            ConditionEvidence(
                condition_id=condition.value,
                evidence_id=f"{condition.value}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=facts,
            ),
        ),
        action=ActionReference(action_id=action_id),
        conditionality=ActionConditionality.IMMEDIATE,
    )


def require_provisioning_verdict(*, failed: bool, verdict: PreconditionVerdict | None) -> None:
    """Refuse silent provisioning failure and success records carrying a refusal."""
    if failed and verdict is None:
        raise ValueError("failed provisioning outcomes require a precondition verdict")
    if not failed and verdict is not None:
        raise ValueError("successful provisioning outcomes cannot carry a precondition verdict")


class ProvisioningOutcome(BaseModel):
    """Shared locale-neutral facts and precondition outcome for provisioning records."""

    model_config = STRICT_FROZEN_CONFIG

    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None
