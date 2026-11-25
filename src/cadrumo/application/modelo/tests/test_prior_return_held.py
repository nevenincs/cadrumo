"""The previous ejercicio's return is held when it was captured as filed or recorded as filed here.

Pure lookup logic: the observation store and the filing-record catalogue are
in-memory stand-ins that hold chosen coordinates and record what was asked.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..prior_return_held import prior_return_held

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "bucket"
_MODELO = "100"
_YEAR = filing_year_envelope().years[-1]
_PERIOD = Period.from_year_and_code(_YEAR, "0A")
_PREVIOUS = Period.from_year_and_code(_YEAR - 1, "0A")


@dataclass
class _Observations:
    held: frozenset[tuple[str, Period]] = frozenset()
    asked: list[tuple[str, Period]] = field(default_factory=list)

    def load_observation(self, modelo: str, period: Period, /) -> object | None:
        self.asked.append((modelo, period))
        return object() if (modelo, period) in self.held else None


@dataclass
class _Catalogue:
    held: frozenset[tuple[str, str, int, Period]]
    asked: list[tuple[str, str, int, Period]]

    def current_for(self, *, bucket_id: str, modelo: str, filing_year: int, period: Period) -> object | None:
        key = (bucket_id, modelo, filing_year, period)
        self.asked.append(key)
        return object() if key in self.held else None


@dataclass
class _Records:
    held: frozenset[tuple[str, str, int, Period]] = frozenset()
    asked: list[tuple[str, str, int, Period]] = field(default_factory=list)

    def load(self) -> _Catalogue:
        return _Catalogue(held=self.held, asked=self.asked)


def _held(observations: _Observations, records: _Records) -> bool:
    return prior_return_held(
        bucket_id=_BUCKET,
        modelo=_MODELO,
        period=_PERIOD,
        observation_repository=observations,
        filing_repository=records,
    )


def test_a_captured_return_of_the_previous_ejercicio_is_held() -> None:
    observations = _Observations(held=frozenset({(_MODELO, _PREVIOUS)}))
    records = _Records()

    assert _held(observations, records) is True
    assert observations.asked == [(_MODELO, _PREVIOUS)]
    assert records.asked == []


def test_a_return_recorded_as_filed_for_the_previous_ejercicio_is_held() -> None:
    observations = _Observations()
    records = _Records(held=frozenset({(_BUCKET, _MODELO, _YEAR - 1, _PREVIOUS)}))

    assert _held(observations, records) is True
    assert records.asked == [(_BUCKET, _MODELO, _YEAR - 1, _PREVIOUS)]


def test_a_return_of_the_same_ejercicio_or_another_modelo_is_not_the_previous_one() -> None:
    observations = _Observations(held=frozenset({(_MODELO, _PERIOD), ("130", _PREVIOUS)}))
    records = _Records(held=frozenset({(_BUCKET, _MODELO, _YEAR, _PERIOD), ("other", _MODELO, _YEAR - 1, _PREVIOUS)}))

    assert _held(observations, records) is False
