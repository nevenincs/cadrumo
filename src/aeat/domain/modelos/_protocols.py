"""Domain-level repository Protocols for the modelos aggregate.

Application-layer code that persists or loads modelo work-unit catalogues,
filing records, calculation results, or verification reports depends on these
Protocols, not on the concrete adapter-backed repository classes. This keeps
the domain layer free of adapter imports while still providing typed port surfaces.

Use of :class:`ModeloRecord` for compliance.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...core import Period
from ._calculation_revision import CalculationRevisionCatalogue
from ._filing_record import ModeloRecord, ModeloRecordCatalogue
from ._verification_report import VerificationReportCatalogue
from ._work_unit import WorkUnitCatalogue


@runtime_checkable
class WorkUnitCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for the work-unit catalogue.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket work-unit catalogue satisfies this protocol. The concrete
    secure-object-backed implementation lives in ``_repository.py``.
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


@runtime_checkable
class CalculationRevisionCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for calculation revisions.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket calculation-revision catalogue satisfies this protocol.
    The concrete secure-object-backed implementation lives in
    ``_calculation_repository.py``.
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

    def save_with_secure_object_writes(
        self,
        catalogue: CalculationRevisionCatalogue,
        extra_writes: tuple[object, ...],
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
    per-bucket modelo-record catalogue satisfies this protocol. The
    concrete secure-object-backed implementation lives in
    ``_filing_repository.py``. The loaded catalogue supports member-scoped
    ``current_for`` and ``history_for`` lookups for grupo fan-in filings.
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


@runtime_checkable
class VerificationReportCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for verification reports.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket verification-report catalogue satisfies this protocol.
    The concrete secure-object-backed implementation lives in
    ``_verification_repository.py``.
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


__all__ = [
    "CalculationRevisionCatalogueRepositoryProtocol",
    "ModeloRecordCatalogueQueryProtocol",
    "ModeloRecordCatalogueRepositoryProtocol",
    "VerificationReportCatalogueRepositoryProtocol",
    "WorkUnitCatalogueRepositoryProtocol",
]
