"""Narrow Protocol surfaces for rental-register repository consumers.

These Protocols capture only the repository surface that
:mod:`aeat.domain.fincas._aggregates` and sibling domain modules
consume, decoupling the aggregation logic from the concrete
SQLAlchemy-session-backed repository classes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ._models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)


@runtime_checkable
class FincaRepositoryProtocol(Protocol):
    """Narrow repository surface for :class:`Finca` records."""

    def list_all(self) -> list[Finca]:
        """Return every finca in the register, ordered by surrogate id."""
        ...

    def get(self, record_id: int) -> Finca:
        """Return the finca with surrogate id ``record_id``."""
        ...

    def get_by_identifier(self, identifier: str) -> Finca | None:
        """Return the finca matching ``identifier``, or ``None`` if absent."""
        ...

    def upsert(self, record: Finca) -> Finca:
        """Insert or update ``record`` and return the persisted entity."""
        ...

    def delete(self, record_id: int) -> None:
        """Delete the finca with surrogate id ``record_id``."""
        ...


@runtime_checkable
class ArrendamientoRepositoryProtocol(Protocol):
    """Narrow repository surface for :class:`Arrendamiento` records."""

    def list_all(self) -> list[Arrendamiento]:
        """Return every rental contract in the register."""
        ...

    def list_for_finca(self, finca_id: int) -> list[Arrendamiento]:
        """Return every contract attached to the supplied finca."""
        ...

    def get(self, record_id: int) -> Arrendamiento:
        """Return the contract with surrogate id ``record_id``."""
        ...

    def upsert(self, record: Arrendamiento) -> Arrendamiento:
        """Insert or update ``record`` and return the persisted entity."""
        ...

    def delete(self, record_id: int) -> None:
        """Delete the contract with surrogate id ``record_id``."""
        ...


@runtime_checkable
class FincaRendimientoRepositoryProtocol(Protocol):
    """Narrow repository surface for :class:`FincaRendimientoRecord` records."""

    def list_for_period(self, period_year: int) -> list[FincaRendimientoRecord]:
        """Return every income record overlapping ``period_year``."""
        ...

    def get_for_contract_period(
        self,
        contract_id: int,
        period_year: int,
    ) -> FincaRendimientoRecord | None:
        """Return the income record for ``contract_id`` and ``period_year``, or ``None``."""
        ...

    def upsert(self, record: FincaRendimientoRecord) -> FincaRendimientoRecord:
        """Insert or update ``record`` and return the persisted entity."""
        ...

    def delete(self, record_id: int) -> None:
        """Delete the income record with surrogate id ``record_id``."""
        ...


@runtime_checkable
class FincaGastoRepositoryProtocol(Protocol):
    """Narrow repository surface for :class:`FincaGasto` records."""

    def list_for_finca_period(self, finca_id: int, period_year: int) -> list[FincaGasto]:
        """Return every expense attached to ``finca_id`` within ``period_year``."""
        ...

    def add(self, record: FincaGasto) -> FincaGasto:
        """Insert ``record`` and return the persisted entity."""
        ...

    def upsert(self, record: FincaGasto) -> FincaGasto:
        """Insert or update ``record`` and return the persisted entity."""
        ...

    def delete(self, record_id: int) -> None:
        """Delete the expense with surrogate id ``record_id``."""
        ...


@runtime_checkable
class FincaAmortizacionLedgerRepositoryProtocol(Protocol):
    """Narrow repository surface for :class:`FincaAmortizacionLedgerEntry` records."""

    def list_for_finca(self, finca_id: int) -> list[FincaAmortizacionLedgerEntry]:
        """Return every ledger entry attached to ``finca_id``."""
        ...

    def get_for_finca_period(
        self,
        finca_id: int,
        period_year: int,
    ) -> FincaAmortizacionLedgerEntry | None:
        """Return the ledger entry for ``finca_id`` and ``period_year``, or ``None``."""
        ...

    def upsert(self, record: FincaAmortizacionLedgerEntry) -> FincaAmortizacionLedgerEntry:
        """Insert or update ``record`` and return the persisted entity."""
        ...

    def delete(self, record_id: int) -> None:
        """Delete the ledger entry with surrogate id ``record_id``."""
        ...


__all__ = [
    "ArrendamientoRepositoryProtocol",
    "FincaAmortizacionLedgerRepositoryProtocol",
    "FincaGastoRepositoryProtocol",
    "FincaRendimientoRepositoryProtocol",
    "FincaRepositoryProtocol",
]
