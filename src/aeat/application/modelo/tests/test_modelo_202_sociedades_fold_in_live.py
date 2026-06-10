"""W04.P12.S19 — Sociedades M202 cross-period folds fire on the LIVE calculate path.

The Impuesto sobre Sociedades fraccionado (Modelo 202) carries two cross-period
values that the operator must not re-key. Both are proven here end-to-end on the
LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`),
not the direct-resolver path the existing continuity tests exercise:

* **M202 cumulative self-carry** (``previous_period``). Casilla 30 ("Pagos
  fraccionados de periodos anteriores") is bound by
  ``modelo-202-2025-y-siguientes-pagos-fraccionados-anteriores``
  (``source = relation_prefill``), fed by the two self-pago relations
  ``modelo-202-2025-y-siguientes-rel-self-pagos-2p`` (period 2P, sums the 1P
  pago) and ``-rel-self-pagos-3p`` (period 3P, sums 1P + 2P), both reading
  ``source_output = '34'`` (the instalment ingresado). So a 2P calculate folds
  the prior 1P pago and a 3P calculate folds 1P + 2P.
* **M202 <- M200 cuota-base ejercicio anterior** (``cross_model_output``).
  Casilla 01 ("Importe de la base") is bound by
  ``modelo-202-2025-y-siguientes-cuota-base-ejercicio-anterior``
  (``source = relation_prefill``, ``selector source_modelo = '200',
  source_output = 'DP200014B:00592'``), fed by the cuota-base relations whose
  ``filing_year_delta`` selects the prior M200 cuota líquida. A 2P calculate
  folds the immediately prior M200 (filing_year_delta = -1) cuota líquida.

Each source period is seeded as a filed observation through the production
observation-persistence API
(:meth:`CalculationObservationRepository.save_observation`, the same write path
the local-file carry flow uses), stamped with the non-official ``app_filing``
source_kind, over a real encrypted-SQLite object store
(:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider` via
:func:`isolated_runtime_profile`). M202 is a sociedad surface: the live calculate
needs a legal-entity profile carrying ``taxpayer_type.entity_type =
legal_entity``, ``legal_entity_form = sl`` and ``incn_prior_12_months`` so the
``incn-prior-12-months`` profile binding resolves and the aggregate cross-store
agreement holds. No mocks, stubs, skips, or xfail.

Non-tautological: the seeded per-period c34 values are DISTINCT non-equal known
Decimals, so an off-by-period fold, a single-period copy, a silent blank, or a
coincidental sum cannot satisfy the cumulative assertion; the prior M200 cuota
líquida is a manual input no formula under test produces. The expected casilla
values derive from the seeded observations via the declared aggregation ops
(``sum`` / cross-year copy), never by re-evaluating any registry formula. A
change in the relation's ``source_output``, ``source_periods``, or
``aggregation`` op would red the assertion.

----------------------------------------------------------------------------
Coverage map for the W04.P12.S19 sociedades fold surface
----------------------------------------------------------------------------
* **M202 cumulative self-carry (casilla 30)** — newly proven LIVE here.
* **M202 <- M200 cuota-base (casilla 01)** — newly proven LIVE here.
* **M200 self BIN stock carry (00670) / dotaciones-deterioro (01494/01495)** —
  already driven through the REAL M200 engine by the direct-resolver continuity
  tests
  ``aeat.application.calculations.tests.test_modelo_200_bin_carry_forward_continuity``
  and ``...test_modelo_200_dotaciones_deterioro_carry_continuity``. The live
  operator path additionally requires the full six-binding legal-entity profile
  scaffold (``new-entity-flag``, ``incn-prior-12-months``,
  ``tributacion-estado-porcentaje``, ``sal-reserva-especial-dotada``,
  ``sal-capital-social``, ``legal-entity-form``) plus a zero-default for every
  other bound casilla; the carried value (00670) is reachable but adds no
  fold-wiring assurance beyond the direct-path proof, so it is cross-referenced
  rather than duplicated.
* **M200 <- M202 pagos fraccionados anuales** — REGISTRY WIRING GAP, NOT
  provable live. The relation ``modelo-200-2024-rel-202-pagos-fraccionados``
  (source_modelo 202, source_output 34, source_periods 1P/2P/3P, sum) and its
  target binding ``modelo-200-2024-pagos-fraccionados-anuales`` are declared and
  listed in the construct, but NO casilla in the M200/2024 revision declares
  ``binding = "modelo-200-2024-pagos-fraccionados-anuales"`` (contrast 00670,
  which IS bound to ``...-bin-pendiente-ejercicios-anteriores``). The binding is
  orphaned: ``resolve_bound_casilla_inputs`` only routes a binding value to a
  casilla that names it, so the folded M202 pagos sum never reaches a casilla
  value. The fold is unobservable on the live path until a casilla is wired to
  the binding; reported as a wiring gap (no fix in this test-only step).
* **M390 <- M303 iva** — already proven LIVE by
  ``test_modelo_390_303_fold_in_live`` (S16); not duplicated here.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaObservation,
    RegistryModeloObservation,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-m202-sociedades-fold"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_M202 = "202"
_M200 = "200"
_FILING_YEAR = 2025
_PRIOR_M200_YEAR = 2024  # filing_year_delta = -1 from the 2025 M202 ejercicio

# M202 source_output 34 is the instalment ingresado that the self-pago relations
# read; M200 source_output DP200014B:00592 is the prior cuota líquida the
# cuota-base relation reads.
_M202_PAGO_OUTPUT = "34"
_M200_CUOTA_LIQUIDA = "DP200014B:00592"

# Bound casillas on the M202/2025 revision under test.
_CASILLA_BASE = "01"  # bound by cuota-base-ejercicio-anterior (M202 <- M200)
_CASILLA_PAGOS_ANTERIORES = "30"  # bound by pagos-fraccionados-anteriores (self-carry)

# DISTINCT non-equal known per-period pago ingresado (M202 c34). Distinct values
# make the cumulative fold unmistakable: a single-period copy or off-by-period
# fold cannot reproduce the multi-period sum.
_M202_C34_BY_PERIOD: dict[str, Decimal] = {
    "1P": Decimal("1234.00"),
    "2P": Decimal("5678.50"),
}
# The prior M200 cuota líquida the 2P cuota-base relation folds (a manual input;
# distinct from every pago value so a cross-wired fold would surface).
_M200_PRIOR_CUOTA = Decimal("48000.00")

_RELATION_PREFILL_SOURCE = "relation_prefill"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_sociedad_profile() -> None:
    """Seed a legal-entity ``UserProfileRecord`` covering M202's profile binding.

    M202/2025 declares one ``source = "profile"`` binding,
    ``modelo-202-2025-y-siguientes-incn-prior-12-months`` (selector
    ``profile_model = taxpayer, field = incn_prior_12_months``). The live source
    mesh's profile resolver fills it from the persisted record, so the value is
    NOT hand-fed through the caller channel. ``entity_type`` and
    ``legal_entity_form`` describe the sociedad routing axis the corporate-tax
    facts hang off; ``display_name`` matches the ``isolated_runtime_profile``
    manifest label (``"Test runtime profile"``) so the loaded
    :class:`ProfileAggregate` passes its cross-store label-agreement validator.
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="B12345678"),
            UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
            UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=Decimal("500000")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _seed_m202_pago(*, period: str, value: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Persist one filed M202/2025 instalment carrying the c34 pago for ``period``."""
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_M202,
            filing_year=_FILING_YEAR,
            period=period,
            observations=(CasillaObservation(casilla_id=_M202_PAGO_OUTPUT, value=value),),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_m200_prior_cuota(*, cuota: Decimal, obs_repo: CalculationObservationRepository) -> None:
    """Persist the prior-year M200 cuota líquida (DP200014B:00592) the 2P base folds."""
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=_M200,
            filing_year=_PRIOR_M200_YEAR,
            period="0A",
            observations=(CasillaObservation(casilla_id=_M200_CUOTA_LIQUIDA, value=cuota),),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _calculate_m202(secure_objects: SecureObjectRepository, *, period: str) -> BucketAggregationCalculationResult:
    """Run the live M202/2025/<period> calculate over the seeded bucket.

    The two ``relation_prefill`` bindings (casilla 01 cuota-base, casilla 30
    pagos-anteriores) are deliberately left UNSET so the enrolled relation
    resolver folds them from the seeded observation store; the one ``profile``
    binding resolves from the seeded sociedad record. No ``binding_values`` are
    supplied so the live mesh is the sole value source.
    """
    _seed_sociedad_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot(_M202, filing_year=_FILING_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M202,
        filing_year=_FILING_YEAR,
        period=period,
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


def test_m202_2p_folds_prior_1p_pago_and_m200_cuota_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: M202 2P folds the prior 1P pago (casilla 30) and prior M200 cuota (casilla 01).

    With a 1P M202 instalment filed (c34) and a prior-year M200 cuota líquida
    recorded, a live calculate of the 2P instalment draws both relation chains
    through the enrolled ``RelationPrefillSourceResolver``:

    - casilla 30 (pagos-fraccionados-anteriores) == the 1P pago (sum over the one
      prior period the 2P self-pago relation declares).
    - casilla 01 (base) == the immediately prior M200 cuota líquida
      (filing_year_delta = -1 cross-model copy).
    """
    obs_repo = CalculationObservationRepository()
    _seed_m202_pago(period="1P", value=_M202_C34_BY_PERIOD["1P"], obs_repo=obs_repo)
    _seed_m200_prior_cuota(cuota=_M200_PRIOR_CUOTA, obs_repo=obs_repo)
    # Sanity: the prior pago and the prior cuota are distinct strictly-positive
    # values, so a cross-wired fold (cuota into pagos, or vice versa) would red
    # the per-casilla assertions below.
    assert _M202_C34_BY_PERIOD["1P"] != _M200_PRIOR_CUOTA
    assert _M202_C34_BY_PERIOD["1P"] > Decimal("0")
    assert Decimal("0") < _M200_PRIOR_CUOTA

    result = _calculate_m202(secure_objects, period="2P")

    values = result.revision.casilla_values
    assert Decimal(values[_CASILLA_PAGOS_ANTERIORES]) == _M202_C34_BY_PERIOD["1P"], (
        f"M202 2P casilla 30 must fold the prior 1P pago ({_M202_C34_BY_PERIOD['1P']}); "
        f"got {values[_CASILLA_PAGOS_ANTERIORES]}"
    )
    assert Decimal(values[_CASILLA_BASE]) == _M200_PRIOR_CUOTA, (
        f"M202 2P casilla 01 must fold the prior M200 cuota líquida ({_M200_PRIOR_CUOTA}); "
        f"got {values[_CASILLA_BASE]}"
    )

    # Both folds run through claimed sources: no relation_prefill diagnostic and
    # a clean resolution overall (the one profile binding resolves silently).
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    assert result.source_diagnostics == (), (
        f"M202 source_diagnostics must be clean for the sociedad fold persona; got {result.source_diagnostics}"
    )


def test_m202_3p_cumulates_prior_1p_and_2p_pagos_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: M202 3P folds the cumulative 1P + 2P pagos into casilla 30.

    With both the 1P and 2P M202 instalments filed (distinct c34 pagos), a live
    calculate of the 3P instalment draws the 3P self-pago relation
    (``source_periods = [1P, 2P]``, ``sum``) and casilla 30 equals the sum of the
    two prior pagos — the cumulative carry the M202 3P modalidad requires. The
    distinct per-period values make the two-term fold unmistakable: a
    single-period copy or off-by-period fold cannot reproduce the sum.
    """
    obs_repo = CalculationObservationRepository()
    _seed_m202_pago(period="1P", value=_M202_C34_BY_PERIOD["1P"], obs_repo=obs_repo)
    _seed_m202_pago(period="2P", value=_M202_C34_BY_PERIOD["2P"], obs_repo=obs_repo)
    _seed_m200_prior_cuota(cuota=_M200_PRIOR_CUOTA, obs_repo=obs_repo)
    expected_cumulative = _M202_C34_BY_PERIOD["1P"] + _M202_C34_BY_PERIOD["2P"]
    # Sanity: the two seeded pagos are distinct so a single-period copy fails.
    assert _M202_C34_BY_PERIOD["1P"] != _M202_C34_BY_PERIOD["2P"]
    assert expected_cumulative > _M202_C34_BY_PERIOD["1P"]

    result = _calculate_m202(secure_objects, period="3P")

    values = result.revision.casilla_values
    assert Decimal(values[_CASILLA_PAGOS_ANTERIORES]) == expected_cumulative, (
        f"M202 3P casilla 30 must cumulate the prior 1P + 2P pagos (sum {expected_cumulative}); "
        f"got {values[_CASILLA_PAGOS_ANTERIORES]}"
    )
    # casilla 01 still folds the prior M200 cuota (filing_year_delta = -1 holds for 3P too).
    assert Decimal(values[_CASILLA_BASE]) == _M200_PRIOR_CUOTA, (
        f"M202 3P casilla 01 must fold the prior M200 cuota líquida ({_M200_PRIOR_CUOTA}); "
        f"got {values[_CASILLA_BASE]}"
    )
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    assert result.source_diagnostics == ()


def test_m202_2p_no_prior_filing_resolves_zero_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """Pin the CURRENT live behaviour of an M202 2P fold with NO prior filing.

    Unlike the M100 0604 fold (which RAISES ``RegistryValidationError`` on an
    absent prior filing — finding #26, the directly-referenced cross-model
    relation has no supplied value), the M202 self-pago carry uses the
    ``previous_period`` ``prior_pagos_cumulative`` alignment and the M202 <- M200
    cuota-base carry tolerates an absent prior M200: both resolve present-or-zero
    rather than raising. With NO prior M202 1P and NO prior M200 in the store,
    the live 2P calculate succeeds and both folded casillas resolve to zero
    (a correct first-instalment zero, not a silent under-declaration of a
    declared prior). This documents the status quo and fails loudly if it
    drifts. (xfail/skip-free per the testing mandate.)
    """
    result = _calculate_m202(secure_objects, period="2P")

    values = result.revision.casilla_values
    assert Decimal(values[_CASILLA_PAGOS_ANTERIORES]) == Decimal("0"), (
        f"M202 2P casilla 30 with no prior 1P pago must resolve zero; got {values[_CASILLA_PAGOS_ANTERIORES]}"
    )
    assert Decimal(values[_CASILLA_BASE]) == Decimal("0"), (
        f"M202 2P casilla 01 with no prior M200 cuota must resolve zero; got {values[_CASILLA_BASE]}"
    )
    assert result.source_diagnostics == ()
