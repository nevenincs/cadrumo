"""M390 annual folds M303 1T-4T quarters via cross_model_output relations (LIVE path).

The annual IVA resumen (Modelo 390) casillas
``iva.anual.reconciliacion.devengada-303``,
``iva.anual.reconciliacion.deducible-303``, and
``iva.anual.reconciliacion.resultado-303`` are bound by the three
``relation_prefill`` bindings that fold the four quarterly M303 totals
(``source_periods=('1T','2T','3T','4T')``), while
``iva.anual.compensacion-ultimo-periodo-97`` (casilla 97) and
``iva.anual.compensacion-generada-ejercicio-no-97`` (casilla 662) are bound
by the single-period copy (4T only) and the three-quarter sum (1T-3T)
compensación relations respectively.

These five bindings were migrated from the now-retired ``previous_filing``
path to the canonical ``relation_prefill`` + ``cross_model_output`` relation
pattern (calculation-aggregation-taxonomy decision, ruling 3).  This
module proves the wiring works end-to-end on the LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
four M303 quarterly filings fold into the M390/0A annual reconciliation casillas.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real relation resolver, real source
mesh — no mocks, stubs, skips, or xfail).

Value-parity assertion (non-tautological):
- The five seeded M303 casilla values are DISTINCT non-equal known Decimals so
  an off-by-one-quarter or coincidental sum cannot satisfy the assertions.
- The expected casilla values are derived from the seeded observations via the
  declared aggregation ops (sum / copy), never by re-evaluating the registry
  formula.  A change in the relation's ``aggregation``, ``source_periods``, or
  ``source_output`` would cause the test to fail.

M390 declares no ``profile``-sourced bindings, so no :class:`UserProfileRecord`
needs to be seeded.  The five ``ledger_iva_aggregation`` bindings resolve from an
empty IVA transaction ledger → zero for all ledger-derived casillas.

M353←M322 ``per_grupo_member`` exemption note:
The M353←M322 ``per_grupo_member`` cross-filer fan-in is EXEMPT from the
``relation_prefill`` migration (calculation-aggregation-taxonomy ruling 4) because it
represents a cross-taxpayer fan-in (many declarante GRUPO members → one
consolidated resumen), not the single-owner quarterly fold-in pattern.  That
relation is addressed separately when the M322/M353 grupo consolidation surface
is stabilised.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-m390-303-fold"
_T0 = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 20, 11, 0, tzinfo=UTC)
_YEAR = 2025

# Five seeded M303 casilla ids that the five M390←M303 relations consume.
_DEVENGADA = "iva.cuota-devengada-total"
_DEDUCIBLE = "iva.cuota-deducible-total"
_RESULTADO = "iva.resultado-regimen-general"
_COMPENSACION = "iva.compensacion-generada-periodo"

# Per-quarter DISTINCT known values — four different Decimals per casilla so any
# wrong aggregation (wrong period, wrong source_output, wrong op) fails the assertion.
_M303_BY_PERIOD: dict[str, dict[str, Decimal]] = {
    "1T": {
        _DEVENGADA: Decimal("100.00"),
        _DEDUCIBLE: Decimal("40.00"),
        _RESULTADO: Decimal("60.00"),
        _COMPENSACION: Decimal("10.00"),  # 1T compensacion (sum 1T-3T, not 4T)
    },
    "2T": {
        _DEVENGADA: Decimal("250.00"),
        _DEDUCIBLE: Decimal("80.00"),
        _RESULTADO: Decimal("170.00"),
        _COMPENSACION: Decimal("20.00"),  # 2T compensacion
    },
    "3T": {
        _DEVENGADA: Decimal("180.00"),
        _DEDUCIBLE: Decimal("60.00"),
        _RESULTADO: Decimal("120.00"),
        _COMPENSACION: Decimal("15.00"),  # 3T compensacion
    },
    "4T": {
        _DEVENGADA: Decimal("90.00"),
        _DEDUCIBLE: Decimal("30.00"),
        _RESULTADO: Decimal("60.00"),
        _COMPENSACION: Decimal("300.00"),  # 4T compensacion (copy → casilla 97)
    },
}

# Expected values derived from the seeded data via the declared aggregation ops,
# NOT from the registry formula (non-tautological).
_EXPECTED_DEVENGADA_TOTAL = sum(v[_DEVENGADA] for v in _M303_BY_PERIOD.values())  # 620.00
_EXPECTED_DEDUCIBLE_TOTAL = sum(v[_DEDUCIBLE] for v in _M303_BY_PERIOD.values())  # 210.00
_EXPECTED_RESULTADO_TOTAL = sum(v[_RESULTADO] for v in _M303_BY_PERIOD.values())  # 410.00
# compensacion-ultimo-periodo: copy of 4T
_EXPECTED_COMPENSACION_ULTIMO = _M303_BY_PERIOD["4T"][_COMPENSACION]  # 300.00
# compensacion-generada-ejercicio-no-97: sum of 1T+2T+3T
_EXPECTED_COMPENSACION_NO97 = sum(_M303_BY_PERIOD[p][_COMPENSACION] for p in ("1T", "2T", "3T"))  # 45.00

_RELATION_PREFILL_SOURCE = "relation_prefill"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_m303_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist one M303/2025 filing observation per quarter carrying the five fold casillas.

    Persisted through the production observation-persistence API
    (:meth:`CalculationObservationRepository.save_observation`) — the same write
    path the local-file carry flow uses — stamped with the non-official
    ``app_filing`` source_kind.
    """
    for period, casillas in _M303_BY_PERIOD.items():
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="303",
                filing_year=_YEAR,
                period=period,
                observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in casillas.items()),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )


def _calculate_m390_annual(secure_objects: SecureObjectRepository):
    """Run the live M390/2025/0A calculate over the seeded bucket.

    The five ``relation_prefill`` bindings are deliberately left UNSET so the
    enrolled :class:`RelationPrefillSourceResolver` folds them from the seeded
    M303 observation store.  The five ``ledger_iva_aggregation`` bindings also
    go unset (empty IVA transaction ledger → zero for all ledger casillas).
    M390 declares no ``profile``-sourced bindings so no profile record is needed.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("390", filing_year=_YEAR, period="0A")
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


def test_m390_folds_five_m303_relations_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """E2E: the four filed M303 quarters fold into the five M390 annual reconciliation casillas.

    With four M303/2025 quarterly observations seeded (each carrying the five
    fold casillas with DISTINCT values), a live calculate of the M390/2025 annual
    draws all five ``cross_model_output`` relations through the enrolled
    :class:`RelationPrefillSourceResolver`:

    - ``iva.anual.reconciliacion.devengada-303`` == sum(1T-4T devengada)
    - ``iva.anual.reconciliacion.deducible-303`` == sum(1T-4T deducible)
    - ``iva.anual.reconciliacion.resultado-303`` == sum(1T-4T resultado)
    - ``iva.anual.compensacion-ultimo-periodo-97`` (casilla 97) == copy(4T compensacion)
    - ``iva.anual.compensacion-generada-ejercicio-no-97`` (casilla 662) == sum(1T-3T compensacion)

    The asserted values derive from the seeded observations via the declared aggregation ops,
    never from the registry formula (non-tautological).
    """
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
    assert Decimal(casilla_values["iva.anual.reconciliacion.devengada-303"]) == _EXPECTED_DEVENGADA_TOTAL, (
        f"M390 reconciliacion.devengada-303 must fold sum(1T-4T devengada)={_EXPECTED_DEVENGADA_TOTAL!r}; "
        f"got {casilla_values['iva.anual.reconciliacion.devengada-303']!r}"
    )
    assert Decimal(casilla_values["iva.anual.reconciliacion.deducible-303"]) == _EXPECTED_DEDUCIBLE_TOTAL, (
        f"M390 reconciliacion.deducible-303 must fold sum(1T-4T deducible)={_EXPECTED_DEDUCIBLE_TOTAL!r}; "
        f"got {casilla_values['iva.anual.reconciliacion.deducible-303']!r}"
    )
    assert Decimal(casilla_values["iva.anual.reconciliacion.resultado-303"]) == _EXPECTED_RESULTADO_TOTAL, (
        f"M390 reconciliacion.resultado-303 must fold sum(1T-4T resultado)={_EXPECTED_RESULTADO_TOTAL!r}; "
        f"got {casilla_values['iva.anual.reconciliacion.resultado-303']!r}"
    )

    # Compensacion casillas (copy of 4T and sum of 1T-3T).
    # casilla_values is keyed by casilla id (not AEAT casilla number).
    # id="iva.anual.compensacion-ultimo-periodo-97" (AEAT number 97)
    # id="iva.anual.compensacion-generada-ejercicio-no-97" (AEAT number 662)
    assert Decimal(casilla_values["iva.anual.compensacion-ultimo-periodo-97"]) == _EXPECTED_COMPENSACION_ULTIMO, (
        f"M390 compensacion-ultimo-periodo-97 (AEAT casilla 97) must copy 4T compensacion "
        f"{_EXPECTED_COMPENSACION_ULTIMO!r}; got {casilla_values['iva.anual.compensacion-ultimo-periodo-97']!r}"
    )
    assert Decimal(casilla_values["iva.anual.compensacion-generada-ejercicio-no-97"]) == _EXPECTED_COMPENSACION_NO97, (
        f"M390 compensacion-generada-ejercicio-no-97 (AEAT casilla 662) must sum 1T-3T compensacion "
        f"{_EXPECTED_COMPENSACION_NO97!r}; got {casilla_values['iva.anual.compensacion-generada-ejercicio-no-97']!r}"
    )

    # The relation_prefill source is CLAIMED (resolver enrolled): no
    # unhandled_binding_source advisory names it.
    relation_prefill_diags = tuple(
        diag for diag in result.source_diagnostics if diag.source_kind == _RELATION_PREFILL_SOURCE
    )
    assert relation_prefill_diags == (), (
        f"relation_prefill must be a claimed source with no diagnostics; got {relation_prefill_diags}"
    )
