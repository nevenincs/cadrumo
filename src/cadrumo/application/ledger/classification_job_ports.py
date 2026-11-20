"""What the ledger classification job operations need from outside the application.

A job is stored through one profile's repository, its movements are read from
that profile's transaction catalogue, and the lane it is bound to is the one the
agent service resolves for the reading role. The outer composition root binds
each to the exact profile and pinned authority of the operation that asks.

The lane is resolved through the same model-run lookup the ledger's
classification review dispatches with, so a job is bound to the model a review
would read with, naming the classification task kind. The agent service owns
which lane, model and effort that is: a setting the person makes for the
classification task kind answers the lookup, else the model documents are read
with does, and Cadrumo names no model of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol

from ...core.model_roles import ModelRole

if TYPE_CHECKING:
    from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunTaskKind

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.transactions.models import TransactionCatalogue
    from .classification_job_repository import ClassificationJobRepository

__all__ = [
    "CLASSIFICATION_READING_ROLE",
    "ClassificationJobEnqueuePorts",
    "ClassificationJobMovementSource",
    "ClassificationJobRepositoryFactory",
    "ClassificationLaneResolver",
]

CLASSIFICATION_READING_ROLE: Final = ModelRole.TEXT_EXTRACTION
"""The role a movement classification reads with, as the classification review's text reader names it."""


class ClassificationJobRepositoryFactory(Protocol):
    """Construct the classification job repository of one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ClassificationJobRepository:
        """Return the encrypted repository bound to ``bucket_id``."""
        ...


class ClassificationJobMovementSource(Protocol):
    """Read the transaction catalogue of the profile a job is enqueued for."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> TransactionCatalogue:
        """Return the profile's whole catalogue under the operation's pinned authority."""
        ...


class ClassificationLaneResolver(Protocol):
    """Resolve the lane the agent service would read with for ``role`` doing ``task_kind``.

    A refused lookup is raised as the ledger's typed reader refusal: no picked
    model, a model not installed, an unreachable service, each with the verdict
    the service gave. Nothing is sent to a model.
    """

    async def __call__(self, role: ModelRole, *, task_kind: ModelRunTaskKind) -> ModelRunLane:
        """Return the lane the person set for ``task_kind``, else the one ``role`` reads with, or raise its refusal."""
        ...


@dataclass(frozen=True, slots=True)
class ClassificationJobEnqueuePorts:
    """The repository, movement catalogue and lane lookup an enqueue reads and writes."""

    jobs: ClassificationJobRepositoryFactory
    movements: ClassificationJobMovementSource
    resolve_lane: ClassificationLaneResolver
