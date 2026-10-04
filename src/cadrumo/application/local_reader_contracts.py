"""Canonical request and result contracts for supervised local-reader provisioning."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from .provisioning_host import RuntimeInstaller

__all__ = [
    "LOCAL_READER_EXECUTE_PHASE",
    "LOCAL_READER_OPERATION_DEFINITION_ID",
    "LOCAL_READER_OPERATION_SUBJECT",
    "LOCAL_READER_PREFLIGHT_PHASE",
    "LOCAL_READER_PULL_PROGRESS_UNIT",
    "LOCAL_READER_SETTLEMENT_PHASE",
    "LocalReaderFactV1",
    "LocalReaderInstallOutcome",
    "LocalReaderInstallOutcomeV1",
    "LocalReaderModelOutcome",
    "LocalReaderModelOutcomeV1",
    "LocalReaderProvisionAction",
    "LocalReaderProvisionOutcome",
    "LocalReaderProvisionPublicResultV1",
    "LocalReaderProvisionRequest",
    "LocalReaderSetupStep",
    "LocalReaderSetupStepOutcome",
    "LocalReaderSetupStepOutcomeV1",
    "LocalReaderSetupStepState",
    "build_local_reader_install_request",
    "build_local_reader_load_request",
    "build_local_reader_remove_request",
    "build_local_reader_setup_request",
    "local_reader_fact_mapping",
    "local_reader_public_verdict",
    "local_reader_setup_phase",
    "project_local_reader_result",
]

LOCAL_READER_OPERATION_DEFINITION_ID = "local-reader.provision"
LOCAL_READER_OPERATION_SUBJECT = "local-reader:runtime"
LOCAL_READER_PULL_PROGRESS_UNIT = "local-reader.bytes"
LOCAL_READER_PREFLIGHT_PHASE = "local-reader.provision.preflight"
LOCAL_READER_EXECUTE_PHASE = "local-reader.provision.execute"
LOCAL_READER_SETTLEMENT_PHASE = "local-reader.provision.settlement"


class LocalReaderProvisionAction(StrEnum):
    """What one provisioning operation does."""

    INSTALL = "install"
    START = "start"
    PULL = "pull"
    LOAD = "load"
    VERIFY = "verify"
    REMOVE = "remove"
    SETUP = "setup"


class LocalReaderSetupStep(StrEnum):
    """The ordered steps of a one-shot setup."""

    INSTALL = "install"
    START = "start"
    PULL = "pull"
    LOAD = "load"
    VERIFY = "verify"


class LocalReaderSetupStepState(StrEnum):
    """What one setup step did: nothing needed, a change, a refusal, or not run."""

    UNCHANGED = "unchanged"
    CHANGED = "changed"
    FAILED = "failed"
    NOT_REACHED = "not_reached"


def local_reader_setup_phase(step: LocalReaderSetupStep) -> str:
    """Return the declared phase code a setup publishes when ``step`` begins."""
    return f"local-reader.provision.step.{step.value}"


_CONSENTING_ACTIONS = frozenset({LocalReaderProvisionAction.INSTALL, LocalReaderProvisionAction.SETUP})
_MODEL_NAMING_ACTIONS = frozenset({LocalReaderProvisionAction.LOAD, LocalReaderProvisionAction.REMOVE})


class LocalReaderProvisionRequest(CredentialFreeOperationRequest):
    """One provisioning action, over one role's model, a named model, or every role's.

    ``consent`` is the operator's explicit agreement to run the package-manager
    install and is accepted only by the actions that may install. ``model``
    names a model outright and is accepted only by load and remove; remove
    requires a role or a model so it never deletes every model by default.
    """

    action: LocalReaderProvisionAction
    role: ModelRole | None = None
    model: str | None = Field(default=None, min_length=1, max_length=256)
    consent: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_coherent_request(self) -> LocalReaderProvisionRequest:
        _require_consent_action(self.action, self.consent)
        _require_model_naming_action(self.action, self.model)
        _require_runtime_action_role(self.action, self.role)
        _require_removal_target(self.action, self.role, self.model)
        return self


def _require_consent_action(action: LocalReaderProvisionAction, consent: bool) -> None:
    if consent and action not in _CONSENTING_ACTIONS:
        raise ValueError("only install and setup accept install consent")


def _require_model_naming_action(action: LocalReaderProvisionAction, model: str | None) -> None:
    if model is not None and action not in _MODEL_NAMING_ACTIONS:
        raise ValueError("only load and remove accept an explicit model")


def _require_runtime_action_role(action: LocalReaderProvisionAction, role: ModelRole | None) -> None:
    if action in {LocalReaderProvisionAction.INSTALL, LocalReaderProvisionAction.START} and role is not None:
        raise ValueError("install and start act on the runtime, not on a role")


def _require_removal_target(
    action: LocalReaderProvisionAction,
    role: ModelRole | None,
    model: str | None,
) -> None:
    if action is LocalReaderProvisionAction.REMOVE and role is None and model is None:
        raise ValueError("remove requires a role or a model")


def _request(
    action: LocalReaderProvisionAction,
    *,
    role: ModelRole | None = None,
    model: str | None = None,
    consent: bool = False,
) -> OperationRequest[LocalReaderProvisionRequest]:
    return OperationRequest(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest(action=action, role=role, model=model, consent=consent),
    )


def build_local_reader_install_request(*, consent: bool) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that installs the runtime; nothing is installed without ``consent``."""
    return _request(LocalReaderProvisionAction.INSTALL, consent=consent)


def build_local_reader_load_request(
    role: ModelRole | None = None, model: str | None = None
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that loads ``role``'s model, a named model, or every role's model."""
    return _request(LocalReaderProvisionAction.LOAD, role=role, model=model)


def build_local_reader_remove_request(
    role: ModelRole | None = None, model: str | None = None
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that removes ``role``'s model or a named model from the runtime's store."""
    return _request(LocalReaderProvisionAction.REMOVE, role=role, model=model)


def build_local_reader_setup_request(*, consent: bool) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the one-shot setup request: install (with ``consent``), start, pull, load, verify."""
    return _request(LocalReaderProvisionAction.SETUP, consent=consent)


class LocalReaderModelOutcome(BaseModel):
    """What happened to one model, or to one role whose selection refused.

    ``already_satisfied`` marks a model that needed nothing: already pulled for
    a pull, already resident for a load. ``step`` names the setup step that
    produced the item, and is absent outside setup.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = None
    roles: tuple[ModelRole, ...]
    succeeded: bool
    already_satisfied: bool = False
    step: LocalReaderSetupStep | None = None
    bytes_fetched: int | None = Field(default=None, ge=0)
    freed_bytes: int | None = Field(default=None, ge=0)
    was_installed: bool = False
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = Field(default=None, ge=0)
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @property
    def failed_condition_id(self) -> str | None:
        """Return the refused condition, when there is one."""
        return None if self.precondition_verdict is None else self.precondition_verdict.failed_condition_id


class LocalReaderInstallOutcome(BaseModel):
    """What the install request found and did."""

    model_config = STRICT_FROZEN_CONFIG

    installed: bool
    already_installed: bool = False
    installer: RuntimeInstaller
    consented: bool
    installer_exit_code: int | None = None


class LocalReaderSetupStepOutcome(BaseModel):
    """One setup step's state and, when it failed, the refused condition."""

    model_config = STRICT_FROZEN_CONFIG

    step: LocalReaderSetupStep
    state: LocalReaderSetupStepState
    failed_condition_id: str | None = None


class LocalReaderProvisionOutcome(BaseModel):
    """The settled result of one provisioning operation.

    ``facts`` and ``precondition_verdict`` describe the runtime-level action
    (install or start); per-model detail is in ``models``. For setup,
    ``steps`` lists every step in order and ``stopped_step`` names the step
    that failed, after which every later step is ``not_reached``.
    """

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool = False
    already_running: bool = False
    started_pid: int | None = Field(default=None, ge=0)
    install: LocalReaderInstallOutcome | None = None
    models: tuple[LocalReaderModelOutcome, ...] = ()
    steps: tuple[LocalReaderSetupStepOutcome, ...] = ()
    stopped_step: LocalReaderSetupStep | None = None
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @property
    def failed_condition_id(self) -> str | None:
        """Return the first refused condition across the runtime action, steps and models."""
        if self.precondition_verdict is not None:
            return self.precondition_verdict.failed_condition_id
        failed_step = next((step.failed_condition_id for step in self.steps if step.failed_condition_id), None)
        if failed_step is not None:
            return failed_step
        return next((item.failed_condition_id for item in self.models if not item.succeeded), None)


class LocalReaderFactV1(BaseModel):
    """One locale-neutral provisioning fact, as an immutable key/value pair."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    value: str | int | bool


def _public_facts(facts: Mapping[str, ProvisioningFactValue]) -> tuple[LocalReaderFactV1, ...]:
    return tuple(LocalReaderFactV1(key=key, value=value) for key, value in sorted(facts.items()))


def local_reader_fact_mapping(facts: tuple[LocalReaderFactV1, ...]) -> dict[str, str | int | bool]:
    """Return published facts as the mapping a frontend payload carries."""
    return {fact.key: fact.value for fact in facts}


def local_reader_public_verdict(
    failed_condition_id: str | None, verdict_facts: tuple[LocalReaderFactV1, ...]
) -> PreconditionVerdict | None:
    """Rebuild the provisioning refusal a public result names, or ``None`` when nothing was refused.

    Every provisioning refusal is a no-recovery runtime observation over its
    condition and facts, so the condition and the evidence facts are the whole
    verdict; the projector refuses to publish one that would not rebuild exactly.
    """
    if failed_condition_id is None:
        return None
    return provisioning_no_recovery_verdict(
        ProvisioningPreconditionCondition(failed_condition_id), facts=local_reader_fact_mapping(verdict_facts)
    )


def _verdict_condition(verdict: PreconditionVerdict | None) -> str | None:
    return None if verdict is None else verdict.failed_condition_id


def _verdict_facts(verdict: PreconditionVerdict | None) -> tuple[LocalReaderFactV1, ...]:
    if verdict is None:
        return ()
    (evidence,) = verdict.evidence
    published: dict[str, ProvisioningFactValue] = {}
    for key, value in evidence.values.items():
        if not isinstance(value, str | int | bool):
            raise ValueError("provisioning refusal evidence must be locale-neutral scalars")
        published[key] = value
    facts = _public_facts(published)
    if local_reader_public_verdict(verdict.failed_condition_id, facts) != verdict:
        raise ValueError("provisioning refusal does not rebuild from its public condition and facts")
    return facts


class LocalReaderModelOutcomeV1(BaseModel):
    """Public projection of one model outcome."""

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = Field(default=None, min_length=1, max_length=256)
    roles: tuple[ModelRole, ...]
    succeeded: bool
    already_satisfied: bool
    step: LocalReaderSetupStep | None = None
    bytes_fetched: NonNegativeInt | None = None
    freed_bytes: NonNegativeInt | None = None
    was_installed: bool
    resident: bool
    answered: bool
    elapsed_ms: NonNegativeInt | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


class LocalReaderInstallOutcomeV1(BaseModel):
    """Public projection of the install request."""

    model_config = STRICT_FROZEN_CONFIG

    installed: bool
    already_installed: bool
    installer: RuntimeInstaller
    consented: bool
    installer_exit_code: int | None = None


class LocalReaderSetupStepOutcomeV1(BaseModel):
    """Public projection of one setup step."""

    model_config = STRICT_FROZEN_CONFIG

    step: LocalReaderSetupStep
    state: LocalReaderSetupStepState
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)


class LocalReaderProvisionPublicResultV1(BaseModel):
    """Public projection of a settled provisioning operation."""

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    runtime_started: bool
    already_running: bool
    started_pid: NonNegativeInt | None = None
    install: LocalReaderInstallOutcomeV1 | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    models: tuple[LocalReaderModelOutcomeV1, ...]
    steps: tuple[LocalReaderSetupStepOutcomeV1, ...]
    stopped_step: LocalReaderSetupStep | None = None
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


def _project_model(item: LocalReaderModelOutcome) -> LocalReaderModelOutcomeV1:
    return LocalReaderModelOutcomeV1(
        model=item.model,
        roles=item.roles,
        succeeded=item.succeeded,
        already_satisfied=item.already_satisfied,
        step=item.step,
        bytes_fetched=item.bytes_fetched,
        freed_bytes=item.freed_bytes,
        was_installed=item.was_installed,
        resident=item.resident,
        answered=item.answered,
        elapsed_ms=item.elapsed_ms,
        failed_condition_id=item.failed_condition_id,
        facts=_public_facts(item.facts),
        verdict_condition_id=_verdict_condition(item.precondition_verdict),
        verdict_facts=_verdict_facts(item.precondition_verdict),
    )


def project_local_reader_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled operation outcome into its credential-free public result."""
    del terminal_receipt
    outcome = LocalReaderProvisionOutcome.model_validate(result, strict=True)
    install = outcome.install
    return LocalReaderProvisionPublicResultV1(
        action=outcome.action,
        succeeded=outcome.succeeded,
        runtime_started=outcome.runtime_started,
        already_running=outcome.already_running,
        started_pid=outcome.started_pid,
        install=(
            None
            if install is None
            else LocalReaderInstallOutcomeV1(
                installed=install.installed,
                already_installed=install.already_installed,
                installer=install.installer,
                consented=install.consented,
                installer_exit_code=install.installer_exit_code,
            )
        ),
        failed_condition_id=outcome.failed_condition_id,
        models=tuple(_project_model(item) for item in outcome.models),
        steps=tuple(
            LocalReaderSetupStepOutcomeV1(
                step=step.step, state=step.state, failed_condition_id=step.failed_condition_id
            )
            for step in outcome.steps
        ),
        stopped_step=outcome.stopped_step,
        facts=_public_facts(outcome.facts),
        verdict_condition_id=_verdict_condition(outcome.precondition_verdict),
        verdict_facts=_verdict_facts(outcome.precondition_verdict),
    )
