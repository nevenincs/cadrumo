"""Domain-level repository Protocols for the modelos aggregate.

Application-layer code that persists or loads modelo work-unit catalogues,
filing records, calculation results, or verification reports depends on these
Protocols, not on the concrete adapter-backed repository classes. This keeps
the domain layer free of adapter imports while still providing typed port surfaces.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._calculation_revision import CalculationRevisionCatalogue
from ._filing_record import ModeloRecordCatalogue
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


@runtime_checkable
class ModeloRecordCatalogueRepositoryProtocol(Protocol):
    """Narrow domain-facing repository contract for modelo filing records.

    Any object that provides ``exists``, ``load``, and ``save`` over a
    per-bucket modelo-record catalogue satisfies this protocol. The
    concrete secure-object-backed implementation lives in
    ``_filing_repository.py``.
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
    "ModeloRecordCatalogueRepositoryProtocol",
    "VerificationReportCatalogueRepositoryProtocol",
    "WorkUnitCatalogueRepositoryProtocol",
]
