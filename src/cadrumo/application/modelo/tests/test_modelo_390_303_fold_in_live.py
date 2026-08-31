"""M390 annual folds M303 quarters through relations plus the IVA partition source.

The annual IVA resumen (Modelo 390) casillas
``iva.anual.reconciliacion.devengada-303``,
``iva.anual.reconciliacion.deducible-303``, and
``iva.anual.reconciliacion.resultado-303`` are bound by the three
``relation_prefill`` bindings that fold the four quarterly M303 totals
(``source_periods=('1T','2T','3T','4T')``), while
``iva.anual.compensacion-ultimo-periodo-97`` (casilla 97) and
``iva.anual.compensacion-generada-ejercicio-no-97`` (casilla 662) are bound
by ``iva_compensation_annual_partition`` from the filed M303 compensation FIFO
carry projection.

The ordinary annual-total bindings migrated from the now-retired
``previous_filing`` path to the canonical ``relation_prefill`` +
``cross_model_output`` relation pattern (calculation-aggregation-taxonomy
decision, ruling 3). The compensation boxes are not independent copy/sum folds;
they are one annual FIFO partition. This module proves both wiring paths work
end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
four M303 quarterly filings fold into the M390/0A annual reconciliation casillas.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real relation / annual-partition
resolvers, real source mesh — no mocks, stubs, skips, or xfail).

Value-parity assertion (non-tautological):
- The seeded M303 casilla values are DISTINCT non-equal known Decimals so
  an off-by-one-quarter or coincidental sum cannot satisfy the assertions.
- The expected casilla values are derived from the seeded observations via the
  declared relation aggregation ops for the ordinary totals and the FIFO
  partition for boxes 97 / 662, never by re-evaluating the registry formula.

The calculation itself still takes its relation values from filed M303
observations, but the current work-unit readiness gate requires a ready profile
before creating the M390 work unit. The five ``ledger_iva_aggregation`` bindings
resolve from an empty IVA transaction ledger → zero for all ledger-derived
casillas.

M353←M322 ``per_grupo_member`` exemption note:
The M353←M322 ``per_grupo_member`` cross-filer fan-in is EXEMPT from the
``relation_prefill`` migration (calculation-aggregation-taxonomy ruling 4) because it
represents a cross-taxpayer fan-in (many declarante GRUPO members → one
consolidated resumen), not the single-owner quarterly fold-in pattern.  That
relation is addressed separately when the M322/M353 grupo consolidation surface
is stabilised.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.iva_compensation.filed_derivation import M303_COMPENSATION_RESULTADO_CASILLA
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...calculations.observations_repository import CalculationObservationRepository, ResultDispositionProjection
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "39000000-0000-4000-8000-000000000390"
_T0 = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 20, 11, 0, tzinfo=UTC)
_YEAR = 2025
_TAX_ID = "12345678Z"


# Seeded M303 casilla ids consumed by the three M390←M303 relations and the
# annual compensation partition source.
_DEVENGADA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_RESULTADO: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_COMPENSACION: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.devengada-303")
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.deducible-303")
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = validated_casilla_id("iva.anual.reconciliacion.resultado-303")
# Régimen simplificado settles annually in the 4T Modelo 303 only (casilla 54,
# "RS - Total cuota resultante"); the fourth relation copies that single 4T
# value onto the M390 resumen anual (box 79), never summed across quarters.
_SIMPLIFICADO_DEVENGADA: CasillaId = validated_casilla_id("54")
_M390_RECONCILIACION_DEVENGADA_SIMPLIFICADO_303_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.reconciliacion.devengada-simplificado-303"
)
_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = validated_casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97"
)

# Per-quarter DISTINCT known values — four different Decimals per casilla so any
# wrong aggregation (wrong period, wrong source_casilla_id, wrong op) fails the assertion.
_M303_BY_PERIOD: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _DEVENGADA: Decimal("100.00"),
        _DEDUCIBLE: Decimal("40.00"),
        _RESULTADO: Decimal("60.00"),
        _COMPENSACION: Decimal("10.00"),  # 1T compensacion
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-10.00"),
    },
    "2T": {
        _DEVENGADA: Decimal("250.00"),
        _DEDUCIBLE: Decimal("80.00"),
        _RESULTADO: Decimal("170.00"),
        _COMPENSACION: Decimal("20.00"),  # 2T compensacion
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-20.00"),
    },
    "3T": {
        _DEVENGADA: Decimal("180.00"),
        _DEDUCIBLE: Decimal("60.00"),
        _RESULTADO: Decimal("120.00"),
        _COMPENSACION: Decimal("15.00"),  # 3T compensacion
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-15.00"),
    },
    "4T": {
        _DEVENGADA: Decimal("90.00"),
        _DEDUCIBLE: Decimal("30.00"),
        _RESULTADO: Decimal("60.00"),
        _COMPENSACION: Decimal("300.00"),  # 4T compensacion
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-300.00"),
        _SIMPLIFICADO_DEVENGADA: Decimal("45.00"),  # RS casilla 54, 4T only
    },
}

# Expected values derived from the seeded data via the declared aggregation ops,
# NOT from the registry formula (non-tautological).
_EXPECTED_DEVENGADA_TOTAL = sum(v[_DEVENGADA] for v in _M303_BY_PERIOD.values())  # 620.00
_EXPECTED_DEDUCIBLE_TOTAL = sum(v[_DEDUCIBLE] for v in _M303_BY_PERIOD.values())  # 210.00
_EXPECTED_RESULTADO_TOTAL = sum(v[_RESULTADO] for v in _M303_BY_PERIOD.values())  # 410.00
# In this degenerate no-carried-pending fixture, the FIFO partition coincides
# numerically with the historical copy/sum split: 4T carries 300.00 and the
# 1T-3T generated amounts remain outside the last period.
_EXPECTED_COMPENSACION_ULTIMO = _M303_BY_PERIOD["4T"][_COMPENSACION]  # 300.00
_EXPECTED_COMPENSACION_NO97 = sum(_M303_BY_PERIOD[p][_COMPENSACION] for p in ("1T", "2T", "3T"))  # 45.00
_EXPECTED_SIMPLIFICADO_DEVENGADA = _M303_BY_PERIOD["4T"][_SIMPLIFICADO_DEVENGADA]  # 45.00, copied not summed

_RELATION_PREFILL_SOURCE = "relation_prefill"
_ANNUAL_PARTITION_SOURCE = "iva_compensation_annual_partition"


def _seed_m303_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist one M303/2025 filing observation per quarter carrying the five fold casillas.

    Persisted through the production observation-persistence API
    (:meth:`CalculationObservationRepository.save_observation`) — the same write
    path the local-file carry flow uses — stamped with the non-official
    ``app_filing`` source_kind.
    """
    for period, casillas in _M303_BY_PERIOD.items():
        obs_repo.save(
            obs_repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="303",
                    filing_year=_YEAR,
                    period=period,
                    observations=registry_grounded_observations(
                        modelo="303",
                        filing_year=_YEAR,
                        period=period,
                        casilla_values=casillas,
                    ),
                ),
                source_kind=APP_FILING_SOURCE_KIND,
                captured_at=_T0,
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.COMPENSACION,
                    provenance_kind="app_filing",
                    provenance_locator=f"test-local-filing:{_YEAR}:{period}",
                ),
                normalize_m303_carry=True,
            )
        )


def _store_ready_profile(secure_objects: SecureObjectRepository) -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value=_TAX_ID),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _calculate_m390_annual(secure_objects: SecureObjectRepository):
    """Run the live M390/2025/0A calculate over the seeded bucket.

    The three ``relation_prefill`` bindings and the two
    ``iva_compensation_annual_partition`` bindings are deliberately left UNSET
    so enrolled source resolvers derive them from the seeded M303 observation
    store. The five ``ledger_iva_aggregation`` bindings also go unset (empty IVA
    transaction ledger -> zero for all ledger casillas). A ready profile is
    pre-seeded for the work-unit readiness gate; assertions still come solely
    from the seeded M303 observation store.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values={},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def test_m390_folds_m303_relations_and_compensation_partition_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: filed M303 quarters feed M390 annual relations and compensation partition.

    With four M303/2025 quarterly observations seeded (each carrying the
    fold casillas with DISTINCT values), a live calculate of the M390/2025 annual
    draws four ``cross_model_output`` relations through the enrolled
    :class:`RelationPrefillSourceResolver` and the two compensation boxes through
    ``IvaCompensationAnnualPartitionSourceResolver``:

    - ``iva.anual.reconciliacion.devengada-303`` == sum(1T-4T devengada)
    - ``iva.anual.reconciliacion.deducible-303`` == sum(1T-4T deducible)
    - ``iva.anual.reconciliacion.resultado-303`` == sum(1T-4T resultado)
    - ``iva.anual.reconciliacion.devengada-simplificado-303`` (casilla 79) == copy(4T casilla 54)
    - ``iva.anual.compensacion-ultimo-periodo-97`` (casilla 97) == FIFO last-period partition
    - ``iva.anual.compensacion-generada-ejercicio-no-97`` (casilla 662) == FIFO remainder partition

    The asserted values derive from the seeded observations via the declared source mechanisms,
    never from the registry formula (non-tautological).
    """
    _store_ready_profile(secure_objects)
    obs_repo = CalculationObservationRepository()
    _seed_m303_quarters(obs_repo=obs_repo)

    # Sanity: the seeded devengada values are distinct so a silent blank or
    # single-quarter copy cannot satisfy the assertion.
    devengada_values = [_M303_BY_PERIOD[p][_DEVENGADA] for p in ("1T", "2T", "3T", "4T")]
    assert len(set(devengada_values)) == 4, "test requires DISTINCT per-quarter devengada values"
    assert Decimal("620.00") == _EXPECTED_DEVENGADA_TOTAL

    result = _calculate_m390_annual(secure_objects)

    casilla_values = result.revision.casilla_values

    # Reconciliation casillas (sum of four 303 quarters via relation fold).
    assert Decimal(casilla_values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA]) == _EXPECTED_DEVENGADA_TOTAL, (
        f"M390 reconciliacion.devengada-303 must fold sum(1T-4T devengada)={_EXPECTED_DEVENGADA_TOTAL!r}; "
        f"got {casilla_values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA]!r}"
    )
    assert Decimal(casilla_values[_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA]) == _EXPECTED_DEDUCIBLE_TOTAL, (
        f"M390 reconciliacion.deducible-303 must fold sum(1T-4T deducible)={_EXPECTED_DEDUCIBLE_TOTAL!r}; "
        f"got {casilla_values[_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA]!r}"
    )
    assert Decimal(casilla_values[_M390_RECONCILIACION_RESULTADO_303_CASILLA]) == _EXPECTED_RESULTADO_TOTAL, (
        f"M390 reconciliacion.resultado-303 must fold sum(1T-4T resultado)={_EXPECTED_RESULTADO_TOTAL!r}; "
        f"got {casilla_values[_M390_RECONCILIACION_RESULTADO_303_CASILLA]!r}"
    )
    assert (
        Decimal(casilla_values[_M390_RECONCILIACION_DEVENGADA_SIMPLIFICADO_303_CASILLA])
        == _EXPECTED_SIMPLIFICADO_DEVENGADA
    ), (
        f"M390 reconciliacion.devengada-simplificado-303 (AEAT casilla 79) must copy the 4T "
        f"régimen simplificado casilla 54={_EXPECTED_SIMPLIFICADO_DEVENGADA!r}; "
        f"got {casilla_values[_M390_RECONCILIACION_DEVENGADA_SIMPLIFICADO_303_CASILLA]!r}"
    )

    # Compensacion casillas (FIFO annual partition).
    # casilla_values is keyed by casilla id (not AEAT casilla number).
    # id="iva.anual.compensacion-ultimo-periodo-97" (AEAT number 97)
    # id="iva.anual.compensacion-generada-ejercicio-no-97" (AEAT number 662)
    assert Decimal(casilla_values[_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA]) == _EXPECTED_COMPENSACION_ULTIMO, (
        f"M390 compensacion-ultimo-periodo-97 (AEAT casilla 97) must carry the FIFO last-period partition "
        f"{_EXPECTED_COMPENSACION_ULTIMO!r}; got {casilla_values[_M390_COMPENSACION_ULTIMO_PERIODO_CASILLA]!r}"
    )
    assert (
        Decimal(casilla_values[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA]) == _EXPECTED_COMPENSACION_NO97
    ), (
        f"M390 compensacion-generada-ejercicio-no-97 (AEAT casilla 662) must carry the FIFO remainder partition "
        f"{_EXPECTED_COMPENSACION_NO97!r}; "
        f"got {casilla_values[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA]!r}"
    )

    # The relation_prefill source is CLAIMED (resolver enrolled): no
    # unhandled_binding_source advisory names it.
    relation_prefill_diags = tuple(
        diag for diag in result.source_diagnostics if diag.source_kind == _RELATION_PREFILL_SOURCE
    )
    assert relation_prefill_diags == (), (
        f"relation_prefill must be a claimed source with no diagnostics; got {relation_prefill_diags}"
    )
    annual_partition_diags = tuple(
        diag for diag in result.source_diagnostics if diag.source_kind == _ANNUAL_PARTITION_SOURCE
    )
    assert annual_partition_diags == (), (
        f"iva_compensation_annual_partition must be a claimed source with no diagnostics; got {annual_partition_diags}"
    )
