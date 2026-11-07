"""Adapter contract tests for the translated empty-NIF capture refusal."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority

from ......core.casilla_id import CasillaId, validated_casilla_id
from ......core.period import Period
from ......domain.calculations.registry.errors import RegistryValidationError
from ......domain.calculations.registry.relations import relation_source_requirements
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_edition
from ..errors import SedeParseError
from .declarations_support import (
    filed_observation,
    modelo_snapshot,
    renta_relation_observations,
    resolve_relations_from_observations,
    whitespace_nif_session,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]
_YEAR = filing_year_envelope().horizon
_RENTA_YEAR = newest_authored_edition("100")
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
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot(
                "100", filing_year=_RENTA_YEAR, period="0A", operation=_authority_operation_for_test
            )
            observations = renta_relation_observations(_RENTA_YEAR)
            available = {
                (observation.modelo, observation.ejercicio, observation.period.registry_token, casilla.casilla_id)
                for observation in observations
                for casilla in observation.casillas
            }
            missing = [
                (requirement.source_modelo, requirement.filing_year, period, requirement.source_casilla_ids[0])
                for requirement in relation_source_requirements(snapshot.revision, filing_year=_RENTA_YEAR, period="0A")
                for period in requirement.periods
                # A source declared over alternative cadences is filed under
                # one of them; the fixture files the first declared cadence.
                if Period.from_year_and_code(_RENTA_YEAR, period).kind
                == Period.from_year_and_code(_RENTA_YEAR, requirement.periods[0]).kind
                and (
                    requirement.source_modelo,
                    requirement.filing_year,
                    period,
                    requirement.source_casilla_ids[0],
                )
                not in available
            ]

            assert not missing

    def test_modelo_100_relations_resolve_from_standardized_filed_observations(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot(
                "100", filing_year=_RENTA_YEAR, period="0A", operation=_authority_operation_for_test
            )
            observations = renta_relation_observations(_RENTA_YEAR)

            resolved = resolve_relations_from_observations(
                snapshot.revision,
                observations,
                filing_year=_RENTA_YEAR,
                period=Period.from_year_and_code(_RENTA_YEAR, "0A"),
                operation=_authority_operation_for_test,
            )

            # Quarterly / monthly aggregations — verify inclusion (every
            # period observation contributed; aggregate exceeds the largest
            # single-period observation) and key presence. The exact arithmetic
            # is NOT externally verified against AEAT: these assertions pin the
            # resolver's wiring contract only, and no bundled oracle reconciles
            # these relation ids against an AEAT-computed figure today.
            quarterly_aggregations = {
                "renta-modelo-130-pagos-fraccionados": Decimal("56"),  # max single quarter
                "renta-modelo-131-pagos-fraccionados": Decimal("88"),
            }
            for relation_id, max_single in quarterly_aggregations.items():
                assert relation_id in resolved, f"{relation_id} missing from resolution"
                assert resolved[relation_id] > max_single, (
                    f"{relation_id} = {resolved[relation_id]} not greater than max single observation "
                    f"{max_single} — at least one period did not contribute"
                )

            # No annual receiver remains: the withholding-automation returns credit the
            # declarant nothing, and the instalment returns are the only relations.
            assert set(resolved) == set(quarterly_aggregations)

            # The fixture's filed Modelo 184 carries the entity's type-2 attribution
            # total, not the member's share that casilla 1577 declares, so it moves
            # no Modelo 100 relation value.
            without_m184 = resolve_relations_from_observations(
                snapshot.revision,
                tuple(observation for observation in observations if observation.modelo != "184"),
                filing_year=_RENTA_YEAR,
                period=Period.from_year_and_code(_RENTA_YEAR, "0A"),
                operation=_authority_operation_for_test,
            )
            assert resolved == without_m184

    def test_modelo_100_relation_resolution_requires_each_source_period(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot(
                "100", filing_year=_RENTA_YEAR, period="0A", operation=_authority_operation_for_test
            )
            missing_period = Period.from_year_and_code(_RENTA_YEAR, "4T")
            observations = tuple(
                observation
                for observation in renta_relation_observations(_RENTA_YEAR)
                if not (observation.modelo == "131" and observation.period == missing_period)
            )

            with pytest.raises(RegistryValidationError, match="expected one observed filing"):
                resolve_relations_from_observations(
                    snapshot.revision,
                    observations,
                    filing_year=_RENTA_YEAR,
                    period=Period.from_year_and_code(_RENTA_YEAR, "0A"),
                    operation=_authority_operation_for_test,
                )

    def test_modelo_100_relation_resolution_rejects_duplicate_source_periods(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot(
                "100", filing_year=_RENTA_YEAR, period="0A", operation=_authority_operation_for_test
            )
            observations = renta_relation_observations(_RENTA_YEAR)
            duplicate = filed_observation(
                modelo="130",
                ejercicio=_RENTA_YEAR,
                period="1T",
                casilla_values={_M130_RESULTADO_FINAL_CASILLA: Decimal("1")},
            )

            with pytest.raises(RegistryValidationError, match="found 2"):
                resolve_relations_from_observations(
                    snapshot.revision,
                    (*observations, duplicate),
                    filing_year=_RENTA_YEAR,
                    period=Period.from_year_and_code(_RENTA_YEAR, "0A"),
                    operation=_authority_operation_for_test,
                )

    @pytest.mark.parametrize("filing_year", (filing_year_envelope().floor, filing_year_envelope().horizon))
    def test_annual_summary_relations_resolve_from_quarterly_filed_observations(self, filing_year: int) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot(
                "180", filing_year=filing_year, period="0A", operation=_authority_operation_for_test
            )
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

            resolved = resolve_relations_from_observations(
                snapshot.revision,
                tuple(
                    filed_observation(
                        modelo="115",
                        ejercicio=filing_year,
                        period=period,
                        casilla_values=casilla_values,
                    )
                    for period, casilla_values in quarterly_values.items()
                ),
                filing_year=filing_year,
                period=Period.from_year_and_code(filing_year, "0A"),
                operation=_authority_operation_for_test,
            )

            assert resolved == {
                "modelo-180-115-base-anual": sum(values[_M115_BASE_CASILLA] for values in quarterly_values.values()),
                "modelo-180-115-retenciones-anual": sum(
                    values[_M115_RETENCIONES_CASILLA] for values in quarterly_values.values()
                ),
            }

    def test_modelo_193_relations_resolve_from_quarterly_filed_observations(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot("193", filing_year=_YEAR, period="0A", operation=_authority_operation_for_test)
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

            resolved = resolve_relations_from_observations(
                snapshot.revision,
                tuple(
                    filed_observation(
                        modelo="123",
                        ejercicio=_YEAR,
                        period=period,
                        casilla_values=casilla_values,
                    )
                    for period, casilla_values in quarterly_values.items()
                ),
                filing_year=_YEAR,
                period=Period.from_year_and_code(_YEAR, "0A"),
                operation=_authority_operation_for_test,
            )

            assert resolved == {
                "modelo-193-123-base-anual": sum(values[_M123_BASE_CASILLA] for values in quarterly_values.values()),
                "modelo-193-123-retenciones-anual": sum(
                    values[_M123_RETENCIONES_CASILLA] for values in quarterly_values.values()
                ),
            }

    def test_missing_relation_source_filing_is_rejected(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot("180", filing_year=_YEAR, period="0A", operation=_authority_operation_for_test)
            observations = tuple(
                filed_observation(
                    modelo="115",
                    ejercicio=_YEAR,
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
                resolve_relations_from_observations(
                    snapshot.revision,
                    observations,
                    filing_year=_YEAR,
                    period=Period.from_year_and_code(_YEAR, "0A"),
                    operation=_authority_operation_for_test,
                )

    def test_incomplete_relation_source_observation_is_rejected(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            snapshot = modelo_snapshot("180", filing_year=_YEAR, period="0A", operation=_authority_operation_for_test)
            observations = tuple(
                filed_observation(
                    modelo="115",
                    ejercicio=_YEAR,
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
                resolve_relations_from_observations(
                    snapshot.revision,
                    observations,
                    filing_year=_YEAR,
                    period=Period.from_year_and_code(_YEAR, "0A"),
                    operation=_authority_operation_for_test,
                )


def test_register_capture_empty_nif_carries_translated_message() -> None:
    """The live session owner refuses an observation without an authenticated NIF."""
    import asyncio
    from typing import cast

    from ......application.live.expedientes_ports import ExpedientesDeclaration
    from ...playwright import BrowserContext, Page
    from ..declarations import DeclaracionesRegisterSession
    from ..errors import SedeNavigationError

    session = whitespace_nif_session()
    declaration = ExpedientesDeclaration(
        modelo="130",
        ejercicio=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        expediente_id=f"{_YEAR}00000000001E",
        estado="ALTA",
        tipo_solicitud=None,
        observaciones=None,
        presented_at=datetime(_YEAR, 4, 20, 10, 0, 0, tzinfo=UTC),
        justificante_link_text="Ver",
        archive_link_text=None,
        declaration_copy_link_text=None,
    )

    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        register = DeclaracionesRegisterSession(
            session,
            cast(Page, object()),
            cast(BrowserContext, object()),
            operation=_authority_operation_for_test,
        )
        with pytest.raises(SedeNavigationError) as exc_info:
            asyncio.run(register.capture_observation(declaration))

    assert exc_info.value.translated_message is not None
    assert "adapters.sede.errors.empty_identity_nif" not in exc_info.value.translated_message


def test_capture_filed_declaration_empty_nif_locale_key_resolves_to_real_copy() -> None:
    """contract-B: the empty-identity-nif locale key resolves to non-placeholder copy."""
    from ......core.i18n.render import tr

    resolved = tr("adapters.sede.errors.empty_identity_nif")
    assert "adapters.sede.errors.empty_identity_nif" not in resolved
    assert len(resolved) > 10
