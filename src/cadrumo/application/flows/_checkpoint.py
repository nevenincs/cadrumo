"""The per-mode checkpoint port.

The substrate defines the port; the domain flow supplies the
implementation, and every implementation routes through the owning
domain's existing encrypted persistence authority — never a bespoke
store, never flow-owned crypto. The facts are the checkpoint: the port
persists the canonical answer map only, and resume rebuilds everything
derived (cursor, staleness, validation) from the *current* definition
(:mod:`._resume`).

Availability is a per-mode declaration on the
:class:`~cadrumo.application.flows.FlowDefinition` (``checkpoint``
field). ``UNAVAILABLE`` is the declared no-op arm: :func:`save_checkpoint`
refuses rather than silently dropping, and frontends read
:func:`checkpoint_available` to disable the save-and-exit affordance
with an explicit message — an interrupted run in a no-op mode discards
staged answers loudly, never silently.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ...core.flows import CheckpointAvailability, FlowMode
from ._definition import FlowDefinition
from ._engine import FlowState
from .errors import FlowCheckpointError


@runtime_checkable
class CheckpointStore(Protocol):
    """Domain-supplied persistence port for in-progress flow answers.

    Implementations MUST write through the owning domain's mutation
    authority (for the profile domain: effective-dated fact writes via
    the profile lifecycle service) and MUST NOT persist plaintext
    anywhere. ``load`` returns the persisted canonical answer map or
    ``None`` when no in-progress run exists; ``discard`` erases through
    the same authority.
    """

    def save(self, flow_id: str, answers: Mapping[str, str]) -> None:
        """Persist the canonical answer map for ``flow_id``."""
        ...

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        """Return the persisted answer map, or ``None`` when absent."""
        ...

    def discard(self, flow_id: str) -> None:
        """Erase the persisted in-progress run."""
        ...


def checkpoint_available(definition: FlowDefinition, mode: FlowMode) -> bool:
    """Whether the definition declares checkpointing for ``mode``."""
    return definition.checkpoint[mode] is CheckpointAvailability.AVAILABLE


def save_checkpoint(
    definition: FlowDefinition,
    state: FlowState,
    store: CheckpointStore,
) -> None:
    """Persist the state's committed answers through the domain store.

    Refuses in a mode whose declaration is the no-op arm — the frontend
    should never have offered the affordance; reaching this refusal
    means a frontend honesty bug, and the refusal (counts only, never
    answer values) makes it loud.
    """
    if not checkpoint_available(definition, state.mode):
        raise FlowCheckpointError(
            translated_message="application.flows.errors.checkpoint_unavailable_mode",
            context={
                "flow_id": definition.id,
                "mode": state.mode.value,
                "answered_count": len(state.answers),
            },
        )
    store.save(definition.id, dict(state.answers))


def discard_checkpoint(definition: FlowDefinition, store: CheckpointStore) -> None:
    """Erase the in-progress run through the domain store."""
    store.discard(definition.id)


__all__ = [
    "CheckpointStore",
    "checkpoint_available",
    "discard_checkpoint",
    "save_checkpoint",
]
