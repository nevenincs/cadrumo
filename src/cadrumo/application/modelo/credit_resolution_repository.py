"""Application-owned capabilities for the operator's acceptances of disputed Modelo figures.

The application owns the key grammar, the read capability the gate and the
calculation use, and the one guarded write path for accepting and revoking. The
encrypted implementation is bound by an outer composition root. Nothing here
logs an amount or the operator's reason.

A row is stored under ``credit-resolution:{modelo}:{filing_year}:{period}:{finding_key}``.
The finding key digests every source's value, the registry revision and the
declaration compared, so the key names one exact disagreement: a recalculation
that reproduces it finds the same row, and any changed amount finds none.

The write refuses, before anything is stored:

* a second active resolution of the same finding, and a revocation of one that is
  not active;
* a resolution whose row is no longer at the revision the write was prepared
  against.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal, Protocol

from ...core.errors.hierarchy import CadrumoError
from ...core.filing_year import FilingYear
from ...core.time.utc import UtcInstant
from ...domain.modelos.credit_resolution import CreditResolutionIdentity, CreditResolutionRecord
from ..aggregation.observation_key_component import validate_observation_key_component

__all__ = [
    "CREDIT_RESOLUTION_KEY_PREFIX",
    "CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS",
    "CreditResolutionPersistenceError",
    "CreditResolutionReader",
    "CreditResolutionRefusalReason",
    "CreditResolutionRefusedError",
    "CreditResolutionRepository",
    "CreditResolutionRevisionConflictError",
    "credit_resolution_key",
    "revoke_credit_resolution",
    "store_credit_resolution",
]

CREDIT_RESOLUTION_KEY_PREFIX: Final = "credit-resolution:"
"""The key prefix every resolution row of the namespace carries."""


def credit_resolution_key(identity: CreditResolutionIdentity) -> str:
    """Return the object key ``credit-resolution:{modelo}:{filing_year}:{period}:{finding_key}``."""
    modelo, filing_year, period, finding_key = identity
    validate_observation_key_component(modelo, context="modelo")
    validate_observation_key_component(period, context="period")
    validate_observation_key_component(finding_key, context="finding_key")
    return f"{CREDIT_RESOLUTION_KEY_PREFIX}{modelo}:{int(filing_year)}:{period}:{finding_key}"


class CreditResolutionPersistenceError(CadrumoError):
    """Translated failure from the credit resolution persistence port."""

    def __init__(self, operation: str) -> None:
        """Carry only the application operation, never storage details or record content."""
        self.operation = operation
        super().__init__(f"credit resolution persistence operation failed: {operation}")


class CreditResolutionRevisionConflictError(CadrumoError):
    """The stored row moved since the revision the write was prepared against."""

    def __init__(self) -> None:
        """Say only that the revision is stale; the row is named by nothing identifying."""
        super().__init__(
            "the credit resolution changed since it was read",
            translated_message="application.modelo.credit_resolution.errors.stale_revision",
        )


type CreditResolutionRefusalReason = Literal[
    "already_resolved", "not_resolved", "unknown_finding", "calculation_not_current"
]
"""Why a resolution or its revocation was refused before it reached storage."""

CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "already_resolved": "application.modelo.credit_resolution.errors.already_resolved",
        "not_resolved": "application.modelo.credit_resolution.errors.not_resolved",
        "unknown_finding": "application.modelo.credit_resolution.errors.unknown_finding",
        "calculation_not_current": "application.modelo.credit_resolution.errors.calculation_not_current",
        "stale_revision": "application.modelo.credit_resolution.errors.stale_revision",
    }
)
"""The worded message of each refusal reason, the stale revision of a guarded write included."""


class CreditResolutionRefusedError(CadrumoError):
    """A resolution or revocation the write path refuses to store."""

    def __init__(self, reason: CreditResolutionRefusalReason) -> None:
        """Name the refusal and nothing of the figure or the operator's reason."""
        self.reason: CreditResolutionRefusalReason = reason
        super().__init__(
            f"credit resolution refused: {reason}",
            context={"reason": reason},
            translated_message=CREDIT_RESOLUTION_MESSAGE_LOCALE_KEYS[reason],
        )


class CreditResolutionReader(Protocol):
    """The read capability the gate, the form and the calculation use."""

    def load_for_work(self, *, modelo: str, filing_year: FilingYear, period: str) -> tuple[CreditResolutionRecord, ...]:
        """Return every resolution of one declaration, active or revoked, ordered by object key.

        Raises:
            CreditResolutionPersistenceError: Storage could not be read. A caller
                never reads that as an empty store.
        """
        ...


class CreditResolutionRepository(CreditResolutionReader, Protocol):
    """The read and guarded-write capability over the resolution rows."""

    def load_revisioned(self, identity: CreditResolutionIdentity) -> tuple[CreditResolutionRecord | None, str]:
        """Return the stored resolution at ``identity`` and the exact revision it was read at.

        An absent row returns ``None`` beside the absent-row revision sentinel.
        """
        ...

    def list_revisioned(
        self, *, modelo: str, filing_year: FilingYear, period: str
    ) -> tuple[tuple[CreditResolutionRecord, str], ...]:
        """Return every resolution of one declaration beside the revision it was read at, ordered by object key."""
        ...

    def save_revisioned(self, record: CreditResolutionRecord, *, expected_revision_id: str) -> str:
        """Store ``record`` only if its row is still at ``expected_revision_id``; return the new revision.

        Raises:
            CreditResolutionRevisionConflictError: The row moved.
        """
        ...


def store_credit_resolution(
    record: CreditResolutionRecord, *, repository: CreditResolutionRepository, expected_revision_id: str
) -> str:
    """Store one active resolution and return the revision it was stored at.

    ``expected_revision_id`` is the absent-row sentinel for a first resolution, or
    the revision of a revoked one it replaces.

    Raises:
        CreditResolutionRefusedError: The record is not active, or the finding already holds an active resolution.
        CreditResolutionRevisionConflictError: The row is no longer at ``expected_revision_id``.
        CreditResolutionPersistenceError: Storage failed.
    """
    if not record.active:
        raise CreditResolutionRefusedError("not_resolved")
    stored, current_revision_id = repository.load_revisioned(record.identity)
    if current_revision_id != expected_revision_id:
        raise CreditResolutionRevisionConflictError
    if stored is not None and stored.active:
        raise CreditResolutionRefusedError("already_resolved")
    return repository.save_revisioned(record, expected_revision_id=expected_revision_id)


def revoke_credit_resolution(
    identity: CreditResolutionIdentity,
    *,
    at: UtcInstant,
    by_session: str,
    repository: CreditResolutionRepository,
    expected_revision_id: str,
) -> tuple[CreditResolutionRecord, str]:
    """Take back the active resolution at ``identity``; return it revoked and its new revision.

    Raises:
        CreditResolutionRefusedError: No active resolution is stored there.
        CreditResolutionRevisionConflictError: The row is no longer at ``expected_revision_id``.
        CreditResolutionPersistenceError: Storage failed.
    """
    stored, current_revision_id = repository.load_revisioned(identity)
    if current_revision_id != expected_revision_id:
        raise CreditResolutionRevisionConflictError
    if stored is None or not stored.active:
        raise CreditResolutionRefusedError("not_resolved")
    revoked = stored.revoked(at, by_session=by_session)
    return revoked, repository.save_revisioned(revoked, expected_revision_id=expected_revision_id)
