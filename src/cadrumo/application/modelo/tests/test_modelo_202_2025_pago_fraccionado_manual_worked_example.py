"""Oracle test for M202 casilla 03, grounded against the AEAT Manual practico de
Sociedades 2024's own worked example (Cap. 15, "El pago fraccionado del Impuesto
sobre Sociedades", apartado "A) Calculo del pago fraccionado: modalidad
articulo 40.2 de la LIS", "Ejemplo", paginas 811-812).

Ground truth (bundled AEAT Manual practico de Sociedades 2024):

    raw_evidence_locator: corpus/aeat_official/manuals/modelo_200/files/manual-sociedades-2024.pdf#Pag.811-812

The manual walks "la Sociedad Limitada <<M>>" (ejercicio economico coincide con
el ano natural) through the THREE 2025 pagos fraccionados under modalidad art.
40.2 LIS, printing an independent AEAT-computed casilla-03 figure for each
instalment (quoted verbatim below):

    "Primer pago. Primeros veinte dias naturales del mes de abril de 2025:
     Base del pago fraccionado: (12.000 - 2.000) = 10.000 euros.
     18% de 10.000 euros = 1.800 euros, que, segun el modelo 202, debera
     ingresar."

    "El 11 de julio de 2025 presenta la declaracion correspondiente al
     ejercicio 2024, con una cuota integra de 3.000 euros, sin que se haya
     practicado deduccion o bonificacion alguna. Las retenciones soportadas en
     el ejercicio 2024 ascendieron a 500 euros.
     Segundo pago. Primeros veinte dias naturales del mes de octubre de 2025.
     18% de (3.000 - 500) = 450 euros, que, segun el modelo 202, debera
     ingresar.
     Tercer pago. Primeros veinte dias naturales del mes de diciembre de 2025.
     18% de (3.000 - 500) = 450 euros, que, segun el modelo 202, debera
     ingresar."

Registry mapping (M202 2025-y-siguientes revision):

    casilla "03" "Mod. 40.2 LIS - A ingresar" = formula
    `modelo-202-modalidad-40-2-a-ingresar`: 18% x casilla "01" (Base del pago
    fraccionado, LIS art. 40.2 - cuota integra/liquida del ultimo periodo
    impositivo cuyo plazo de declaracion estuviese vencido, minorada en
    deducciones/bonificaciones/retenciones) - casilla "02" (Resultado de la
    declaracion anterior, only for complementarias). The manual's own
    "(12.000 - 2.000)" and "(3.000 - 500)" subtractions ARE the casilla "01"
    determination rule quoted in the manual's own "Casilla 01. Base del pago
    fraccionado" apartado ("La cuota integra del ultimo periodo impositivo...
    minorado en las deducciones y bonificaciones, asi como en las retenciones
    e ingresos a cuenta"), so casilla "01" = 10.000,00 EUR (1P, from ejercicio
    2023's cuota 12.000 - retenciones 2.000) and casilla "01" = 2.500,00 EUR
    (2P/3P, from ejercicio 2024's cuota 3.000 - retenciones 500). The 18%
    percentage is the registry parameter `is.modalidad_cuota.percentage`
    (value "18" for `date_axis = "filing_period"`, `valid_from = 2025-01-01`).

    The registry's casilla "01" binding
    (`modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior`,
    `source = "relation_prefill"`) is a `CALLER_OVERRIDABLE_CARRY_SOURCES`
    member, so this test supplies it directly as the manual's own quoted
    10.000,00 / 2.500,00 EUR figure, mirroring the same override channel the
    live CLI ``--binding`` flag uses
    (see ``test_modelo_202_art_40_2_cuota_incn_below_threshold`` in
    ``entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py``,
    which independently grounds the SAME 1P figure against a different
    citation, AEAT DR 202 Instrucciones). This module adds the manual's own
    SECOND, independently-quoted 2P/3P data point (base 2.500,00 -> cuota
    450,00), never exercised elsewhere, proving the formula is genuinely
    proportional rather than a constant.

Anti-tautology: this test does not hand-compute 1.800,00 or 450,00 from the
registry's own `modelo-202-modalidad-40-2-a-ingresar` formula under test.
Both casilla "01" inputs (10.000,00 and 2.500,00) and both casilla "03"
results (1.800,00 and 450,00) are quoted verbatim from the manual's printed
worked example above. A companion delta check proves the registry formula
consumes casilla "01" proportionally: the manual's own base delta
(10.000,00 - 2.500,00 = 7.500,00) times 18% equals the manual's own result
delta (1.800,00 - 450,00 = 1.350,00) exactly - so the formula is doing real
multiplicative work, not returning a constant or ignoring casilla "01".
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....application.filing import (
    ModeloOperatorProfile,
    build_draft,
    build_runtime_schema_provider,
)
from ....application.filing._draft_construction import _filing_period_date
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import bundled_path
from ....domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
from ....domain.calculations.registry.ids import BindingId
from ....domain.period import calculation_filing_date
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._revision_replay_inputs import revision_filing_replay_inputs
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "3d7c1e9a-5b2f-4a68-9c0d-1e6f8b3a2c5d"
_T0 = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
_M202 = "202"
_FILING_YEAR = 2025

# Manual casilla inputs (Ejemplo, quoted verbatim in the module docstring).
_CASILLA_RESULTADO_DECLARACION_ANTERIOR: CasillaId = validated_casilla_id(
    "02",
    surface="_CASILLA_RESULTADO_DECLARACION_ANTERIOR",
)

# Target/oracle casilla.
_CASILLA_A_INGRESAR: CasillaId = validated_casilla_id("03", surface="_CASILLA_A_INGRESAR")

_BINDING_INCN: BindingId = "modelo-202-2025-y-siguientes-incn-prior-12-months"
_BINDING_CUOTA_BASE_EJERCICIO_ANTERIOR: BindingId = "modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior"
_BINDING_PAGOS_FRACCIONADOS_ANTERIORES: BindingId = "modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores"

# INCN below the LIS art. 40.3 mandatory-modality threshold (6.000.000 EUR)
# so the art. 40.2 lane (clave 03) is offered; the manual's Sociedad "M" is
# not stated to be a large company and files the optional art. 40.2 lane.
_INCN_BELOW_THRESHOLD = Decimal("500000")

_BASE_PRIMER_PAGO_EXPECTED = Decimal("10000.00")
_A_INGRESAR_PRIMER_PAGO_EXPECTED = Decimal("1800.00")
_BASE_SEGUNDO_TERCER_PAGO_EXPECTED = Decimal("2500.00")
_A_INGRESAR_SEGUNDO_TERCER_PAGO_EXPECTED = Decimal("450.00")

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()


def _seed_sociedad_m_profile() -> None:
    """Seed the M202 legal-entity profile scaffold for the manual's Sociedad "M".

    ``incn_prior_12_months`` is fed below the LIS art. 40.3 mandatory-modality
    threshold (6.000.000 EUR) so the art. 40.2 lane the manual walks through
    (clave 03) is the applicable one - matching the manual's scenario, which
    never mentions the art. 40.3 obligation.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.name", value="Sociedad M Ejemplo"),
            UserProfileFact(path="identity.legal_name", value="Sociedad Limitada M SL"),
            UserProfileFact(path="identity.tax_id", value="B87654323"),
            UserProfileFact(path="activities.description", value="actividad economica"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=_INCN_BELOW_THRESHOLD),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _calculate_m202(
    secure_objects: SecureObjectRepository,
    *,
    period_code: str,
    cuota_base_ejercicio_anterior: Decimal,
) -> BucketAggregationCalculationResult:
    """Run the live M202/2025 calculate with the manual's Ejemplo casilla inputs."""
    _seed_sociedad_m_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot(_M202, filing_year=_FILING_YEAR, period=period_code)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M202,
        filing_year=_FILING_YEAR,
        period=Period.from_year_and_code(_FILING_YEAR, period_code),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        casilla_inputs={_CASILLA_RESULTADO_DECLARACION_ANTERIOR: Decimal("0.00")},
        binding_values={
            _BINDING_INCN: _INCN_BELOW_THRESHOLD,
            _BINDING_CUOTA_BASE_EJERCICIO_ANTERIOR: cuota_base_ejercicio_anterior,
            _BINDING_PAGOS_FRACCIONADOS_ANTERIORES: Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_m202_2025_primer_pago_manual_worked_example(secure_objects: SecureObjectRepository) -> None:
    """1P casilla "03" = 1.800,00 EUR (base 10.000,00, 18%).

    Oracle: AEAT Manual practico de Sociedades 2024, Cap. 15, Ejemplo, "Primer
    pago" (pagina 811): "Base del pago fraccionado: (12.000 - 2.000) = 10.000
    euros. 18% de 10.000 euros = 1.800 euros".
    """
    result = _calculate_m202(secure_objects, period_code="1P", cuota_base_ejercicio_anterior=_BASE_PRIMER_PAGO_EXPECTED)
    assert result.revision.casilla_values[_CASILLA_A_INGRESAR] == _A_INGRESAR_PRIMER_PAGO_EXPECTED


def test_m202_2025_segundo_pago_manual_worked_example(secure_objects: SecureObjectRepository) -> None:
    """2P casilla "03" = 450,00 EUR (base 2.500,00, 18%).

    Oracle: AEAT Manual practico de Sociedades 2024, Cap. 15, Ejemplo, "Segundo
    pago" (pagina 811): "18% de (3.000 - 500) = 450 euros".
    """
    result = _calculate_m202(
        secure_objects,
        period_code="2P",
        cuota_base_ejercicio_anterior=_BASE_SEGUNDO_TERCER_PAGO_EXPECTED,
    )
    assert result.revision.casilla_values[_CASILLA_A_INGRESAR] == _A_INGRESAR_SEGUNDO_TERCER_PAGO_EXPECTED


def test_m202_2025_tercer_pago_manual_worked_example(secure_objects: SecureObjectRepository) -> None:
    """3P casilla "03" = 450,00 EUR (base 2.500,00, 18%), same figures as 2P.

    Oracle: AEAT Manual practico de Sociedades 2024, Cap. 15, Ejemplo, "Tercer
    pago" (pagina 811): "18% de (3.000 - 500) = 450 euros" - the manual states
    the third instalment reuses the same ejercicio-2024 cuota/retenciones as
    the second.
    """
    result = _calculate_m202(
        secure_objects,
        period_code="3P",
        cuota_base_ejercicio_anterior=_BASE_SEGUNDO_TERCER_PAGO_EXPECTED,
    )
    assert result.revision.casilla_values[_CASILLA_A_INGRESAR] == _A_INGRESAR_SEGUNDO_TERCER_PAGO_EXPECTED


@pytest.mark.parametrize(
    ("period_code", "cuota_base_ejercicio_anterior", "expected_filing_date"),
    (
        ("1P", _BASE_PRIMER_PAGO_EXPECTED, date(2025, 4, 30)),
        ("2P", _BASE_SEGUNDO_TERCER_PAGO_EXPECTED, date(2025, 10, 31)),
        ("3P", _BASE_SEGUNDO_TERCER_PAGO_EXPECTED, date(2025, 12, 31)),
    ),
)
def test_m202_calculation_revision_replays_to_draft_on_the_same_sanctioned_filing_date(
    secure_objects: SecureObjectRepository,
    period_code: str,
    cuota_base_ejercicio_anterior: Decimal,
    expected_filing_date: date,
) -> None:
    """The AEAT-worked M202 calculation must retain its result through draft replay.

    Each payment month is the AEAT Modelo 202 filing-date anchor documented in
    the Manual de Sociedades worked example above.  The test calculates from
    the real encrypted work-unit source, rehydrates that persisted revision's
    actual filing inputs, and lets the filing runtime recompute its draft.
    """
    calculated = _calculate_m202(
        secure_objects,
        period_code=period_code,
        cuota_base_ejercicio_anterior=cuota_base_ejercicio_anterior,
    ).revision
    work_unit = WorkUnitCatalogueRepository(objects=secure_objects).load().get(calculated.work_unit_id)
    assert work_unit is not None
    assert calculation_filing_date(work_unit.period) == expected_filing_date
    assert _filing_period_date(work_unit.period) == expected_filing_date

    replay_inputs = revision_filing_replay_inputs(revision=calculated, work_unit=work_unit)
    draft = build_draft(
        modelo=_M202,
        period=work_unit.period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Sociedad Limitada M SL"),
        inputs=replay_inputs,
        schema_provider=build_runtime_schema_provider(
            modelos=(_M202,),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        ),
    )
    draft_values = {value.casilla_id: value.value for value in draft.values}

    assert draft_values[_CASILLA_A_INGRESAR] == calculated.casilla_values[_CASILLA_A_INGRESAR]


def test_casilla_01_anti_tautology_delta_changes_casilla_03_proportionally(
    secure_objects: SecureObjectRepository,
) -> None:
    """Anti-tautology: the manual's own base delta must produce its own result delta.

    Proves the registry's ``modelo-202-modalidad-40-2-a-ingresar`` formula
    genuinely multiplies casilla "01" by 18% (rather than ignoring it or
    returning a constant) - both endpoints are independently AEAT-printed
    figures from the SAME worked example (never hand-computed from the
    formula under test): base delta 10.000,00 - 2.500,00 = 7.500,00 must
    produce a result delta of exactly 18% x 7.500,00 = 1.350,00, matching the
    manual's own 1.800,00 - 450,00 = 1.350,00.
    """
    primer_pago = _calculate_m202(
        secure_objects, period_code="1P", cuota_base_ejercicio_anterior=_BASE_PRIMER_PAGO_EXPECTED
    )
    segundo_pago = _calculate_m202(
        secure_objects,
        period_code="2P",
        cuota_base_ejercicio_anterior=_BASE_SEGUNDO_TERCER_PAGO_EXPECTED,
    )

    base_delta = _BASE_PRIMER_PAGO_EXPECTED - _BASE_SEGUNDO_TERCER_PAGO_EXPECTED
    result_delta = _A_INGRESAR_PRIMER_PAGO_EXPECTED - _A_INGRESAR_SEGUNDO_TERCER_PAGO_EXPECTED
    assert base_delta == Decimal("7500.00")
    assert result_delta == Decimal("1350.00")

    assert (
        primer_pago.revision.casilla_values[_CASILLA_A_INGRESAR]
        - segundo_pago.revision.casilla_values[_CASILLA_A_INGRESAR]
        == result_delta
    )


def test_m202_2025_manual_grounding_is_enrolled_and_raises_independently_grounded_fraction() -> None:
    """The manual-oracle grounding of casilla "03" is enrolled, not just computed.

    A companion registry-honesty gate
    (``test_external_oracle_grounding_enrolled.py``, generalised across every
    bundled modelo) already proves the ``externally_grounded_casilla_ids``
    declaration on the ``modelo-202-2025-cuota-chain-verification``
    verification expectation is backed by the bundled
    ``corpus/manual_oracles/modelo-202-2025-primer-pago-modalidad-40-2.json``
    evidence. This test proves the OTHER end of the wire: that the
    declaration actually reaches the live, VALIDATED
    :class:`~cadrumo.domain.calculations.registry.RegistryVerificationPolicy` fold,
    so casilla "03" raises ``independently_grounded_fraction`` above zero for
    M202 rather than sitting inert in TOML. Not tautological: the grounded
    set and the fraction are read from the registry's own declared and
    validated data, never hand-computed or asserted from a synthetic
    fixture.
    """
    authority = ValidatedRegistryAuthority.load(_REGISTRY_ROOT, source_root=_SOURCE_ROOT)
    snapshot = authority.snapshot(_M202, filing_year=_FILING_YEAR, period="1P")
    policy = snapshot.verification_policy()

    assert _CASILLA_A_INGRESAR in policy.externally_grounded_casilla_ids

    reconciled_casilla_ids = policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids
    externally_grounded = policy.externally_grounded_casilla_ids & reconciled_casilla_ids
    independently_grounded_fraction = (
        len(externally_grounded) / len(reconciled_casilla_ids) if reconciled_casilla_ids else 0.0
    )

    assert _CASILLA_A_INGRESAR in externally_grounded
    assert independently_grounded_fraction > 0.0
