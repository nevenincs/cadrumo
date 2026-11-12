"""Hand-worked oracle for the Modelo 200 microempresa scale of LIS DT 44ª.

The scenario runs for every bundled Sociedades manual edition that prints the
two-rate scale for entities whose prior-period INCN is below 1.000.000 euros,
and whose exercise an authored Modelo 200 revision calculates.

Sources:

    ``corpus/normatives/html/ley-27-2014-dt-44.html.extracted.md`` L3-6 (DT
      44ª.1.a): "Las entidades cuyo importe neto de la cifra de negocios del
      periodo impositivo inmediato anterior sea inferior a 1 millon de euros,
      aplicaran la siguiente escala ... i) Por la parte de base imponible
      comprendida entre 0 y 50.000 euros, al tipo del 21 por ciento. ii) Por la
      parte de base imponible restante, al tipo del 22 por ciento."

    ``corpus/manuals/sociedades/2025/source.pdf.extracted.md``:
      L3231-3237 (pag. 85, casilla 00088): the same 21 / 22 scale.
      L14948-14954 (pag. 372): "[00562] = [01330] x [00558]/100", always
        "una cantidad positiva o cero".
      L14961-14983 (pag. 373, "Tipos de gravamen vigentes", column "2025"):
        "Entidades INCN < 1 millon de euros ... Hasta 50.000 euros 21 por 100 /
        Resto Base Imponible 22 por 100"; L14968 "Tipo general 25 por 100".

    ``corpus/aeat_official/disenos_registro/modelo_200/files/
      01-200-ejercicio-2025-10-9-mb-xls.xls.extracted.md`` L1495 (DP200014
      field 31, "Tipo de gravamen [00558]", 4 positions, Nota 1) and
      L1530-1534 (Nota 1): "En caso de tipo de gravamen unico se rellenaran
      los dos primeros digitos con el tipo, y los dos ultimos con 00. Ej: 25%
      se rellenara como 2500. En caso de tipo de gravamen doble se rellenaran
      los dos primeros digitos con el primer tipo, y los dos ultimos con el
      segundo. Ej: 18/19% se rellenara como 1819."

The general rule 00562 = 01330 x 00558 / 100 holds for a single rate. The scale
has two, so the cuota is the scale applied to 01330. Box 00558 holds the
design's four-digit code: "2122" for the scale and "2500" for the general 25,
and its export field prints that code unchanged.

Synthetic scenario: a sociedad limitada (no entidad patrimonial, not newly
created, regimen comun, not in a tax group), prior-period INCN 600.000 euros,
with a resultado contable before IS (casilla 00501) and no correction, reserva,
BIN compensation, bonificacion or deduccion, so the base imponible after the
reserva de nivelacion (casilla 01330) equals the resultado. No pago
fraccionado, no retencion, INCN below 20 millones and no consolidacion fiscal,
so the art. 30 bis cuota liquida minima does not apply.

Hand derivation, base 100.000:
    00558 = 2122; export field "2122"            (Nota 1)
    00562 = 50.000 x 21 % + 50.000 x 22 %
          = 10.500 + 11.000 = 21.500             (DT 44ª.1.a)
    00582 = 00592 = 00611 = 21.500
  A single 21 would give 21.000, a single 22 would give 22.000, the general 25
  would give 25.000 and the 2024 flat 23 would give 23.000.

Hand derivation, base 150.000 (the base moves by 50.000 inside the second
tranche):
    00562 = 10.500 + 100.000 x 22 % = 32.500; the change is 50.000 x 22 % =
    11.000, the second rate alone.

Hand derivation, base 40.000 (inside the first tranche):
    00562 = 40.000 x 21 % = 8.400.

Hand derivation, prior-period INCN 12.000.000 euros and base 100.000: general
rate, 00558 = 2500 (export field "2500") and 00562 = 25.000 (L14968).

None of these amounts was read from a run of the registry formulas under test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.secure_objects_fixture import secure_objects
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.calculations.observations_repository import APP_FILING_SOURCE_KIND
from cadrumo.application.modelo.calculation_bucket_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from cadrumo.domain.calculations.registry.fixed_width_codec import render_fixed_width_export_field
from cadrumo.domain.calculations.registry.schema_exports import ExportFieldDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions_where,
    manual_editions_printing,
)
from cadrumo.domain.calculations.registry.tests.published_authority import published_revision
from cadrumo.domain.calculations.registry.tests.registry_observations import (
    registry_grounded_observations,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.tests.profile_persistence.file_flow_test_support import calculation_ports_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from .observation_seeding_support import save_stamped_observation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "7d41c2e8-9a3b-4f6c-8e15-2b0d9c4a6f81"

__all__ = ["secure_objects"]


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


_M200 = "200"
_M202 = "202"

_CASILLA_RESULTADO_CTA_PYG: CasillaId = validated_casilla_id("DP200012:00501", surface="_CASILLA_RESULTADO_CTA_PYG")
_CASILLA_CUOTA_LIQUIDA_MINIMA: CasillaId = validated_casilla_id(
    "DP200014B:00619", surface="_CASILLA_CUOTA_LIQUIDA_MINIMA"
)
_CASILLA_TIPO_GRAVAMEN: CasillaId = validated_casilla_id("DP200014:00558", surface="_CASILLA_TIPO_GRAVAMEN")
_CASILLA_CUOTA_INTEGRA: CasillaId = validated_casilla_id("DP200014:00562", surface="_CASILLA_CUOTA_INTEGRA")
_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA: CasillaId = validated_casilla_id(
    "DP200014:00582", surface="_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA"
)
_CASILLA_CUOTA_LIQUIDA: CasillaId = validated_casilla_id("DP200014B:00592", surface="_CASILLA_CUOTA_LIQUIDA")
_CASILLA_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id("DP200014B:00611", surface="_CASILLA_CUOTA_DIFERENCIAL")

# No pago fraccionado in the scenario: the same-year Modelo 202 instalments are
# recorded as filed zero so the cuota diferencial's direct relation operands resolve.
_M202_PAGO_OUTPUT: CasillaId = validated_casilla_id("34", surface="_M202_PAGO_OUTPUT")
_M202_PAGO_OUTPUT_40_2: CasillaId = validated_casilla_id("03", surface="_M202_PAGO_OUTPUT_40_2")
_M202_PAGO_PERIODS = ("1P", "2P", "3P")

# Scenario inputs (synthetic, module docstring).
_INCN_MICROEMPRESA = Decimal("600000")
_INCN_GENERAL = Decimal("12000000")
_BASE_BOTH_TRANCHES = Decimal("100000.00")
_BASE_SECOND_TRANCHE_MOVED = Decimal("150000.00")
_BASE_FIRST_TRANCHE_ONLY = Decimal("40000.00")

# Hand-derived expectations (module docstring).
_TIPO_DOBLE = Decimal("2122")
_TIPO_GENERAL = Decimal("2500")
_TIPO_DOBLE_WIRE = "2122"
_TIPO_GENERAL_WIRE = "2500"
_CUOTA_BOTH_TRANCHES = Decimal("21500.00")
_CUOTA_SECOND_TRANCHE_MOVED = Decimal("32500.00")
_CUOTA_FIRST_TRANCHE_ONLY = Decimal("8400.00")
_CUOTA_GENERAL = Decimal("25000.00")
_SECOND_TRANCHE_CHANGE = Decimal("11000.00")


def _calculated_m200_exercise(exercise: int) -> bool:
    """Whether an authored Modelo 200 revision covering the exercise claims calculation authority."""
    return any(
        revision.valid_from.year <= exercise and (revision.valid_to is None or exercise <= revision.valid_to.year)
        for revision in authored_revisions_where(
            _M200, lambda revision: revision.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY
        )
    )


# Every Sociedades manual edition that prints the 21 / 22 microempresa scale,
# restricted to the exercises a Modelo 200 revision calculates.
_ESCALA_EDITIONS = tuple(
    exercise
    for exercise in manual_editions_printing(
        "sociedades",
        "aplican los tipos de gravamen que se indican en la siguiente escala",
        "Por la parte de base imponible comprendida entre 0 y 50.000 euros, el tipo del 21",
        "Por la parte de base imponible restante, el tipo del 22 por ciento",
    )
    if _calculated_m200_exercise(exercise)
)
assert _ESCALA_EDITIONS, "no calculated Modelo 200 exercise has a manual printing the 21 / 22 microempresa scale"


def _tipo_gravamen_export_field(filing_year: int) -> ExportFieldDefinition:
    """The one export field the exercise's Modelo 200 layout gives casilla 00558."""
    snapshot = published_authority_operation().snapshot(
        _M200, filing_year=filing_year, period="0A", grade=RegistryAuthorityGrade.CALCULATION
    )
    revision = published_revision(_M200, str(snapshot.revision.id))
    fields = [
        field
        for layout in revision.export_layouts
        for record in layout.records
        for field in record.fields
        if field.casilla_id == _CASILLA_TIPO_GRAVAMEN
    ]
    assert len(fields) == 1, fields
    return fields[0]


def _profile_instant(filing_year: int) -> datetime:
    return datetime(filing_year + 1, 1, 15, 9, 0, tzinfo=UTC)


def _clock(filing_year: int, hour: int) -> datetime:
    return datetime(filing_year + 2, 1, 15, hour, 0, tzinfo=UTC)


def _seed_sociedad_profile(filing_year: int, incn_prior: Decimal) -> None:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="B00023002"),
                UserProfileFact(path="identity.legal_name", value="Microempresa Escala Sintetica SL"),
                UserProfileFact(path="activities.description", value="comercio al por menor"),
                UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=incn_prior),
            ),
            persona_id="sociedad-limitada",
        ),
        created_at=_profile_instant(filing_year),
        updated_at=_profile_instant(filing_year),
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record)


def _seed_zero_m202_pagos(filing_year: int) -> None:
    obs_repo = CalculationObservationRepository()
    for period in _M202_PAGO_PERIODS:
        save_stamped_observation(
            obs_repo,
            RegistryModeloObservation(
                modelo=_M202,
                filing_year=filing_year,
                period=period,
                observations=registry_grounded_observations(
                    modelo=_M202,
                    filing_year=filing_year,
                    period=period,
                    casilla_values={_M202_PAGO_OUTPUT: Decimal("0"), _M202_PAGO_OUTPUT_40_2: Decimal("0")},
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_profile_instant(filing_year),
        )


def _calculate_m200(
    secure_objects: SecureObjectRepository,
    *,
    filing_year: int,
    incn_prior: Decimal,
    resultado: Decimal,
    operation: PinnedAuthorityOperation,
) -> BucketAggregationCalculationResult:
    """Run the live Modelo 200 0A calculation for the synthetic sociedad."""
    _seed_sociedad_profile(filing_year, incn_prior)
    _seed_zero_m202_pagos(filing_year)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    bucket_event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot(
        _M200,
        filing_year=filing_year,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=filing_year,
        period=Period.from_year_and_code(filing_year, "0A"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=bucket_event_repo),
        clock=_clock(filing_year, 9),
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bucket_event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as ports:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            casilla_inputs={
                _CASILLA_RESULTADO_CTA_PYG: resultado,
                # Art. 30 bis does not reach this sociedad (INCN below 20 millones,
                # no consolidacion fiscal), so the operator enters no cuota mínima.
                _CASILLA_CUOTA_LIQUIDA_MINIMA: Decimal("0"),
            },
            ports=ports,
            clock=_clock(filing_year, 10),
        )


@pytest.mark.parametrize("filing_year", _ESCALA_EDITIONS)
def test_m200_microempresa_states_both_rates_and_taxes_the_base_on_the_scale(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """INCN 600.000, base 100.000: 00558 = 2122; 00562/00582/00592/00611 = 21.500."""
    values = _calculate_m200(
        secure_objects,
        filing_year=filing_year,
        incn_prior=_INCN_MICROEMPRESA,
        resultado=_BASE_BOTH_TRANCHES,
        operation=operation,
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_DOBLE
    assert (
        render_fixed_width_export_field(_tipo_gravamen_export_field(filing_year), values[_CASILLA_TIPO_GRAVAMEN])
        == _TIPO_DOBLE_WIRE
    )
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_BOTH_TRANCHES
    assert values[_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA] == _CUOTA_BOTH_TRANCHES
    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_BOTH_TRANCHES
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_BOTH_TRANCHES


@pytest.mark.parametrize("filing_year", _ESCALA_EDITIONS)
def test_m200_microempresa_cuota_moves_with_the_base_at_the_second_rate(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Base 150.000: 00562 = 32.500, so 50.000 more base adds 11.000, the 22 per cent tranche alone."""
    values = _calculate_m200(
        secure_objects,
        filing_year=filing_year,
        incn_prior=_INCN_MICROEMPRESA,
        resultado=_BASE_SECOND_TRANCHE_MOVED,
        operation=operation,
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_DOBLE
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_SECOND_TRANCHE_MOVED
    assert values[_CASILLA_CUOTA_INTEGRA] - _CUOTA_BOTH_TRANCHES == _SECOND_TRANCHE_CHANGE
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_SECOND_TRANCHE_MOVED


@pytest.mark.parametrize("filing_year", _ESCALA_EDITIONS)
def test_m200_microempresa_base_inside_the_first_tranche_pays_the_first_rate(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Base 40.000: 00562 = 40.000 x 21 % = 8.400; 00558 still states the pair 2122."""
    values = _calculate_m200(
        secure_objects,
        filing_year=filing_year,
        incn_prior=_INCN_MICROEMPRESA,
        resultado=_BASE_FIRST_TRANCHE_ONLY,
        operation=operation,
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_DOBLE
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_FIRST_TRANCHE_ONLY
    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_FIRST_TRANCHE_ONLY


@pytest.mark.parametrize("filing_year", _ESCALA_EDITIONS)
def test_m200_incn_not_below_one_million_keeps_the_single_general_rate(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """INCN 12.000.000, base 100.000: 00558 = 2500, 00562 = 25.000; the scale is not reached."""
    values = _calculate_m200(
        secure_objects,
        filing_year=filing_year,
        incn_prior=_INCN_GENERAL,
        resultado=_BASE_BOTH_TRANCHES,
        operation=operation,
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_GENERAL
    assert (
        render_fixed_width_export_field(_tipo_gravamen_export_field(filing_year), values[_CASILLA_TIPO_GRAVAMEN])
        == _TIPO_GENERAL_WIRE
    )
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_GENERAL
