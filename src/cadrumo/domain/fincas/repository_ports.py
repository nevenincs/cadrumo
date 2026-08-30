"""Read-side repository ports for rental-register aggregation.

These :class:`~typing.Protocol` declarations are the hexagonal boundary
between the pure :mod:`domain.fincas` aggregation logic and the
ORM-backed concrete repositories that live in the persistence adapter
(:mod:`adapters.persistence.profile.fincas`). The aggregation
functions in :mod:`._aggregates` annotate against these ports and depend
only on the read methods they call, never on SQLAlchemy or the storage
mapper rows — keeping the domain layer free of adapter coupling.

The concrete adapter repositories satisfy these ports structurally; no
explicit subclassing is required. Each port declares exactly the read
method the aggregation pipeline consumes (interface segregation), so a
port change is a real change to what the domain needs.

The port set is :class:`FincaReader`, :class:`ArrendamientoReader`,
:class:`FincaRendimientoReader`, :class:`FincaGastoReader`, and
:class:`FincaAmortizacionLedgerReader`; each returns the corresponding
:class:`Finca`, :class:`Arrendamiento`, :class:`FincaRendimientoRecord`,
:class:`FincaGasto`, or :class:`FincaAmortizacionLedgerEntry` record. The
adapter implementations are
:class:`~adapters.persistence.profile.fincas.FincaRepository`,
:class:`~adapters.persistence.profile.fincas.ArrendamientoRepository`,
:class:`~adapters.persistence.profile.fincas.FincaRendimientoRepository`,
:class:`~adapters.persistence.profile.fincas.FincaGastoRepository`, and
:class:`~adapters.persistence.profile.fincas.FincaAmortizacionLedgerRepository`.
"""

from __future__ import annotations

from typing import Protocol

from .models import (
    Arrendamiento,
    Finca,
    FincaAmortizacionLedgerEntry,
    FincaGasto,
    FincaRendimientoRecord,
)


class FincaReader(Protocol):
    """Read port over the :class:`Finca` register."""

    def list_all(self) -> list[Finca]:
        """Return every persisted :class:`Finca` record."""
        ...


class ArrendamientoReader(Protocol):
    """Read port over the :class:`Arrendamiento` (rental contract) register."""

    def list_for_finca(self, finca_id: int) -> list[Arrendamiento]:
        """Return every :class:`Arrendamiento` attached to ``finca_id``."""
        ...


class FincaRendimientoReader(Protocol):
    """Read port over the :class:`FincaRendimientoRecord` income register."""

    def get_for_contract_period(
        self,
        contract_id: int,
        period_year: int,
    ) -> FincaRendimientoRecord | None:
        """Return the :class:`FincaRendimientoRecord` for ``contract_id`` in ``period_year``, or ``None``."""
        ...


class FincaGastoReader(Protocol):
    """Read port over the :class:`FincaGasto` expense register."""

    def list_for_finca_period(self, finca_id: int, period_year: int) -> list[FincaGasto]:
        """Return every :class:`FincaGasto` for ``finca_id`` within ``period_year``."""
        ...


class FincaAmortizacionLedgerReader(Protocol):
    """Read port over the :class:`FincaAmortizacionLedgerEntry` ledger."""

    def list_for_finca(self, finca_id: int) -> list[FincaAmortizacionLedgerEntry]:
        """Return every :class:`FincaAmortizacionLedgerEntry` attached to ``finca_id``."""
        ...


__all__ = [
    "ArrendamientoReader",
    "FincaAmortizacionLedgerReader",
    "FincaGastoReader",
    "FincaReader",
    "FincaRendimientoReader",
]
