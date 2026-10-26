"""Public projections shared by the local reader's read operations.

Facts, refusals and the measured admission verdict of one model load, as the
``local-reader`` reads publish them. Nothing here starts, loads, installs,
downloads or removes anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, Field, NonNegativeInt

from cadrumo_client.contracts.model_runs import MODEL_RUN_MODEL_ID_MAX_LENGTH

from ..core.hardware import ContentionCause
from ..core.models import STRICT_FROZEN_CONFIG
from .operator_actions.models import PreconditionVerdict
from .provisioning_contracts import (
    ProvisioningFactValue,
    ProvisioningPreconditionCondition,
    provisioning_no_recovery_verdict,
)
from .provisioning_runtime import ContentionSnapshot

__all__ = [
    "LOCAL_READER_OPERATION_SUBJECT",
    "LocalReaderContentionV1",
    "LocalReaderFactV1",
    "local_reader_fact_mapping",
    "local_reader_public_facts",
    "local_reader_public_verdict",
    "local_reader_verdict_condition",
    "local_reader_verdict_facts",
    "project_local_reader_contention",
]

LOCAL_READER_OPERATION_SUBJECT: Final = "local-reader:runtime"


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

    model: str = Field(min_length=1, max_length=MODEL_RUN_MODEL_ID_MAX_LENGTH)
    admitted: bool
    causes: tuple[ContentionCause, ...]
    required_bytes: NonNegativeInt
    free_vram_bytes: NonNegativeInt | None = None
    free_system_memory_bytes: NonNegativeInt | None = None
    shortfall_bytes: NonNegativeInt | None = None
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
        facts=local_reader_public_facts(snapshot.facts),
        verdict_condition_id=local_reader_verdict_condition(snapshot.precondition_verdict),
        verdict_facts=local_reader_verdict_facts(snapshot.precondition_verdict),
    )
