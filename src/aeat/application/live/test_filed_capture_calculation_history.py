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
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine, get_engine
from aeat.application.calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    IvaCompensationPeriodState,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from aeat.core.config import override_settings
from aeat.core.resources import resources
from aeat.domain.calculations.registry import CasillaObservation, RegistryModeloObservation, RegistryValidationError

from . import (
    _latest_declarations_by_period,
    _persist_iva_compensation_history_observations_strict,
    _persist_latest_filed_calculation_observations,
    list_iva_compensation_history,
    persist_filed_calculation_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_CAPTURED_AT = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
_SYNTHETIC_PROFILE_ID = "SYNTHETIC_PROFILE"
_SYNTHETIC_EXPEDIENTE_ID = "200030300000000Z"


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[Path]:
    provider = EphemeralMasterKeyProvider()
    db_path = tmp_path / "filed-calculation-history.db"
    with provider, override_settings(
        aeat_database_url=f"sqlite:///{db_path.as_posix()}",
        aeat_active_profile="operator",
    ) as settings:
        engine = get_engine(settings)
        SecureObjectRepository(engine=engine)
        try:
            yield db_path
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
        recurrence, recurrence_prefill = extract_modelo_303_local_iva_compensation_recurrence(
            target_snapshot,
            repository=repository,
            captured_at=_CAPTURED_AT,
        )

        assert calculation_key == "303:2026:1T"
        assert repository.load("303", 2026, "1T") is not None
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_periods == ("1T",)
        assert recurrence is not None
        assert recurrence.amount == Decimal("1200.00")
        assert recurrence.source_periods == ("1T",)
        assert recurrence_prefill.binding_values == prefill.binding_values


def test_filed_observation_capture_promotes_cross_year_303_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(
                year=2025,
                period="4T",
                pending_compensation=Decimal("450.00"),
                expediente_id="200030300000001Z",
            ),
            repository=repository,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
        prefill = resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)

        assert calculation_key == "303:2025:4T"
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
        assert prefill.prefilled[0].source_filing_year == 2025
        assert prefill.prefilled[0].source_periods == ("4T",)


def test_binding_prefill_uses_profile_secure_iva_compensation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        history_repository = IvaCompensationHistoryRepository()
        history_repository.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif=_SYNTHETIC_PROFILE_ID,
                filing_year=2026,
                period="1T",
                expediente_id=_SYNTHETIC_EXPEDIENTE_ID,
                status="ALTA",
                presented_at=_CAPTURED_AT,
                prior_pending_amount=Decimal("2.34"),
                applied_amount=Decimal("1.23"),
                pending_for_later_amount=Decimal("8.90"),
                period_result_amount=Decimal("-4.32"),
                final_result_amount=Decimal("-4.32"),
                generated_amount=Decimal("4.32"),
                available_end_amount=Decimal("13.22"),
                source_observation_key=f"303:2026:1T:{_SYNTHETIC_EXPEDIENTE_ID}",
                source_artefact_sha256=hashlib.sha256(b"synthetic-submitted-file").hexdigest(),
            )
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
        prefill = resolve_bindings_from_local_store(
            target_snapshot,
            repository=repository,
            iva_history_repository=history_repository,
            captured_at=_CAPTURED_AT,
        )

        assert repository.load("303", 2026, "1T") is None
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("13.22")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_filing_year == 2026
        assert prefill.prefilled[0].source_periods == ("1T",)


def test_iva_compensation_history_strict_persist_stores_latest_and_reloads(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = _persist_iva_compensation_history_observations_strict(
            (
                _prior_303_observation(
                    pending_compensation=Decimal("1.00"),
                    expediente_id="200030300000004Z",
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    pending_compensation=Decimal("2.00"),
                    expediente_id="200030300000005Z",
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            )
        )

        history = IvaCompensationHistoryRepository().load_period(2026, "1T")

        assert keys == ("303:2026:1T",)
        assert history is not None
        assert history.expediente_id == "200030300000005Z"
        assert history.pending_for_later_amount == Decimal("2.00")


def test_iva_history_capture_selects_latest_alta_declaration_per_period() -> None:
    selected = _latest_declarations_by_period(
        (
            _declaration(
                period="1T",
                expediente_id="200030300000006Z",
                estado="BAJA",
                presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
            ),
            _declaration(
                period="1T",
                expediente_id="200030300000007Z",
                estado="ALTA",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            ),
            _declaration(
                period="2T",
                expediente_id="200030300000008Z",
                estado="ALTA",
                presented_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=UTC),
            ),
        )
    )

    assert tuple(row.period for row in selected) == ("1T", "2T")
    assert selected[0].expediente_id == "200030300000007Z"
    assert selected[1].expediente_id == "200030300000008Z"


def test_duplicate_period_capture_promotes_latest_filing_to_calculation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        _persist_latest_filed_calculation_observations(
            (
                _prior_303_observation(
                    expediente_id="200030300000002Z",
                    pending_compensation=Decimal("800.00"),
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    expediente_id="200030300000003Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            )
        )

        stored = repository.load("303", 2026, "1T")

        assert stored is not None
        assert stored.observation.casilla_values["iva.compensacion-disponible-fin-periodo"] == Decimal("1200.00")


def test_filed_303_capture_persists_secure_iva_compensation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path) as db_path:
        prior_pending = Decimal("19.99")
        applied = Decimal("3.21")
        pending_later = Decimal("7.89")
        period_result = Decimal("-4.56")
        final_result = Decimal("-4.56")
        key = persist_filed_calculation_observation(
            _prior_303_observation(
                pending_compensation=pending_later,
                prior_pending=prior_pending,
                applied=applied,
                result=period_result,
                final_result=final_result,
                expediente_id=_SYNTHETIC_EXPEDIENTE_ID,
            )
        )

        history = IvaCompensationHistoryRepository().load_period(2026, "1T")

        assert key == "303:2026:1T"
        assert history is not None
        assert history.taxpayer_nif == _SYNTHETIC_PROFILE_ID
        assert history.expediente_id == _SYNTHETIC_EXPEDIENTE_ID
        assert history.prior_pending_amount == prior_pending
        assert history.applied_amount == applied
        assert history.pending_for_later_amount == pending_later
        assert history.period_result_amount == period_result
        assert history.final_result_amount == final_result
        assert history.source_artefact_sha256 == hashlib.sha256(b"303-2026-1T-submitted-file").hexdigest()
        assert history.source_observation_key == f"303:2026:1T:{_SYNTHETIC_EXPEDIENTE_ID}"

        listed = list_iva_compensation_history()
        assert listed.row_count == 1
        assert not hasattr(listed.rows[0], "taxpayer_nif")

        database_bytes = db_path.read_bytes()
        assert _SYNTHETIC_PROFILE_ID.encode("utf-8") not in database_bytes
        assert _SYNTHETIC_EXPEDIENTE_ID.encode("utf-8") not in database_bytes


def test_binding_prefill_refuses_incomplete_prior_filing_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        repository.save(
            RegistryModeloObservation(
                modelo="303",
                filing_year=2026,
                period="1T",
                observations=(CasillaObservation(casilla_id="87", value=Decimal("1200.00")),),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CAPTURED_AT,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")

        with pytest.raises(RegistryValidationError, match=r"iva\.compensacion-disponible-fin-periodo"):
            resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)


def _prior_303_observation(
    *,
    pending_compensation: Decimal,
    prior_pending: Decimal | None = None,
    applied: Decimal | None = None,
    result: Decimal = Decimal("0.00"),
    final_result: Decimal | None = None,
    year: int = 2026,
    period: str = "1T",
    expediente_id: str = _SYNTHETIC_EXPEDIENTE_ID,
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
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
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
            *(
                (
                    ObservedCasillaValue(
                        casilla_id="110",
                        value=str(prior_pending),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:110",
                        confidence=1.0,
                    ),
                )
                if prior_pending is not None
                else ()
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id="78",
                        value=str(applied),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:78",
                        confidence=1.0,
                    ),
                )
                if applied is not None
                else ()
            ),
            ObservedCasillaValue(
                casilla_id="87",
                value=str(pending_compensation),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:87",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id="69",
                value=str(result),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:69",
                confidence=1.0,
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id="71",
                        value=str(final_result),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:71",
                        confidence=1.0,
                    ),
                )
                if final_result is not None
                else ()
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id=f"303:2009-y-siguientes:{year}:{period}",
    )


def _declaration(
    *,
    period: str,
    expediente_id: str,
    estado: str,
    presented_at: datetime,
) -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        estado=estado,
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )
