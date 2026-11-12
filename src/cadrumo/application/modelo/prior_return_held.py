"""Whether the profile holds the return the previous ejercicio filed, of the same modelo and period."""

from __future__ import annotations

from typing import Protocol

from ...core.period import Period


class FiledObservationReader(Protocol):
    """The filed-observation store, as far as a held return is concerned."""

    def load_observation(self, modelo: str, period: Period, /) -> object | None:
        """Load the effective filed observation of one single-filer coordinate."""
        ...


class FilingRecordLookup(Protocol):
    """The loaded filing-record catalogue, as far as a held return is concerned."""

    def current_for(self, *, bucket_id: str, modelo: str, filing_year: int, period: Period) -> object | None:
        """Return the current filing record of one coordinate, or ``None`` when none was recorded."""
        ...


class FilingRecordReader(Protocol):
    """The filing-record store, as far as a held return is concerned."""

    def load(self) -> FilingRecordLookup:
        """Return the profile's filing-record catalogue."""
        ...


def prior_return_held(
    *,
    bucket_id: str,
    modelo: str,
    period: Period,
    observation_repository: FiledObservationReader,
    filing_repository: FilingRecordReader,
) -> bool:
    """Return whether a return of ``modelo`` for the ejercicio before ``period``'s is held.

    A held return is either a filed return the profile captured or imported, or
    one the application recorded as filed. Holding it says nothing of what it
    states; a reader still has to match its boxes to what it needs.
    """
    previous = Period.from_year_and_code(period.filing_year - 1, period.code)
    if observation_repository.load_observation(modelo, previous) is not None:
        return True
    current = filing_repository.load().current_for(
        bucket_id=bucket_id, modelo=modelo, filing_year=previous.filing_year, period=previous
    )
    return current is not None


__all__ = ["FiledObservationReader", "FilingRecordLookup", "FilingRecordReader", "prior_return_held"]
