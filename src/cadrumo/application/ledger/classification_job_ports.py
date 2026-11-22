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

A run reads each movement through the same classification reader the review
asks, composed for the job's lane and consent. A lane that reads off this
computer is read only under a grant the consent ledger still holds: not
revoked, in scope, and for the job's lane and the classification task kind.
Each read mints its own consent bound to the revision of the movement it sends.

An apply writes each accepted proposal through the ledger's own action ports,
the ones the reviewed classification writes through.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunTaskKind

    from ...core.config import Settings
    from ...core.model_roles import ModelRole
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.evidence_consent.grant import ConsentGrantStanding
    from ...domain.transactions.classification_job import (
        ClassificationConsentScope,
        ClassificationJobConsent,
        ClassificationJobLane,
    )
    from ...domain.transactions.models import TransactionCatalogue
    from .action_ports import LedgerActionPortsFactory
    from .classification_job_repository import ClassificationJobRepository
    from .llm_classification_ports import LLMClassificationPorts
    from .protocols import TransactionCatalogueCoCommitWriterProtocol

__all__ = [
    "ClassificationConsentGrants",
    "ClassificationJobApplyPorts",
    "ClassificationJobConsentPorts",
    "ClassificationJobEnqueuePorts",
    "ClassificationJobMovementSource",
    "ClassificationJobReader",
    "ClassificationJobReaderFactory",
    "ClassificationJobRepositoryFactory",
    "ClassificationJobRunPorts",
    "ClassificationLaneResolver",
]


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


class ClassificationConsentGrants(Protocol):
    """Record, find, check and revoke a person's grants of off-host classification reads in the consent ledger.

    Every grant is bound to the profile, the lane (provider, transport and
    model) and the classification task kind. The ledger is the only source:
    a job holds a grant's reference, never the grant.
    """

    def grant(
        self,
        *,
        bucket_id: str,
        lane: ClassificationJobLane,
        scope: ClassificationConsentScope,
        job_id: str,
        surface: str,
    ) -> ClassificationJobConsent:
        """Record the person's grant for ``lane`` and return the consent a job holds for it.

        Raises:
            LedgerOffHostConsentRequiredError: A standing bar refuses off-host
                reads for this profile, so no grant is recorded.
        """
        ...

    def standing_grant(self, *, bucket_id: str, lane: ClassificationJobLane) -> ClassificationJobConsent | None:
        """Return the newest remembered grant, or grant for the agent session open now, that covers ``lane``."""
        ...

    def standing(
        self, *, bucket_id: str, lane: ClassificationJobLane, consent: ClassificationJobConsent, job_id: str
    ) -> ConsentGrantStanding:
        """Return whether the grant ``consent`` names covers a read by ``job_id`` on ``lane`` now."""
        ...

    def revoke(self, *, bucket_id: str, consent: ClassificationJobConsent, surface: str) -> bool:
        """Withdraw the grant ``consent`` names; ``False`` when the ledger holds no such grant or it was revoked."""
        ...


@dataclass(frozen=True, slots=True)
class ClassificationJobEnqueuePorts:
    """The repository, movement catalogue, lane lookup and consent ledger an enqueue reads and writes."""

    jobs: ClassificationJobRepositoryFactory
    movements: ClassificationJobMovementSource
    resolve_lane: ClassificationLaneResolver
    consent: ClassificationConsentGrants


@dataclass(frozen=True, slots=True)
class ClassificationJobConsentPorts:
    """The repository, lane lookup and consent ledger an authorise or a revoke reads and writes."""

    jobs: ClassificationJobRepositoryFactory
    resolve_lane: ClassificationLaneResolver
    consent: ClassificationConsentGrants


@dataclass(frozen=True, slots=True)
class ClassificationJobReader:
    """The profile's movements and the classification reader one run reads them with.

    ``llm_for`` composes the reader for one read, given the content address of
    what it sends: the revision of the movement. A lane that reads off this
    computer binds that read's own consent to it; any other lane ignores it.
    """

    transactions: TransactionCatalogueCoCommitWriterProtocol
    llm_for: Callable[[str], LLMClassificationPorts]
    settings: Settings


class ClassificationJobReaderFactory(Protocol):
    """Compose the reader a job's run reads with, for the job's own lane and consent."""

    def __call__(
        self,
        *,
        bucket_id: str,
        operation: PinnedAuthorityOperation,
        lane: ClassificationJobLane,
        consent: ClassificationJobConsent | None,
        job_id: str,
    ) -> ClassificationJobReader:
        """Return the profile's reader for the job's lane and grant.

        On a lane that reads off this computer each read mints its own consent
        from the job's grant, checked against the consent ledger when it is
        made; a read the grant no longer covers is refused there.

        Raises:
            LedgerOffHostConsentRequiredError: The lane reads off this computer
                and the job's consent cannot be bound to a read; the refusal
                carries both remedies.
        """
        ...


@dataclass(frozen=True, slots=True)
class ClassificationJobRunPorts:
    """The repository a run reads and writes the job through, the reader, the lane lookup and the consent ledger."""

    jobs: ClassificationJobRepositoryFactory
    readers: ClassificationJobReaderFactory
    resolve_lane: ClassificationLaneResolver
    consent: ClassificationConsentGrants


@dataclass(frozen=True, slots=True)
class ClassificationJobApplyPorts:
    """The repository an apply reads and marks the job through, and the ledger it writes accepted proposals to."""

    jobs: ClassificationJobRepositoryFactory
    ledger: LedgerActionPortsFactory
