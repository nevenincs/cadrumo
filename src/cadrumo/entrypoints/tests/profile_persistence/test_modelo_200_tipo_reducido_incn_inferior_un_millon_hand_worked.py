"""Hand-worked oracle for the Modelo 200 reduced rate of entities whose prior-period INCN is below 1.000.000 euros.

The scenario runs for every bundled Sociedades manual edition that prints the
flat 23 per cent reduced rate of LIS art. 29.1 as amended by Ley 31/2022, and
whose exercise an authored Modelo 200 revision calculates. Ley 7/2024 replaced
that flat rate with a two-tranche microempresa scale for periods starting in
the following year, so this is the point where that edition's law differs from
its successor's and a revision that inherited the successor's rate would fail
here.

Sources (line numbers of ``corpus/manuals/sociedades/2024/source.pdf.extracted.md``):

    L14682-14683 (pag. 363, "Tipos de gravamen vigentes", column "2024"):
      "Entidades INCN < 1 millon de euros en el periodo impositivo inmediato
       anterior (no siendo aplicable a aquellas entidades que tengan la
       consideracion de entidad patrimonial)  23 por 100"
    L14670: "Tipo general 25 por 100"
    L3169-3175 (casilla 00088): "Marcaran esta casilla las entidades cuyo
      importe neto de la cifra de negocios del periodo impositivo inmediato
      anterior sea inferior a 1 millon de euros y que segun lo dispuesto en el
      articulo 29.1 de la LIS (segun la redaccion aplicable respecto a los
      periodos impositivos iniciados con anterioridad a 1 de enero de 2025),
      tributan al tipo de gravamen reducido del 23 por ciento."
    L14663-14665 (casilla 00558): "se hara constar el tipo de gravamen que
      corresponda de acuerdo con el regimen de tributacion aplicable".
    L14648-14654 (casilla 00562): "[00562] = [01330] x [00558]/100".
    L14819-14821 (casilla 00582): "[00582] = ([00562] + [01038]) - ([00567] +
      ... + [00573] + ... + [00581])".
    L16399-16401 (casilla 00592): "[00592] = [00582] - ([00583] + ... + [00588]
      + ... + [01041])"; "El resultado ... siempre tendra que ser una cantidad
      positiva o cero."
    L15807-15811 (art. 30 bis.1 LIS, tributacion minima): applies only to
      contribuyentes with INCN "al menos de 20 millones de euros durante los 12
      meses anteriores" or in consolidacion fiscal.
    L20345 (casilla 00599): "[00599] = ([00625]/100]) x ([00592] - [01766] -
      [01784])".
    L20579-20582 (casilla 00611): "[00611] = [00599] - ([00601] + [00603] +
      [00605])".

The successor's rate, for contrast only (``corpus/manuals/sociedades/2025/
source.pdf.extracted.md`` L14980-14983): "Entidades INCN < 1 millon de euros
... Hasta 50.000 euros 21 por 100 / Resto Base Imponible 22 por 100", the LIS
DT 44a.1 scale (``corpus/normatives/html/ley-27-2014-dt-44.html.extracted.md``
L3-6).

Synthetic scenario: a sociedad limitada (no entidad patrimonial, not newly
created, regimen comun, not in a tax group) with a resultado contable before IS
of 100.000 euros (casilla 00501) and no correction, reserva, BIN compensation,
bonificacion or deduccion, so the base imponible after the reserva de
nivelacion (casilla 01330) is 100.000 euros. No pago fraccionado and no
retencion.

Hand derivation, prior-period INCN 600.000 euros, and 28.500 euros (the
sociedad-limitada persona's turnover), both below 1.000.000:
    00558 = 23                                   (L14682-14683, L3169-3175)
    00562 = 100.000 x 23 / 100 = 23.000          (L14654)
    00582 = (23.000 + 0) - 0 = 23.000            (L14819-14821)
    00619 = 0: INCN below 20 millones and no consolidacion fiscal, so art. 30
            bis tributacion minima does not apply (L15807-15811)
    00592 = 23.000 - 0 = 23.000                  (L16399-16401)
    00599 = 100 % Estado x (00592 - 0 - 0) = 23.000; 00611 = 23.000 - 0 = 23.000
                                                 (L20579-20582)
  The successor's scale would give 50.000 x 21 % + 50.000 x 22 % = 21.500 and
  the general rate 25.000; neither equals 23.000.

Hand derivation, prior-period INCN exactly 1.000.000 euros: the reduced rate
requires INCN "inferior a 1 millon de euros" (L3172), which 1.000.000 is not,
so the general rate applies (L14670): 00558 = 25, 00562 = 100.000 x 25 / 100 =
25.000, 00592 = 00611 = 25.000.

Hand derivation, prior-period INCN 12.000.000 euros: general rate (L14670),
art. 30 bis not reached (below 20 millones): 00558 = 25, 00562 = 00592 = 00611
= 25.000.

None of 23.000 / 25.000 was read from a run of the registry formulas under test.
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
from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions_where,
    manual_editions_printing,
)
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

_BUCKET_ID = "3c7e1b9a-5d2f-4a8e-b6c4-9f0a1d2e3b47"

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
_RESULTADO_ANTES_IS = Decimal("100000.00")
_INCN_BELOW_ONE_MILLION = Decimal("600000")
_INCN_SMALL_SOCIEDAD = Decimal("28500")
_INCN_AT_ONE_MILLION = Decimal("1000000")
_INCN_GENERAL_BELOW_TRIBUTACION_MINIMA = Decimal("12000000")

# Hand-derived expectations (module docstring).
_TIPO_REDUCIDO = Decimal("23")
_TIPO_GENERAL = Decimal("25")
_CUOTA_TIPO_REDUCIDO = Decimal("23000.00")
_CUOTA_TIPO_GENERAL = Decimal("25000.00")


def _calculated_m200_exercise(exercise: int) -> bool:
    """Whether an authored Modelo 200 revision covering the exercise claims calculation authority."""
    return any(
        revision.valid_from.year <= exercise and (revision.valid_to is None or exercise <= revision.valid_to.year)
        for revision in authored_revisions_where(
            _M200, lambda revision: revision.effective_authority_grade is not RegistryAuthorityGrade.APPLICABILITY
        )
    )


# Every Sociedades manual edition that prints the flat 23 per cent reduced rate
# for INCN below 1 millon, restricted to the exercises a Modelo 200 revision calculates.
_FLAT_REDUCED_RATE_EDITIONS = tuple(
    exercise
    for exercise in manual_editions_printing(
        "sociedades",
        "Entidades INCN < 1 millón de euros en el período impositivo inmediato anterior",
        "tributan al tipo de gravamen reducido del 23 por ciento",
    )
    if _calculated_m200_exercise(exercise)
)
assert _FLAT_REDUCED_RATE_EDITIONS, "no calculated Modelo 200 exercise has a manual printing the flat reduced rate"


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
                UserProfileFact(path="identity.legal_name", value="Sociedad Tipo Reducido Sintetica SL"),
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
                _CASILLA_RESULTADO_CTA_PYG: _RESULTADO_ANTES_IS,
                # Art. 30 bis does not reach this sociedad (INCN below 20 millones,
                # no consolidacion fiscal), so the operator enters no cuota mínima.
                _CASILLA_CUOTA_LIQUIDA_MINIMA: Decimal("0"),
            },
            ports=ports,
            clock=_clock(filing_year, 10),
        )


@pytest.mark.parametrize("filing_year", _FLAT_REDUCED_RATE_EDITIONS)
@pytest.mark.parametrize("incn_prior", [_INCN_BELOW_ONE_MILLION, _INCN_SMALL_SOCIEDAD])
def test_m200_incn_below_one_million_applies_flat_23_per_cent(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    incn_prior: Decimal,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """INCN 600.000 and 28.500: 00558/00562/00582/00592/00611 = 23 / 23.000 / 23.000 / 23.000 / 23.000."""
    values = _calculate_m200(
        secure_objects, filing_year=filing_year, incn_prior=incn_prior, operation=operation
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_REDUCIDO
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_TIPO_REDUCIDO
    assert values[_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA] == _CUOTA_TIPO_REDUCIDO
    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_TIPO_REDUCIDO
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_TIPO_REDUCIDO


@pytest.mark.parametrize("filing_year", _FLAT_REDUCED_RATE_EDITIONS)
@pytest.mark.parametrize("incn_prior", [_INCN_AT_ONE_MILLION, _INCN_GENERAL_BELOW_TRIBUTACION_MINIMA])
def test_m200_incn_not_below_one_million_applies_general_25_per_cent(
    secure_objects: SecureObjectRepository,
    filing_year: int,
    incn_prior: Decimal,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """INCN 1.000.000 (the threshold is strict) and 12.000.000: general 25 per cent, 25.000 throughout."""
    values = _calculate_m200(
        secure_objects, filing_year=filing_year, incn_prior=incn_prior, operation=operation
    ).revision.casilla_values

    assert values[_CASILLA_TIPO_GRAVAMEN] == _TIPO_GENERAL
    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_TIPO_GENERAL
    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_TIPO_GENERAL
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_TIPO_GENERAL
