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
    "OLLAMA_LOAD_KEEP_ALIVE",
    "OLLAMA_PROBE_CACHE_TTL_S",
    "OLLAMA_PROBE_TIMEOUT_S",
    "OLLAMA_READINESS_TIMEOUT_S",
    "ProvisioningFactValue",
    "ProvisioningOutcome",
    "ProvisioningPreconditionCondition",
    "provisioning_no_recovery_verdict",
    "provisioning_setup_verdict",
    "require_provisioning_verdict",
]

LOCAL_AI_PROVISION_ACTION_ID = "operator.provision.local_ai"
"""The operator action that sets up the local AI program and every role's model."""

OLLAMA_PROBE_TIMEOUT_S = 2.0

# How long one probe's answer stands before the endpoint is asked again.
#
# Reachability of a local model server is a property of the machine, not of the
# work being done, so asking once per document -- or once per batch run, or once
# per test -- re-answers a question whose answer did not change. Measured on a
# host with no Ollama running: 65 probes of 127.0.0.1:11434 across one test
# module, 71.5s of its 98s, at ~0.94s per refused connection. Redirecting the
# endpoint does not help, because the cost is the connection ATTEMPT rather than
# the target.
#
# Bounded rather than process-lifetime, for the same reason the registry
# fingerprint cache is: an operator who starts their model server mid-session
# must see it appear without restarting the process. Ten seconds folds the
# repeated probes of one operator interaction while still noticing a server that
# came up moments ago, and matches BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS
# rather than inventing a second cadence.
OLLAMA_PROBE_CACHE_TTL_S = 10.0

# Readiness asks whether a LOADED model answers. A cold load of a small vision
# model is tens of seconds on this class of hardware, so the bound is generous
# enough not to report a working model as unready while still bounded.
OLLAMA_READINESS_TIMEOUT_S = 120.0

# How long the runtime keeps a model resident after an explicit load. The
# runtime's own default is five minutes, which expires before an operator who
# loaded ahead of a batch has started it; half an hour covers that gap while
# still releasing memory on an idle machine.
OLLAMA_LOAD_KEEP_ALIVE = "30m"


class ProvisioningPreconditionCondition(StrEnum):
    """Stable failed-condition identities emitted by provisioning policy."""

    OPTIONAL_EXTRA_IMPORTABLE = "provisioning.optional_extra.importable"
    PLAYWRIGHT_BROWSER_INSTALLED = "provisioning.playwright_browser.installed"
    PLAYWRIGHT_BROWSER_MANIFEST_READABLE = "provisioning.playwright_browser.manifest_readable"
    RUNTIME_REACHABLE = "provisioning.runtime.reachable"
    RUNTIME_INSTALLED = "provisioning.runtime.installed"
    ROLE_MODEL_INSTALLED = "provisioning.role_model.installed"
    ROLE_MODEL_FIT_FOR_ROLE = "provisioning.role_model.fit_for_role"
    ROLE_MODEL_FITNESS_VERIFIED = "provisioning.role_model.fitness_verified"
    ROLE_MODEL_FITNESS_WITHIN_TIMEOUT = "provisioning.role_model.fitness_within_timeout"
    HARDWARE_FLOOR_MET = "provisioning.hardware_floor.met"
    SELECTED_MODEL_AVAILABLE = "provisioning.selected_model.available"
    SELECTED_MODEL_FITS = "provisioning.selected_model.fits"
    SELECTED_MODEL_CATALOGUED = "provisioning.selected_model.catalogued"
    LOAD_HEADROOM_MEASURABLE = "provisioning.load_headroom.measurable"
    LOAD_CAPACITY_AVAILABLE = "provisioning.load_capacity.available"
    RESIDENT_SET_READABLE = "provisioning.resident_set.readable"
    MODEL_SELECTED_BY_CADRUMO = "provisioning.model.selected_by_cadrumo"
    MODEL_RESIDENT = "provisioning.model.resident"
    MODEL_LOADED = "provisioning.model.loaded"
    MODEL_READY = "provisioning.model.ready"
    MODEL_INSTALLED = "provisioning.model.installed"
    LOCAL_MODEL_INVENTORY_READABLE = "provisioning.local_model.inventory_readable"
    LOCAL_MODEL_EXTRA_REQUIRES_MODEL = "provisioning.local_model.extra_requires_model"
    LOCAL_MODEL_MODEL_REQUIRES_EXTRA = "provisioning.local_model.model_requires_extra"


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
