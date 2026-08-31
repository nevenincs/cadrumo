"""Current-schema proof for disposition-aware Modelo 303 carry ingress."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import CasillaId, Modelo, ObservedHeaderFact, Period, ResultDisposition
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ....domain.calculations.registry.casilla_membership import casillas_by_id
from ....domain.iva_compensation import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
    M303_COMPENSATION_GENERADA_CASILLA,
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from ....tests.secure_sql import isolated_runtime_profile
from .._m303_carry_ingress import M303CarryIngressError
from ..observations_repository import (
    CalculationObservationRepository,
    ObservationSourceKind,
    ResultDispositionProjection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_POSTERIOR = Decimal("7.00")
_NEGATIVE_RESULT = Decimal("-20.00")


def _observed_header(code: str) -> ObservedHeaderFact:
    return ObservedHeaderFact(
        header_key="declaration_type",
        value=code,
        source_artefact_kind="submitted_file",
        source_locator=f"modelo-303-fichero-boe:declaration-type:{code}",
    )


def _carry_observation() -> RegistryModeloObservation:
    snapshot = bundled_authority().snapshot(
        Modelo.M303.value,
        filing_year=_PERIOD.filing_year,
        period=_PERIOD.registry_token,
    )
    definitions = casillas_by_id(snapshot.revision)

    def observed(casilla_id: CasillaId, value: Decimal) -> CasillaObservation:
        definition = definitions[casilla_id]
        return CasillaObservation(
            casilla_id=casilla_id,
            value=value,
            legal_refs=tuple(definition.legal_refs),
            source_refs=tuple(definition.source_refs),
        )

    return RegistryModeloObservation(
        modelo=Modelo.M303.value,
        filing_year=_PERIOD.filing_year,
        period=_PERIOD.registry_token,
        observations=(
            observed(M303_COMPENSATION_POSTERIOR_CASILLA, _POSTERIOR),
            observed(M303_COMPENSATION_RESULTADO_CASILLA, _NEGATIVE_RESULT),
        ),
    )


@pytest.mark.parametrize(
    ("source_kind", "source_headers"),
    [
        (ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE, ()),
        (ObservationSourceKind.APP_FILING, ()),
    ],
)
def test_under_declared_m303_carry_is_refused_before_repository_mutation(
    tmp_path: Path,
    source_kind: ObservationSourceKind,
    source_headers: tuple[ObservedHeaderFact, ...],
) -> None:
    """Canonical ingress never invents a missing official or filing disposition."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()

        with pytest.raises(M303CarryIngressError):
            repository.prepare_observation_envelope(
                _carry_observation(),
                source_kind=source_kind,
                captured_at=_CAPTURED_AT,
                source_headers=source_headers,
                normalize_m303_carry=True,
            )

        assert repository.load_observation(Modelo.M303.value, _PERIOD) is None


@pytest.mark.parametrize(
    ("disposition", "source_headers", "projection", "expected_available", "expected_generated", "expected_basis"),
    [
        (
            ResultDisposition.COMPENSACION,
            (_observed_header(ResultDisposition.COMPENSACION.value),),
            None,
            Decimal("27.00"),
            Decimal("20.00"),
            "resultado",
        ),
        (
            ResultDisposition.DEVOLUCION,
            (),
            ResultDispositionProjection(
                disposition=ResultDisposition.DEVOLUCION,
                provenance_kind="app_filing",
                provenance_locator="filed-revision:current-schema-proof",
            ),
            Decimal("7.00"),
            Decimal("0.00"),
            "refunded",
        ),
    ],
)
def test_current_dispositions_and_normalized_pair_round_trip_through_real_repository(
    tmp_path: Path,
    disposition: ResultDisposition,
    source_headers: tuple[ObservedHeaderFact, ...],
    projection: ResultDispositionProjection | None,
    expected_available: Decimal,
    expected_generated: Decimal,
    expected_basis: str,
) -> None:
    """Official and local current-schema evidence persist one strict normalized envelope."""
    source_kind = ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE if source_headers else ObservationSourceKind.APP_FILING
    with isolated_runtime_profile(tmp_path=tmp_path):
        repository = CalculationObservationRepository()
        prepared = repository.prepare_observation_envelope(
            _carry_observation(),
            source_kind=source_kind,
            captured_at=_CAPTURED_AT,
            source_headers=source_headers,
            result_disposition=projection,
            normalize_m303_carry=True,
        )

        repository.save(prepared)
        loaded = repository.load_observation(Modelo.M303.value, _PERIOD)

        assert loaded == prepared
        assert loaded is not None
        assert loaded.result_disposition is not None
        assert loaded.result_disposition.disposition is disposition
        assert loaded.m303_compensation_basis == expected_basis
        assert loaded.observation.casilla_values[M303_COMPENSATION_AVAILABLE_CASILLA] == expected_available
        assert loaded.observation.casilla_values[M303_COMPENSATION_GENERADA_CASILLA] == expected_generated
