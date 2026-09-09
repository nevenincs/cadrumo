"""Encrypted-SQL round-trip assertions shared by multi-year fidelity suites."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from ....tests.registry_observations import revision_id_for_observation
from ....tests.secure_sql import isolated_runtime_profile
from ..observations_repository import CalculationObservationRepository

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from ....domain.calculations.registry.bindings import RegistryModeloObservation
    from ..observations_repository import ObservationEnvelopePayload


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


def _assert_ejercicio_round_trip(
    repository: CalculationObservationRepository,
    *,
    modelo: str,
    period: str,
    observation: RegistryModeloObservation,
    filing_year: int,
    captured_at: datetime,
    year_label: str,
) -> ObservationEnvelopePayload:
    repository.save(
        repository.prepare_observation_envelope(
            observation,
            source_kind="app_filing",
            captured_at=captured_at,
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )
    loaded = _find_modelo_observation(
        repository,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
    )
    assert loaded is not None, (
        f"{year_label} observation not found for ({modelo!r}, {filing_year}, {period!r}) after save"
    )
    assert loaded.observation == observation, (
        f"{modelo} {year_label} observation did not survive the encrypted-SQL roundtrip; "
        "at least one casilla was silently dropped, coerced, or defaulted away"
    )
    assert loaded.source_kind == "app_filing"
    assert loaded.captured_at == captured_at
    return loaded


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
            loaded_n = _assert_ejercicio_round_trip(
                repository,
                modelo=modelo,
                period=period,
                observation=obs_n,
                filing_year=year_n,
                captured_at=clock_n,
                year_label="year-N",
            )

        if stage in ("year_n_plus_1", "both"):
            loaded_n_plus_1 = _assert_ejercicio_round_trip(
                repository,
                modelo=modelo,
                period=period,
                observation=obs_n_plus_1,
                filing_year=year_n_plus_1,
                captured_at=clock_n_plus_1,
                year_label="year-N+1",
            )

        return loaded_n, loaded_n_plus_1


__all__ = ["assert_two_ejercicio_round_trip"]
