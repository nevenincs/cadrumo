"""Canonical request and result contracts for the local reader's load and verify actions.

Both act on models the native component engine installed and the runtime
manager's server holds; neither starts, installs, downloads or removes
anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, Field, NonNegativeInt

from ..core.external_constants import OutputLanguage
from ..core.hardware import ContentionCause
from ..core.model_catalogue import ModelRole
from ..core.models import STRICT_FROZEN_CONFIG
from .operations.models import CredentialFreeOperationRequest, OperationRequest, OperationTerminalReceipt
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from .provisioning_runtime import ContentionSnapshot

__all__ = [
    "LOCAL_READER_EXECUTE_PHASE",
    "LOCAL_READER_OPERATION_DEFINITION_ID",
    "LOCAL_READER_OPERATION_SUBJECT",
    "LOCAL_READER_PREFLIGHT_PHASE",
    "LOCAL_READER_SETTLEMENT_PHASE",
    "LocalReaderContentionV1",
    "LocalReaderFactV1",
    "LocalReaderModelOutcome",
    "LocalReaderModelOutcomeV3",
    "LocalReaderProvisionAction",
    "LocalReaderProvisionOutcome",
    "LocalReaderProvisionPublicResultV3",
    "LocalReaderProvisionRequest",
    "build_local_reader_load_request",
    "local_reader_fact_mapping",
    "local_reader_public_facts",
    "local_reader_public_result",
    "local_reader_public_verdict",
    "local_reader_verdict_condition",
    "local_reader_verdict_facts",
    "project_local_reader_contention",
    "project_local_reader_result",
]

LOCAL_READER_OPERATION_DEFINITION_ID = "local-reader.provision"
LOCAL_READER_OPERATION_SUBJECT = "local-reader:runtime"
LOCAL_READER_PREFLIGHT_PHASE = "local-reader.provision.preflight"
LOCAL_READER_EXECUTE_PHASE = "local-reader.provision.execute"
LOCAL_READER_SETTLEMENT_PHASE = "local-reader.provision.settlement"


class LocalReaderProvisionAction(StrEnum):
    """What one local-reader action does with a model already installed; neither downloads anything.

    Load makes the running program hold a model in memory; verify measures it.
    Installing, starting and removing belong to the native component engine.
    """

    LOAD = "load"
    VERIFY = "verify"


class LocalReaderProvisionRequest(CredentialFreeOperationRequest):
    """One local-reader action, over one role's model, a named model, or every role's.

    ``output_language`` is the language a licence advisory is written in, so
    the frontend that asked reads it in its own; the host's language applies
    when it is absent.
    """

    action: LocalReaderProvisionAction
    role: ModelRole | None = None
    model: str | None = Field(default=None, min_length=1, max_length=256)
    output_language: OutputLanguage | None = None


def _request(
    action: LocalReaderProvisionAction,
    *,
    role: ModelRole | None = None,
    model: str | None = None,
    output_language: OutputLanguage | None = None,
) -> OperationRequest[LocalReaderProvisionRequest]:
    return OperationRequest(
        definition_id=LOCAL_READER_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderProvisionRequest(action=action, role=role, model=model, output_language=output_language),
    )


def build_local_reader_load_request(
    role: ModelRole | None = None,
    model: str | None = None,
    *,
    output_language: OutputLanguage | None = None,
) -> OperationRequest[LocalReaderProvisionRequest]:
    """Build the request that loads ``role``'s model, a named model, or every role's model."""
    return _request(LocalReaderProvisionAction.LOAD, role=role, model=model, output_language=output_language)


class LocalReaderModelOutcome(BaseModel):
    """What happened to one model, or to one role whose selection refused.

    ``already_satisfied`` marks a model that needed nothing, such as one
    already resident for a load. ``contention`` is the measured admission
    verdict that refused a load before anything was sent.
    """

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = None
    roles: tuple[ModelRole, ...]
    licence_advisories: tuple[str, ...] = ()
    succeeded: bool
    already_satisfied: bool = False
    contention: ContentionSnapshot | None = None
    resident: bool = False
    answered: bool = False
    elapsed_ms: int | None = Field(default=None, ge=0)
    facts: Mapping[str, ProvisioningFactValue] = Field(default_factory=dict)
    precondition_verdict: PreconditionVerdict | None = None

    @property
    def failed_condition_id(self) -> str | None:
        """Return the refused condition, when there is one."""
        return None if self.precondition_verdict is None else self.precondition_verdict.failed_condition_id


class LocalReaderProvisionOutcome(BaseModel):
    """The settled result of one local-reader action, one outcome per model in ``models``."""

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    models: tuple[LocalReaderModelOutcome, ...] = ()

    @property
    def failed_condition_id(self) -> str | None:
        """Return the first refused condition across the models."""
        return next((item.failed_condition_id for item in self.models if not item.succeeded), None)


class LocalReaderFactV1(BaseModel):
    """One locale-neutral provisioning fact, as an immutable key/value pair."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    value: str | int | bool


def local_reader_public_facts(facts: Mapping[str, ProvisioningFactValue]) -> tuple[LocalReaderFactV1, ...]:
    """Return provisioning facts as immutable pairs, in the order they were recorded."""
    return tuple(LocalReaderFactV1(key=key, value=value) for key, value in facts.items())


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


def local_reader_verdict_condition(verdict: PreconditionVerdict | None) -> str | None:
    """Return the refused condition a public result names, or ``None`` when nothing was refused."""
    return None if verdict is None else verdict.failed_condition_id


def local_reader_verdict_facts(verdict: PreconditionVerdict | None) -> tuple[LocalReaderFactV1, ...]:
    """Return the evidence facts a public result carries beside its refused condition.

    Raises:
        ValueError: When the refusal would not rebuild exactly from its condition and facts.
    """
    if verdict is None:
        return ()
    (evidence,) = verdict.evidence
    published: dict[str, ProvisioningFactValue] = {}
    for key, value in evidence.values.items():
        if not isinstance(value, str | int | bool):
            raise ValueError("provisioning refusal evidence must be locale-neutral scalars")
        published[key] = value
    facts = local_reader_public_facts(published)
    if local_reader_public_verdict(verdict.failed_condition_id, facts) != verdict:
        raise ValueError("provisioning refusal does not rebuild from its public condition and facts")
    return facts


class LocalReaderContentionV1(BaseModel):
    """Public projection of the measured admission verdict for one model load."""

    model_config = STRICT_FROZEN_CONFIG

    model: str = Field(min_length=1, max_length=256)
    admitted: bool
    causes: tuple[ContentionCause, ...]
    required_bytes: NonNegativeInt
    free_vram_bytes: NonNegativeInt | None = None
    free_system_memory_bytes: NonNegativeInt | None = None
    shortfall_bytes: NonNegativeInt | None = None
    unloadable_models: tuple[str, ...]
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


def project_local_reader_contention(snapshot: ContentionSnapshot | None) -> LocalReaderContentionV1 | None:
    """Project one contention verdict, or ``None`` when no admission check refused."""
    if snapshot is None:
        return None
    return LocalReaderContentionV1(
        model=snapshot.model,
        admitted=snapshot.admitted,
        causes=snapshot.causes,
        required_bytes=snapshot.required_bytes,
        free_vram_bytes=snapshot.free_vram_bytes,
        free_system_memory_bytes=snapshot.free_system_memory_bytes,
        shortfall_bytes=snapshot.shortfall_bytes,
        unloadable_models=snapshot.unloadable_models,
        facts=local_reader_public_facts(snapshot.facts),
        verdict_condition_id=local_reader_verdict_condition(snapshot.precondition_verdict),
        verdict_facts=local_reader_verdict_facts(snapshot.precondition_verdict),
    )


class LocalReaderModelOutcomeV3(BaseModel):
    """Public projection of one model outcome."""

    model_config = STRICT_FROZEN_CONFIG

    model: str | None = Field(default=None, min_length=1, max_length=256)
    roles: tuple[ModelRole, ...]
    licence_advisories: tuple[str, ...] = ()
    succeeded: bool
    already_satisfied: bool
    contention: LocalReaderContentionV1 | None = None
    resident: bool
    answered: bool
    elapsed_ms: NonNegativeInt | None = None
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    facts: tuple[LocalReaderFactV1, ...]
    verdict_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    verdict_facts: tuple[LocalReaderFactV1, ...]


class LocalReaderProvisionPublicResultV3(BaseModel):
    """Public projection of a settled provisioning operation."""

    model_config = STRICT_FROZEN_CONFIG

    action: LocalReaderProvisionAction
    succeeded: bool
    failed_condition_id: str | None = Field(default=None, min_length=1, max_length=128)
    models: tuple[LocalReaderModelOutcomeV3, ...]


def _project_model(item: LocalReaderModelOutcome) -> LocalReaderModelOutcomeV3:
    return LocalReaderModelOutcomeV3(
        model=item.model,
        roles=item.roles,
        licence_advisories=item.licence_advisories,
        succeeded=item.succeeded,
        already_satisfied=item.already_satisfied,
        contention=project_local_reader_contention(item.contention),
        resident=item.resident,
        answered=item.answered,
        elapsed_ms=item.elapsed_ms,
        failed_condition_id=item.failed_condition_id,
        facts=local_reader_public_facts(item.facts),
        verdict_condition_id=local_reader_verdict_condition(item.precondition_verdict),
        verdict_facts=local_reader_verdict_facts(item.precondition_verdict),
    )


def project_local_reader_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt) -> BaseModel:
    """Project a settled operation outcome into its credential-free public result."""
    del terminal_receipt
    return local_reader_public_result(LocalReaderProvisionOutcome.model_validate(result, strict=True))


def local_reader_public_result(outcome: LocalReaderProvisionOutcome) -> LocalReaderProvisionPublicResultV3:
    """Return the public result of one provisioning outcome, whichever caller ran it."""
    return LocalReaderProvisionPublicResultV3(
        action=outcome.action,
        succeeded=outcome.succeeded,
        failed_condition_id=outcome.failed_condition_id,
        models=tuple(_project_model(item) for item in outcome.models),
    )
