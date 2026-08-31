"""Narrow calling convention for presenting the generic operation modal.

A caller needs exactly one door: hand over an already-bound
:class:`OperationController` and receive the typed public outcome once the
modal settles or the operator detaches. Nothing here exposes the modal's
internal Textual widgets, its polling worker, or any application-private
operation type; the accepted and returned shapes are the public operation
contracts and this package's own derived public DTOs.
"""

from __future__ import annotations

from typing import Protocol

from .controller import OperationController
from .modal import OperationModal, OperationModalDetachedOutcomeV1, OperationModalOutcomeV1


class _ModalHost(Protocol):
    """The narrow subset of a Textual app/screen this facade depends on."""

    async def push_screen_wait(self, screen: OperationModal) -> OperationModalOutcomeV1: ...


async def present_operation_modal(
    host: _ModalHost,
    controller: OperationController,
) -> OperationModalOutcomeV1:
    """Present the generic operation modal and return its public outcome."""
    return await host.push_screen_wait(OperationModal(controller))


def is_detached_outcome(outcome: OperationModalOutcomeV1) -> bool:
    """Report whether a presented modal closed by detaching, not settling."""
    return isinstance(outcome, OperationModalDetachedOutcomeV1)


__all__ = ["is_detached_outcome", "present_operation_modal"]
