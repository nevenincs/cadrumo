"""Domain-level repository Protocols for the modelos aggregate.

Application-layer code that persists or loads modelo work-unit catalogues,
filing records, calculation results, or verification reports depends on these
Protocols, not on the concrete adapter-backed repository classes. This keeps
the domain layer free of adapter imports while still providing typed port surfaces.

The work-unit, calculation-revision, filing-record, and verification-report
protocols return :class:`WorkUnitCatalogue`,
:class:`CalculationRevisionCatalogue`, :class:`ModeloRecordCatalogue`, and
:class:`VerificationReportCatalogue` instances while keeping application code
independent of concrete storage adapters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ...core import Period
from ._calculation_revision import CalculationRevisionCatalogue
from ._filing_record import ModeloRecord, ModeloRecordCatalogue
from ._participation_index import TransactionRevisionParticipationIndex
from ._verification_report import VerificationReportCatalogue
from ._work_unit import WorkUnitCatalogue

if TYPE_CHECKING:
    from collections.abc import Callable

    # pragma: no cover - typing-only boundary DTO (lives in core, not adapters)
    from ...core import SecureObjectWrite


@runtime_checkable
class WorkUnitCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the work-unit catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`WorkUnitCatalogue` satisfies this protocol. The concrete
    secure-object-backed implementation is :class:`WorkUnitCatalogueRepository`.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a work-unit catalogue object has been persisted."""
        ...

    def load(self) -> WorkUnitCatalogue:
        """Return the persisted :class:`WorkUnitCatalogue` or an empty catalogue if absent."""
        ...

    def save(self, catalogue: WorkUnitCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...

    def mutate(self, mutation: Callable[[WorkUnitCatalogue], WorkUnitCatalogue]) -> WorkUnitCatalogue:
        """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work.

        Part of the port because the application NEEDS it, not merely because
        the adapter offers it: the catalogue is a singleton row, so any caller
        changing one work unit rewrites all of them, and doing that through
        ``save`` discards whatever a concurrent caller wrote. A stand-in that
        cannot offer this cannot stand in on those paths.
        """
        ...

    def save_with_secure_object_writes(
        self,
        catalogue: WorkUnitCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus co-emitted secure-object writes atomically."""
        ...

    def to_secure_object_write(self, catalogue: WorkUnitCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` for ``catalogue`` without committing it.

        Lets a mutation advance the work-unit pointer inside the same unit of
        work as the catalogues and lifecycle event the pointer names.
        """
        ...


@runtime_checkable
class CalculationRevisionCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for calculation revisions.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`CalculationRevisionCatalogue` satisfies this protocol.
    The concrete secure-object-backed implementation is
    :class:`CalculationRevisionCatalogueRepository`.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a calculation-revision catalogue object has been persisted."""
        ...

    def load(self) -> CalculationRevisionCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The :class:`CalculationRevisionCatalogue` loaded from storage.
        """
        ...

    def save(self, catalogue: CalculationRevisionCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...

    def to_secure_object_write(self, catalogue: CalculationRevisionCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` for ``catalogue`` without committing it."""
        ...

    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus co-emitted secure-object writes atomically."""
        ...


@runtime_checkable
class ModeloRecordCatalogueQueryProtocol(Protocol):
    """Query contract exposed by loaded modelo filing-record catalogues."""

    def current_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> ModeloRecord | None:
        """Return the current :class:`ModeloRecord` for a filing tuple and optional group member."""
        ...

    def history_for(
        self,
        *,
        bucket_id: str,
        modelo: str,
        filing_year: int,
        period: Period,
        member_nif: str | None = None,
    ) -> tuple[ModeloRecord, ...]:
        """Return :class:`ModeloRecord` filing history for a filing tuple and optional group member."""
        ...


@runtime_checkable
class ModeloRecordCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for modelo filing records.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`ModeloRecordCatalogue` satisfies this protocol. The
    concrete secure-object-backed implementation is
    :class:`ModeloRecordCatalogueRepository`. The loaded catalogue supports
    member-scoped ``current_for`` and ``history_for`` lookups for grupo fan-in
    filings.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a modelo-record catalogue object has been persisted."""
        ...

    def load(self) -> ModeloRecordCatalogue:
        """Return the persisted :class:`ModeloRecordCatalogue` or an empty catalogue if absent."""
        ...

    def save(self, catalogue: ModeloRecordCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...

    def mutate(self, mutation: Callable[[ModeloRecordCatalogue], ModeloRecordCatalogue]) -> ModeloRecordCatalogue:
        """Apply ``mutation`` to the stored catalogue as one revision-guarded unit of work.

        On the port because the application needs it: the catalogue is a
        singleton row, so stamping one record rewrites every other, and doing
        that through ``save`` discards whatever a concurrent caller wrote.
        """
        ...

    def to_secure_object_write(self, catalogue: ModeloRecordCatalogue) -> SecureObjectWrite:
        """Return the :class:`SecureObjectWrite` for ``catalogue`` without committing it."""
        ...

    def save_with_secure_object_writes(
        self,
        catalogue: ModeloRecordCatalogue,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        """Persist ``catalogue`` plus co-emitted secure-object writes atomically."""
        ...


@runtime_checkable
class VerificationReportCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for verification reports.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket :class:`VerificationReportCatalogue` satisfies this protocol.
    The concrete secure-object-backed implementation is
    :class:`VerificationReportCatalogueRepository`.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self) -> bool:
        """Return whether a verification-report catalogue object has been persisted."""
        ...

    def load(self) -> VerificationReportCatalogue:
        """Return the persisted catalogue or an empty catalogue if absent.

        Returns:
            The :class:`VerificationReportCatalogue` loaded from storage.
        """
        ...

    def save(self, catalogue: VerificationReportCatalogue) -> None:
        """Persist ``catalogue`` as the encrypted singleton object."""
        ...


@runtime_checkable
class TransactionParticipationIndexRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the participation index.

    The participation index is a per-transaction, derived-and-rebuildable
    read-side cache mapping a ledger transaction to the calculation revisions
    it participates in. Unlike the singleton catalogue repositories, its objects
    are keyed by ``transaction_id``. Any object that provides ``exists``,
    ``load``, and ``save`` over a
    :class:`TransactionRevisionParticipationIndex` satisfies this protocol; the
    concrete secure-object-backed implementation is
    :class:`TransactionParticipationIndexRepository`. Lifecycle correctness never
    depends on this cache's freshness — it is rebuilt from the revision
    catalogue — so the port is a navigation/read seam, not a source of truth.
    """

    @property
    def bucket_id(self) -> str | None:
        """Return the profile bucket id when this repository resolved one."""
        ...

    def exists(self, transaction_id: str) -> bool:
        """Return whether a participation-index object exists for ``transaction_id``."""
        ...

    def load(self, transaction_id: str) -> TransactionRevisionParticipationIndex:
        """Return the persisted index for ``transaction_id`` or an empty index if absent."""
        ...

    def save(self, index: TransactionRevisionParticipationIndex) -> None:
        """Persist ``index`` as the encrypted per-transaction object."""
        ...


__all__ = [
    "CalculationRevisionCatalogueRepositoryProtocol",
    "ModeloRecordCatalogueQueryProtocol",
    "ModeloRecordCatalogueRepositoryProtocol",
    "TransactionParticipationIndexRepositoryProtocol",
    "VerificationReportCatalogueRepositoryProtocol",
    "WorkUnitCatalogueRepositoryProtocol",
]
