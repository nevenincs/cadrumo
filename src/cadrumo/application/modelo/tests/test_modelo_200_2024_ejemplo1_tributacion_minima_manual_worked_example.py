"""Oracle test for M200 2024 casillas 00562/00592/00611, grounded against the
AEAT Manual practico de Sociedades 2024's own "Ejemplo 1" worked example
(Cap. 6, "Liquidacion del Impuesto sobre Sociedades: Determinacion de la deuda
tributaria", "Cuota liquida minima (casilla 00619)", paginas 392-396).

Ground truth (bundled AEAT Manual practico de Sociedades 2024):

    raw_evidence_locator: corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf#Pag.392-396

The manual walks "la sociedad <<A>>" - importe neto de la cifra de negocios
(INCN) en los 12 meses anteriores superior a 20 millones de euros, base
imponible de 2.000.000 euros, tipo general de gravamen del 25 por ciento -
through the LIS art. 30 bis "tributacion minima" mechanism, printing BOTH the
liquidacion that would result WITHOUT tributacion minima and the liquidacion
that actually applies once tributacion minima is taken into account. Both
printed tables are quoted verbatim below and both are graded in this module
(two independent, AEAT-printed data points from the SAME worked example):

    Raw facts (pag. 392), quoted verbatim:
      "tiene una base imponible de 2.000.000 de euros y tributa al tipo
       general de gravamen del 25 por ciento"
      "Deduccion para evitar doble imposicion internacional: 150.000 euros"
      "Deduccion de I+D+i (art. 35 LIS): 80.000 euros"
      "Cuota integra = Base imponible (2.000.000) x Tipo de gravamen (25%) =
       500.000 euros"

    Liquidacion del IS 2024 (sin tributacion minima) (pag. 393-394), quoted
    verbatim:
      "Resultado cuenta de perdidas y ganancias [00500] 2.000.000"
      "Base imponible [00552] 2.000.000"
      "Tipo de gravamen 25%"
      "Cuota integra [00562] 500.000"
      "Deduccion Doble Imposicion Internacional [00573] - 150.000"
      "Cuota integra ajustada positiva [00582] 350.000"
      "Deduccion incentivar determinadas actividades [00588] - 80.000"
      "Cuota liquida minima [00619] 0"
      "Cuota liquida [00592] 270.000"
      "Resultado de la liquidacion [01586] 270.000"

    Liquidacion final (con tributacion minima aplicada) (pag. 395-396), quoted
    verbatim - the manual computes the cuota liquida minima under LIS art. 30
    bis.1 as "BI despues de la reserva de nivelacion [01330] 2.000.000 / Tipo
    de gravamen 15% / Cuota liquida minima [00619] 300.000" (pag. 394), then
    prints the corrected final liquidacion:
      "Cuota integra [00562] 500.000 -"
      "Deduccion Doble Imposicion Internacional [00573] -150.000 -"
      "Cuota integra ajustada positiva [00582] 350.000 -"
      "Deduccion incentivar determinadas actividades [00588] -50.000 -30.0000"
      "Cuota liquida minima [00619] 300.000 -"
      "Cuota liquida [00592] 300.000 -"
      "Resultado de la liquidacion [01586] 300.000 -"

Registry mapping (M200 2024 revision):

    casilla DP200014:00562 "Cuota integra" = formula
      `modelo-200-cuota-integra`: BI despues de la reserva de nivelacion
      (DP200014:01330, fed here via the manual casilla [00501] "Resultado
      cuenta perdidas y ganancias antes de IS" = 2.000.000, with every
      correccion/reserva/compensacion casilla in the 00501->01330 chain left
      at its registry default of Decimal(0), matching the manual's own
      "Reserva de capitalizacion [01032] 0 / Compensacion BIN [00547] 0 /
      Reserva de nivelacion [01033]/[01034] 0" rows) x the flat 25% general
      bracket (`is.modelo-200.cuota-integra-bracket-general`, INCN > 10M so
      the general lane applies) = 2.000.000 x 25% = 500.000 -> matches the
      manual's own "Cuota integra [00562] 500.000" exactly, in BOTH tables.
    casilla DP200014:00582 "Cuota integra ajustada positiva" = formula
      `modelo-200-cuota-integra-ajustada-positiva`: max(0, (00562 + 01038) -
      sum-of-bonificaciones-and-DI-deductions) = max(0, 500.000 - 150.000) =
      350.000 (casilla 00573 fed 150.000, every other bonificacion/DI casilla
      in the sum left at 0) -> matches the manual's own "Cuota integra
      ajustada positiva [00582] 350.000" exactly, in BOTH tables. (Not
      enrolled as an externally-grounded target per the revision's own
      verification-expectations comment, which deliberately excludes 00582 as
      "situational"; asserted here as an intermediate cross-check only.)
    casilla DP200014B:00592 "Cuota liquida" = formula `modelo-200-cuota-
      liquida`: max(00619, max(0, 00582 - sum-of-otras-deducciones)).
      * WITHOUT tributacion minima (00619 fed 0, matching the manual's own
        "sin tributacion minima" table): max(0, max(0, 350.000 - 80.000)) =
        270.000 -> matches the manual's own "Cuota liquida [00592] 270.000"
        exactly.
      * WITH tributacion minima (00619 fed 300.000, the manual's own art. 30
        bis.1 result): max(300.000, max(0, 350.000 - 80.000=270.000)) =
        300.000 -> matches the manual's own final "Cuota liquida [00592]
        300.000" exactly. Note the registry formula's max(...) floor
        reproduces the art. 30 bis effect WITHOUT needing the operator to
        pre-limit casilla 00588 to the capped 50.000 the manual's own
        art.30bis.2.b) allocation arithmetic derives (see the manual's own
        "podra aplicarse 50.000 euros de deduccion de I+D+i... pues... existe
        una diferencia de 50.000 euros"): feeding the FULL 80.000 euros of
        generated (not manually pre-capped) deduccion still yields the
        correct 300.000 floor, because max(00619, ...) dominates regardless
        of how far past the floor the uncapped subtraction lands.
    casilla DP200014B:00611 "Cuota diferencial - Estado" = formula `modelo-
      200-cuota-diferencial`: 00599 - (M202 pagos fraccionados relations).
      00599 = (tributacion_estado_porcentaje/100) x (00592 - 01766 - 01784) =
      1.0 x (00592 - 0 - 0) = 00592 (no retenciones, no forales, and the
      taxpayer's tributacion_estado_porcentaje profile binding fed 100 -
      comun-regimen, matching the manual's scenario which mentions no
      regimen foral). No Modelo 202 pagos fraccionados are seeded for 2024
      (the manual's Ejemplo 1 does not mention any pago a cuenta), so both
      M202 relations are seeded filed-zero (casillas 34 and 03) exactly as
      the proven `test_modelo_200_fold_in_live` fold-in scaffold does, making
      00611 = 00599 - 0 = 00592 in both scenarios -> 270.000 / 300.000,
      consistent with the manual's own "Resultado de la liquidacion [01586]"
      row printing the SAME 270.000 / 300.000 figures (01586 itself is a
      manual casilla outside this test's engine-grounded scope, but its
      printed value corroborates that no further Liquidacion IV item beyond
      00592 applies in this scenario).

Anti-tautology: this test does not hand-compute 500.000, 350.000, 270.000, or
300.000 from the registry's own cuota-chain formulas under test. Every raw
input (base imponible via casilla 00501, DI deduction via casilla 00573,
I+D+i deduction via casilla 00588, and the art. 30 bis cuota liquida minima
via casilla 00619) is quoted verbatim from the manual's own printed tables
above, and the two independent AEAT-printed scenarios (sin/con tributacion
minima) are BOTH graded - proving the registry's max(00619, ...) floor
mechanism is doing real work (the con-minima run changes casillas 00592/00611
by exactly the manual's own delta), not a hand-computed absolute figure or a
formula that ignores casilla 00619 entirely.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import CasillaId, Period, RegistryAuthorityGrade, validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.tests import oracle_declared_figures
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from .._work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "8f1a6c2e-9b3d-4e7a-9c1f-2d5b6a7e8f90"
_T0 = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
_M200 = "200"
_M202 = "202"
_FILING_YEAR = 2024

# Manual casilla inputs (Ejemplo 1, quoted verbatim in the module docstring).
#
# One mapping is worth a reader's attention. The example's liquidación table
# labels the resultado row ``[00500]`` while the scenario feeds ``00501``; the
# registry records why on the casilla itself -- 00501 is the Liquidación I
# result-before-IS row the official manual uses as the base-determination
# starting point. The FIGURE is the same 2.000.000 the example states twice,
# and its locator cites both statements. That box choice predates this
# declaration and is unchanged by it.
_ORACLE_PAYLOAD_NAME = "modelo-200-2024-ejemplo1-tributacion-minima-empresa-grande.json"

_CASILLA_RESULTADO_CTA_PYG: CasillaId = validated_casilla_id("00501", surface="_CASILLA_RESULTADO_CTA_PYG")
_CASILLA_DEDUCCION_DI_INTERNACIONAL: CasillaId = validated_casilla_id(
    "00573",
    surface="_CASILLA_DEDUCCION_DI_INTERNACIONAL",
)
_CASILLA_DEDUCCION_INCENTIVAR_ACTIVIDADES: CasillaId = validated_casilla_id(
    "DP200014B:00588",
    surface="_CASILLA_DEDUCCION_INCENTIVAR_ACTIVIDADES",
)
_CASILLA_CUOTA_LIQUIDA_MINIMA: CasillaId = validated_casilla_id(
    "DP200014B:00619",
    surface="_CASILLA_CUOTA_LIQUIDA_MINIMA",
)

# Target/oracle casillas.
_CASILLA_CUOTA_INTEGRA: CasillaId = validated_casilla_id("DP200014:00562", surface="_CASILLA_CUOTA_INTEGRA")
_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA: CasillaId = validated_casilla_id(
    "DP200014:00582",
    surface="_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA",
)
_CASILLA_CUOTA_LIQUIDA: CasillaId = validated_casilla_id("DP200014B:00592", surface="_CASILLA_CUOTA_LIQUIDA")
_CASILLA_CUOTA_DIFERENCIAL: CasillaId = validated_casilla_id("DP200014B:00611", surface="_CASILLA_CUOTA_DIFERENCIAL")

# No Modelo 202 pagos fraccionados are mentioned in Ejemplo 1; seed both
# same-year M202 relations filed-zero exactly as the proven
# `test_modelo_200_fold_in_live` fold-in scaffold does, so the cuota-
# diferencial formula (a direct, non-defaultable operand) resolves instead of
# raising.
_M202_PAGO_OUTPUT: CasillaId = validated_casilla_id("34", surface="_M202_PAGO_OUTPUT")
_M202_PAGO_OUTPUT_40_2: CasillaId = validated_casilla_id("03", surface="_M202_PAGO_OUTPUT_40_2")
_M202_PAGO_PERIODS = ("1P", "2P", "3P")

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()

_CUOTA_INTEGRA_EXPECTED = Decimal("500000.00")
_CUOTA_INTEGRA_AJUSTADA_POSITIVA_EXPECTED = Decimal("350000.00")
_CUOTA_LIQUIDA_SIN_MINIMA_EXPECTED = Decimal("270000.00")
_CUOTA_LIQUIDA_CON_MINIMA_EXPECTED = Decimal("300000.00")


def _seed_sociedad_profile() -> None:
    """Seed the standard M200 legal-entity profile scaffold for Ejemplo 1.

    ``incn_prior_12_months`` is fed 25.000.000 - matching the manual's own
    "importe neto de la cifra de negocios en los 12 meses anteriores...
    superio los 20 millones de euros" (pag. 392) - which routes the
    `modelo-200-cuota-integra` formula's entity-form dispatch to the flat 25%
    general bracket (INCN > 10.000.000). ``tributacion_estado_porcentaje`` is
    100 (comun regimen, no forales mentioned in the scenario).
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="A12345674"),
            UserProfileFact(path="identity.legal_name", value="Sociedad A Ejemplo1 SL"),
            UserProfileFact(path="activities.description", value="fabricacion industrial"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("25000000")),
            UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _seed_zero_m202_pagos() -> None:
    """Seed same-year M202 instalments as filed zero, so the M200 cuota-
    diferencial formula's direct M202 relation operands resolve.
    """
    obs_repo = CalculationObservationRepository()
    for period in _M202_PAGO_PERIODS:
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo=_M202,
                    filing_year=_FILING_YEAR,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo=_M202,
                        filing_year=_FILING_YEAR,
                        period=period,
                        casilla_values={
                            _M202_PAGO_OUTPUT: Decimal("0"),
                            _M202_PAGO_OUTPUT_40_2: Decimal("0"),
                        },
                    ),
                ),
                source_kind=APP_FILING_SOURCE_KIND,
                captured_at=_T0,
            )
        )


def _calculate_m200(
    secure_objects: SecureObjectRepository,
    *,
    cuota_liquida_minima: Decimal,
) -> BucketAggregationCalculationResult:
    """Run the live M200/2024/0A calculate with Ejemplo 1's manual casilla inputs."""
    _seed_sociedad_profile()
    _seed_zero_m202_pagos()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot(
        _M200,
        filing_year=_FILING_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M200,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs={
            **oracle_declared_figures(_ORACLE_PAYLOAD_NAME),
            # Not declared: the cuota líquida mínima is what this scenario ASSERTS
            # (casillas 00592 and 00611), so supplying it as a declared input would
            # have the oracle check the figure it was handed.
            _CASILLA_CUOTA_LIQUIDA_MINIMA: cuota_liquida_minima,
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_m200_2024_ejemplo1_con_tributacion_minima_manual_worked_example(
    secure_objects: SecureObjectRepository,
) -> None:
    """00562/00582/00592/00611 = 500.000/350.000/300.000/300.000, con tributacion minima.

    Oracle: AEAT Manual practico de Sociedades 2024, Cap. 6, "Cuota liquida
    minima (casilla 00619)", Ejemplo 1, paginas 392-396 - final liquidacion
    once LIS art. 30 bis tributacion minima is applied: "Cuota integra [00562]
    500.000", "Cuota integra ajustada positiva [00582] 350.000", "Cuota
    liquida minima [00619] 300.000", "Cuota liquida [00592] 300.000". The
    manual's own art. 30 bis.1 computation ("BI despues de la reserva de
    nivelacion [01330] 2.000.000 / Tipo de gravamen 15% / Cuota liquida
    minima [00619] 300.000") is fed here as the manual casilla 00619 input,
    exactly as the manual states it - this test does not re-derive the 15%
    art. 30 bis.1 floor itself (that sub-computation is not modelled as a
    registry formula; casilla 00619 is `input_kind = manual`), only the
    downstream max(00619, ...) cuota-liquida/cuota-diferencial chain that
    IS a registry formula under test.
    """
    result = _calculate_m200(secure_objects, cuota_liquida_minima=Decimal("300000.00"))
    values = result.revision.casilla_values

    assert values[_CASILLA_CUOTA_INTEGRA] == _CUOTA_INTEGRA_EXPECTED
    assert values[_CASILLA_CUOTA_INTEGRA_AJUSTADA_POSITIVA] == _CUOTA_INTEGRA_AJUSTADA_POSITIVA_EXPECTED
    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_LIQUIDA_CON_MINIMA_EXPECTED
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_LIQUIDA_CON_MINIMA_EXPECTED


def test_m200_2024_ejemplo1_sin_tributacion_minima_manual_worked_example(
    secure_objects: SecureObjectRepository,
) -> None:
    """00592/00611 = 270.000, sin tributacion minima (00619 = 0).

    Oracle: the SAME manual Ejemplo 1's OTHER printed table (paginas 393-394),
    "Liquidacion del IS 2024 (sin tributacion minima)": "Cuota liquida minima
    [00619] 0", "Cuota liquida [00592] 270.000", "Resultado de la liquidacion
    [01586] 270.000". Every other raw input (00501/00573/00588) is identical
    to the con-minima scenario; only casilla 00619 changes (300.000 -> 0).
    """
    result = _calculate_m200(secure_objects, cuota_liquida_minima=Decimal("0"))
    values = result.revision.casilla_values

    assert values[_CASILLA_CUOTA_LIQUIDA] == _CUOTA_LIQUIDA_SIN_MINIMA_EXPECTED
    assert values[_CASILLA_CUOTA_DIFERENCIAL] == _CUOTA_LIQUIDA_SIN_MINIMA_EXPECTED


def test_casilla_00619_anti_tautology_floor_changes_cuota_liquida(secure_objects: SecureObjectRepository) -> None:
    """Anti-tautology: raising casilla 00619 from 0 to 300.000 must raise 00592/00611
    by exactly the manual's own delta (30.000 = 300.000 - 270.000).

    Proves the registry's ``modelo-200-cuota-liquida`` formula genuinely
    consumes casilla 00619 as a floor (``max(00619, ...)``) rather than
    ignoring it or returning a constant - both endpoints are independently
    AEAT-printed figures from the SAME worked example (never hand-computed
    from the formula under test).
    """
    sin_minima = _calculate_m200(secure_objects, cuota_liquida_minima=Decimal("0"))
    con_minima = _calculate_m200(secure_objects, cuota_liquida_minima=Decimal("300000.00"))

    delta = Decimal("300000.00") - Decimal("270000.00")
    assert (
        con_minima.revision.casilla_values[_CASILLA_CUOTA_LIQUIDA]
        - sin_minima.revision.casilla_values[_CASILLA_CUOTA_LIQUIDA]
        == delta
    )
    assert (
        con_minima.revision.casilla_values[_CASILLA_CUOTA_DIFERENCIAL]
        - sin_minima.revision.casilla_values[_CASILLA_CUOTA_DIFERENCIAL]
        == delta
    )


def test_m200_2024_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction() -> None:
    """The manual-oracle grounding of 00562/00592/00611 is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``, generalised across every
    bundled modelo) already proves the ``externally_grounded_casilla_ids``
    declaration on the ``modelo-200-cuota-chain-verification`` verification
    expectation is backed by the bundled
    ``corpus/manual_oracles/modelo-200-2024-ejemplo1-tributacion-minima-empresa-grande.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`~cadrumo.domain.calculations.registry.RegistryVerificationPolicy` fold,
    so 00562/00592/00611 raise ``independently_grounded_fraction`` above zero
    for M200 rather than sitting inert in TOML. Not tautological: the
    grounded set and the fraction are read from the registry's own declared
    and validated data, never hand-computed or asserted from a synthetic
    fixture.
    """
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    snapshot = authority.snapshot(
        _M200,
        filing_year=_FILING_YEAR,
        period="0A",
        grade=RegistryAuthorityGrade.CALCULATION,
    )
    policy = snapshot.verification_policy()

    for casilla_id in (_CASILLA_CUOTA_INTEGRA, _CASILLA_CUOTA_LIQUIDA, _CASILLA_CUOTA_DIFERENCIAL):
        assert casilla_id in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_CUOTA_LIQUIDA in externally_grounded
    assert independently_grounded_fraction > 0.0
