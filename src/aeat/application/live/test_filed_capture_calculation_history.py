"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from aeat.adapters.outbound.aeat.sede import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from aeat.application.calculations import CalculationObservationRepository, resolve_bindings_from_local_store
from aeat.core.config import override_settings
from aeat.core.resources import resources

from . import _persist_latest_filed_calculation_observations, persist_filed_calculation_observation

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CAPTURED_AT = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    provider = EphemeralMasterKeyProvider()
    with provider, override_settings(
        aeat_database_url=f"sqlite:///{(tmp_path / 'filed-calculation-history.db').as_posix()}",
        aeat_active_profile="operator",
    ) as settings:
        engine = get_engine(settings)
        SecureObjectRepository(engine=engine)
        try:
            yield
        finally:
            dispose_engine(settings)


def test_filed_observation_capture_promotes_previous_303_into_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(pending_compensation=Decimal("1200.00")),
            repository=repository,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
        prefill = resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)

        assert calculation_key == "303:2026:1T"
        assert repository.load("303", 2026, "1T") is not None
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_periods == ("1T",)


def test_filed_observation_capture_promotes_cross_year_303_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(
                year=2025,
                period="4T",
                pending_compensation=Decimal("450.00"),
                expediente_id="202530313529999Z",
            ),
            repository=repository,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
        prefill = resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)

        assert calculation_key == "303:2025:4T"
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
        assert prefill.prefilled[0].source_filing_year == 2025
        assert prefill.prefilled[0].source_periods == ("4T",)


def test_duplicate_period_capture_promotes_latest_filing_to_calculation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        _persist_latest_filed_calculation_observations(
            (
                _prior_303_observation(
                    expediente_id="202630313520001A",
                    pending_compensation=Decimal("800.00"),
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    expediente_id="202630313520002B",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            )
        )

        stored = repository.load("303", 2026, "1T")

        assert stored is not None
        assert stored.observation.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("1200.00")


def _prior_303_observation(
    *,
    pending_compensation: Decimal,
    year: int = 2026,
    period: str = "1T",
    expediente_id: str = "202630313522222A",
    presented_at: datetime = _CAPTURED_AT,
) -> FiledDeclaracionObservation:
    body = f"303-{year}-{period}-submitted-file".encode("ascii")
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=year,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/SCEJ-MANT/CONSUL/index.zul"),
                content_type="application/octet-stream",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=_CAPTURED_AT,
            ),
        ),
        casillas=(
            ObservedCasillaValue(
                casilla_id="87",
                value=str(pending_compensation),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:87",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id="69",
                value="0.00",
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:69",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id=f"303:2009-y-siguientes:{year}:{period}",
    )
