"""Public projections shared by the local reader's read operations.

Facts and refusals, as the ``local-reader`` reads publish them. Nothing here
starts, loads, installs, downloads or removes anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from .operator_actions.models import PreconditionVerdict
from .probe_outcomes import ProbeFactValue, ProbePreconditionCondition, probe_no_recovery_verdict

__all__ = [
    "LOCAL_READER_OPERATION_SUBJECT",
    "LocalReaderFactV1",
    "local_reader_fact_mapping",
    "local_reader_public_facts",
    "local_reader_public_verdict",
    "local_reader_verdict_condition",
    "local_reader_verdict_facts",
]

LOCAL_READER_OPERATION_SUBJECT: Final = "local-reader:runtime"


class LocalReaderFactV1(BaseModel):
    """One locale-neutral provisioning fact, as an immutable key/value pair."""

    model_config = STRICT_FROZEN_CONFIG

    key: str = Field(min_length=1, max_length=128)
    value: str | int | bool


def local_reader_public_facts(facts: Mapping[str, ProbeFactValue]) -> tuple[LocalReaderFactV1, ...]:
    """Return facts as immutable pairs, in the order they were recorded."""
    return tuple(LocalReaderFactV1(key=key, value=value) for key, value in facts.items())


def local_reader_fact_mapping(facts: tuple[LocalReaderFactV1, ...]) -> dict[str, str | int | bool]:
    """Return published facts as the mapping a frontend payload carries."""
    return {fact.key: fact.value for fact in facts}


def local_reader_public_verdict(
    failed_condition_id: str | None,
    verdict_facts: tuple[LocalReaderFactV1, ...],
) -> PreconditionVerdict | None:
    """Rebuild the refusal a public result names, or ``None`` when nothing was refused.

    A refusal is a runtime observation over its condition and facts, so the
    condition and the evidence facts are the whole verdict; the projector
    refuses to publish one that would not rebuild exactly.
    """
    if failed_condition_id is None:
        return None
    condition = ProbePreconditionCondition(failed_condition_id)
    return probe_no_recovery_verdict(condition, facts=local_reader_fact_mapping(verdict_facts))


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
    published: dict[str, ProbeFactValue] = {}
    for key, value in evidence.values.items():
        if not isinstance(value, str | int | bool):
            raise ValueError("refusal evidence must be locale-neutral scalars")
        published[key] = value
    facts = local_reader_public_facts(published)
    if verdict.action is not None or local_reader_public_verdict(verdict.failed_condition_id, facts) != verdict:
        raise ValueError("refusal does not rebuild from its public condition and facts")
    return facts
