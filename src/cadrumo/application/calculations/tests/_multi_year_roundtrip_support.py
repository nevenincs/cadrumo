"""Encrypted-SQL round-trip assertions shared by multi-year fidelity suites."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ....tests.secure_sql import isolated_runtime_profile
from .._observations_repository import CalculationObservationRepository

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
    from .._observations_repository import ObservationEnvelopePayload


def _find_modelo_observation(
    repo: CalculationObservationRepository,
    *,
    modelo: str,
    filing_year: int,
    period: str,
) -> ObservationEnvelopePayload | None:
    """Return the encrypted envelope matching one filing identity."""
    for payload in repo.iter_modelo(modelo):
        observation = payload.observation
        if observation.filing_year == filing_year and observation.period == period:
            return payload
    return None


def assert_two_ejercicio_round_trip(
    *,
    tmp_path: Path,
    stage: Literal["year_n", "year_n_plus_1", "both"],
    modelo: str,
    period: str,
    obs_n: RegistryModeloObservation,
    obs_n_plus_1: RegistryModeloObservation,
    year_n: int,
    year_n_plus_1: int,
    clock_n: datetime,
    clock_n_plus_1: datetime,
) -> tuple[ObservationEnvelopePayload | None, ObservationEnvelopePayload | None]:
    """Persist the selected years and prove strict payload and provenance equality."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        loaded_n: ObservationEnvelopePayload | None = None
        loaded_n_plus_1: ObservationEnvelopePayload | None = None

        if stage in ("year_n", "both"):
            repository.save(
                repository.prepare_observation_envelope(
                    obs_n,
                    source_kind="app_filing",
                    captured_at=clock_n,
                )
            )
            loaded_n = _find_modelo_observation(
                repository,
                modelo=modelo,
                filing_year=year_n,
                period=period,
            )
            assert loaded_n is not None, (
                f"year-N observation not found for ({modelo!r}, {year_n}, {period!r}) after save"
            )
            assert loaded_n.observation == obs_n, (
                f"{modelo} year-N observation did not survive the encrypted-SQL roundtrip; "
                "at least one casilla was silently dropped, coerced, or defaulted away"
            )
            assert loaded_n.source_kind == "app_filing"
            assert loaded_n.captured_at == clock_n

        if stage in ("year_n_plus_1", "both"):
            repository.save(
                repository.prepare_observation_envelope(
                    obs_n_plus_1,
                    source_kind="app_filing",
                    captured_at=clock_n_plus_1,
                )
            )
            loaded_n_plus_1 = _find_modelo_observation(
                repository,
                modelo=modelo,
                filing_year=year_n_plus_1,
                period=period,
            )
            assert loaded_n_plus_1 is not None, (
                f"year-N+1 observation not found for ({modelo!r}, {year_n_plus_1}, {period!r}) after save"
            )
            assert loaded_n_plus_1.observation == obs_n_plus_1, (
                f"{modelo} year-N+1 observation did not survive the encrypted-SQL roundtrip; "
                "at least one casilla was silently dropped, coerced, or defaulted away"
            )
            assert loaded_n_plus_1.source_kind == "app_filing"
            assert loaded_n_plus_1.captured_at == clock_n_plus_1

        return loaded_n, loaded_n_plus_1


__all__ = ["assert_two_ejercicio_round_trip"]
