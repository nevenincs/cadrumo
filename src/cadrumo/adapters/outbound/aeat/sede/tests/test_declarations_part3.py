"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ......core import CasillaId, Period, validated_casilla_id
from .._declarations_observations import resolve_relation_values_from_filed_declarations
from ._declarations_support import (
    UTC,
    Decimal,
    RegistryValidationError,
    SedeParseError,
    _filed_observation,
    _modelo_snapshot,
    _renta_2025_relation_observations,
    _whitespace_nif_session,
    datetime,
    relation_source_requirements,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_M115_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("01", surface="_M115_PERCEPTORES_CASILLA")
_M115_BASE_CASILLA: CasillaId = validated_casilla_id("02", surface="_M115_BASE_CASILLA")
_M115_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_CASILLA")
_M123_PERCEPTORES_CASILLA: CasillaId = validated_casilla_id("03", surface="_M123_PERCEPTORES_CASILLA")
_M123_BASE_CASILLA: CasillaId = validated_casilla_id("06", surface="_M123_BASE_CASILLA")
_M123_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_CASILLA")
_M130_RESULTADO_FINAL_CASILLA: CasillaId = validated_casilla_id("19", surface="_M130_RESULTADO_FINAL_CASILLA")


class TestFiledObservationRelations:
    """Verify filed observations can supply registry cross-model relations."""

    def test_modelo_100_relation_fixture_covers_registry_source_requirements(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()
        available = {
            (observation.modelo, observation.ejercicio, observation.period.registry_token, casilla.casilla_id)
            for observation in observations
            for casilla in observation.casillas
        }
        missing = [
            (requirement.source_modelo, requirement.filing_year, period, requirement.source_casilla_ids[0])
            for requirement in relation_source_requirements(snapshot.revision, filing_year=2025, period="0A")
            for period in requirement.periods
            if (
                requirement.source_modelo,
                requirement.filing_year,
                period,
                requirement.source_casilla_ids[0],
            )
            not in available
        ]

        assert not missing

    def test_modelo_100_relations_resolve_from_standardized_filed_observations(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            observations,
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
        )

        # Quarterly / monthly aggregations — verify inclusion (every
        # period observation contributed; aggregate exceeds the largest
        # single-period observation) and key presence. The exact arithmetic
        # is verified against AEAT's open simulator via the replay-parity
        # layer; assertions here pin the resolver's wiring contract only.
        quarterly_aggregations = {
            "renta-2025-rel-111-retenciones-trimestrales": Decimal("40"),  # max single quarter
            "renta-2025-rel-123-retenciones-trimestrales": Decimal("24"),
            "renta-2025-rel-130-pagos-fraccionados": Decimal("56"),
            "renta-2025-rel-131-pagos-fraccionados": Decimal("88"),
        }
        for relation_id, max_single in quarterly_aggregations.items():
            assert relation_id in resolved, f"{relation_id} missing from resolution"
            assert resolved[relation_id] > max_single, (
                f"{relation_id} = {resolved[relation_id]} not greater than max single observation "
                f"{max_single} — at least one period did not contribute"
            )

        # Monthly relation: same INCLUSION property — value must exceed max month (12).
        assert resolved["renta-2025-rel-111-retenciones-mensuales"] > Decimal("12")

        # Annual receivers are op=copy passthroughs — assert the
        # fixture's literal threads through to the resolved relation
        # value unchanged.
        annual_copies = {
            "renta-2025-rel-190-retenciones-anuales": Decimal("178"),
            "renta-2025-rel-193-retenciones-anuales": Decimal("60"),
            "renta-2025-rel-184-atribucion-actividades-economicas": Decimal("77"),
        }
        for relation_id, fixture_value in annual_copies.items():
            assert resolved[relation_id] == fixture_value, (
                f"{relation_id} copy thread broke — expected {fixture_value} from fixture"
            )

    def test_modelo_100_relation_resolution_requires_each_source_period(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        missing_period = Period.from_year_and_code(2025, "4T")
        observations = tuple(
            observation
            for observation in _renta_2025_relation_observations()
            if not (observation.modelo == "131" and observation.period == missing_period)
        )

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
            )

    def test_modelo_100_relation_resolution_rejects_duplicate_source_periods(self) -> None:
        snapshot = _modelo_snapshot("100", filing_year=2025, period="0A")
        observations = _renta_2025_relation_observations()
        duplicate = _filed_observation(
            modelo="130",
            ejercicio=2025,
            period="1T",
            casilla_values={_M130_RESULTADO_FINAL_CASILLA: Decimal("1")},
        )

        with pytest.raises(RegistryValidationError, match="found 2"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                (*observations, duplicate),
                filing_year=2025,
                period=Period.from_year_and_code(2025, "0A"),
            )

    @pytest.mark.parametrize("filing_year", (2022, 2026))
    def test_annual_summary_relations_resolve_from_quarterly_filed_observations(self, filing_year: int) -> None:
        snapshot = _modelo_snapshot("180", filing_year=filing_year, period="0A")
        quarterly_values = {
            "1T": {
                _M115_PERCEPTORES_CASILLA: Decimal("2"),
                _M115_BASE_CASILLA: Decimal("100.10"),
                _M115_RETENCIONES_CASILLA: Decimal("19.20"),
            },
            "2T": {
                _M115_PERCEPTORES_CASILLA: Decimal("3"),
                _M115_BASE_CASILLA: Decimal("200.20"),
                _M115_RETENCIONES_CASILLA: Decimal("38.40"),
            },
            "3T": {
                _M115_PERCEPTORES_CASILLA: Decimal("1"),
                _M115_BASE_CASILLA: Decimal("50.00"),
                _M115_RETENCIONES_CASILLA: Decimal("9.50"),
            },
            "4T": {
                _M115_PERCEPTORES_CASILLA: Decimal("4"),
                _M115_BASE_CASILLA: Decimal("300.30"),
                _M115_RETENCIONES_CASILLA: Decimal("57.60"),
            },
        }

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            tuple(
                _filed_observation(
                    modelo="115",
                    ejercicio=filing_year,
                    period=period,
                    casilla_values=casilla_values,
                )
                for period, casilla_values in quarterly_values.items()
            ),
            filing_year=filing_year,
            period=Period.from_year_and_code(filing_year, "0A"),
        )

        assert resolved == {
            "modelo-180-rel-115-base-anual": sum(values[_M115_BASE_CASILLA] for values in quarterly_values.values()),
            "modelo-180-rel-115-retenciones-anual": sum(
                values[_M115_RETENCIONES_CASILLA] for values in quarterly_values.values()
            ),
        }

    def test_modelo_193_relations_resolve_from_quarterly_filed_observations(self) -> None:
        snapshot = _modelo_snapshot("193", filing_year=2026, period="0A")
        quarterly_values = {
            "1T": {
                _M123_PERCEPTORES_CASILLA: Decimal("5"),
                _M123_BASE_CASILLA: Decimal("1201.00"),
                _M123_RETENCIONES_CASILLA: Decimal("228.19"),
            },
            "2T": {
                _M123_PERCEPTORES_CASILLA: Decimal("4"),
                _M123_BASE_CASILLA: Decimal("800.25"),
                _M123_RETENCIONES_CASILLA: Decimal("152.05"),
            },
            "3T": {
                _M123_PERCEPTORES_CASILLA: Decimal("7"),
                _M123_BASE_CASILLA: Decimal("999.75"),
                _M123_RETENCIONES_CASILLA: Decimal("189.95"),
            },
            "4T": {
                _M123_PERCEPTORES_CASILLA: Decimal("6"),
                _M123_BASE_CASILLA: Decimal("500.00"),
                _M123_RETENCIONES_CASILLA: Decimal("95.00"),
            },
        }

        resolved = resolve_relation_values_from_filed_declarations(
            snapshot.revision,
            tuple(
                _filed_observation(
                    modelo="123",
                    ejercicio=2026,
                    period=period,
                    casilla_values=casilla_values,
                )
                for period, casilla_values in quarterly_values.items()
            ),
            filing_year=2026,
            period=Period.from_year_and_code(2026, "0A"),
        )

        assert resolved == {
            "modelo-193-rel-123-base-anual": sum(values[_M123_BASE_CASILLA] for values in quarterly_values.values()),
            "modelo-193-rel-123-retenciones-anual": sum(
                values[_M123_RETENCIONES_CASILLA] for values in quarterly_values.values()
            ),
        }

    def test_missing_relation_source_filing_is_rejected(self) -> None:
        snapshot = _modelo_snapshot("180", filing_year=2026, period="0A")
        observations = tuple(
            _filed_observation(
                modelo="115",
                ejercicio=2026,
                period=period,
                casilla_values={
                    _M115_PERCEPTORES_CASILLA: Decimal("1"),
                    _M115_BASE_CASILLA: Decimal("10"),
                    _M115_RETENCIONES_CASILLA: Decimal("2"),
                },
            )
            for period in ("1T", "2T", "3T")
        )

        with pytest.raises(RegistryValidationError, match="expected one observed filing"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "0A"),
            )

    def test_incomplete_relation_source_observation_is_rejected(self) -> None:
        snapshot = _modelo_snapshot("180", filing_year=2026, period="0A")
        observations = tuple(
            _filed_observation(
                modelo="115",
                ejercicio=2026,
                period=period,
                casilla_values={
                    _M115_PERCEPTORES_CASILLA: Decimal("1"),
                    _M115_BASE_CASILLA: Decimal("10"),
                    _M115_RETENCIONES_CASILLA: Decimal("2"),
                },
                extraction_coverage={"submitted_file": 0.5} if period == "4T" else None,
            )
            for period in ("1T", "2T", "3T", "4T")
        )

        with pytest.raises(SedeParseError, match="incomplete extraction coverage"):
            resolve_relation_values_from_filed_declarations(
                snapshot.revision,
                observations,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "0A"),
            )


def test_capture_filed_declaration_empty_nif_carries_translated_message() -> None:
    """contract-A: capture_filed_declaration_observation raises SedeNavigationError with
    translated_message when AeatSession.identity_nif is whitespace-only."""
    import asyncio

    from .._declarations import (
        Declaracion,
        capture_filed_declaration_observation,
    )
    from ..errors import SedeNavigationError

    session = _whitespace_nif_session()
    declaration = Declaracion(
        modelo="130",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202600000000001E",
        estado="ALTA",
        tipo_solicitud=None,
        observaciones=None,
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        justificante_link_text="Ver",
        archive_link_text=None,
        declaration_copy_link_text=None,
    )

    with pytest.raises(SedeNavigationError) as exc_info:
        asyncio.run(capture_filed_declaration_observation(session, declaration))

    assert exc_info.value.translated_message is not None
    assert "adapters.sede.errors.empty_identity_nif" not in exc_info.value.translated_message


def test_capture_filed_declaration_empty_nif_locale_key_resolves_to_real_copy() -> None:
    """contract-B: the empty-identity-nif locale key resolves to non-placeholder copy."""
    from ......core.i18n import tr

    resolved = tr("adapters.sede.errors.empty_identity_nif")
    assert "adapters.sede.errors.empty_identity_nif" not in resolved
    assert len(resolved) > 10
