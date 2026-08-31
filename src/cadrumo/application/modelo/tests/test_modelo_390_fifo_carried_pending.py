"""M390 year-end carry boxes 97/662 as a FIFO partition - the DISCRIMINATING case.

Companion to ``test_modelo_390_303_fold_in_live.py``. That module proves the
ordinary M390<-M303 relations and the annual compensation partition source run on
the live calculate path, but its fixture seeds independent per-period
``iva.compensacion-generada-periodo`` with NO carried pending chain (each
period's disponible equals its own generated credit). In
that degenerate case the FIFO partition and the naive per-period split COINCIDE
(box 97 = copy(4T generated), box 662 = sum(1T-3T generated)), so the existing
test cannot tell whether the box-97/662 values came from the declared FIFO
annual-partition source (#7/#12, IVA-1/IVA-2) or from the un-fixed naive relation sums.

This module closes that coverage hole with a REAL carried-pending chain driven
through the full operator calculate action
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`),
choosing inputs where the FIFO partition DIVERGES from the naive split, so the
test FAILS if the annual-partition source is ever removed and the naive relation
sums leak through.

Scenario (the AEAT "always-carry" case - every period's credit carries forward
into the last period's autoliquidacion, nothing consumed):

    period  generada  aplicada  disponible(available_end)
    1T      100.00    0.00      100.00
    2T       20.00    0.00      120.00   (100 carried + 20 new)
    3T       30.00    0.00      150.00   (120 carried + 30 new)
    4T       50.00    0.00      200.00   (150 carried + 50 new)

The year generated 100+20+30+50 = 200.00 of compensacion credit and consumed
none, so the whole 200.00 is pending and ALL of it is carried into the 4T
autoliquidacion (4T disponible = 200.00).

Oracle (grounded in the carried-pending inputs + the AEAT identity
``[86] = [95] - [97] - [98] - [662]`` -> ``[97] + [662] = year pending``, NOT in
the registry formula under test):
  - AEAT box 97 ``iva.anual.compensacion-ultimo-periodo-97`` = credit carried
    INTO the last period = the whole year pending = 200.00 (because every
    quarter's credit carried forward into 4T).
  - AEAT box 662 ``iva.anual.compensacion-generada-ejercicio-no-97`` = year
    credit NOT carried into the last period = 0.00.

Divergence proof (what the un-fixed naive per-period relation split would give):
  - naive box 97 = copy(4T generada) = 50.00  != FIFO 200.00
  - naive box 662 = sum(1T-3T generada) = 100+20+30 = 150.00  != FIFO 0.00
Both partitions satisfy the identity (200 = 50+150 = 200+0), so a test that only
checked the sum would not discriminate; this test asserts the PARTITION.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real relation resolver, real source
mesh - no mocks, stubs, skips, or xfail), mirroring the companion module's
harness.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.result_disposition import ResultDisposition
from ....core.period import Period
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.iva_compensation.filed_derivation import M303_COMPENSATION_POSTERIOR_CASILLA, M303_COMPENSATION_RESULTADO_CASILLA
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, ResultDispositionProjection
from .._calculation_actions import calculate_modelo_revision_from_bucket_aggregation_with_diagnostics
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000390"
_PROFILE_LABEL = "M390 FIFO profile"
_T0 = datetime(2026, 1, 20, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 20, 11, 0, tzinfo=UTC)
_YEAR = 2025


# M303 compensacion casillas the annual partition source reads to build each period's state.
_GENERADA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_APLICADA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_DISPONIBLE: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")

# M390 annual carry boxes the partition overrides.
_M390_BOX_97: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_BOX_662: CasillaId = validated_casilla_id("iva.anual.compensacion-generada-ejercicio-no-97")

# Carried-pending chain: every quarter generates credit, none is consumed, and
# each quarter's disponible accumulates the prior quarters' unconsumed saldo, so
# the whole year's credit carries into the 4T autoliquidacion.
_M303_COMPENSACION_BY_PERIOD: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-100.00"),
        _GENERADA: Decimal("100.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("0.00"),
        _DISPONIBLE: Decimal("100.00"),
    },
    "2T": {
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-20.00"),
        _GENERADA: Decimal("20.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("100.00"),
        _DISPONIBLE: Decimal("120.00"),
    },
    "3T": {
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-30.00"),
        _GENERADA: Decimal("30.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("120.00"),
        _DISPONIBLE: Decimal("150.00"),
    },
    "4T": {
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-50.00"),
        _GENERADA: Decimal("50.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("150.00"),
        _DISPONIBLE: Decimal("200.00"),
    },
}

# Oracle from the carried-pending inputs + AEAT identity (NOT the registry formula).
_YEAR_PENDING = sum(v[_GENERADA] for v in _M303_COMPENSACION_BY_PERIOD.values())  # 200.00
_EXPECTED_BOX_97 = Decimal("200.00")  # whole year pending carried into 4T
_EXPECTED_BOX_662 = Decimal("0.00")  # nothing left the chain

# The un-fixed naive per-period relation split (what this test must NOT see).
_NAIVE_BOX_97 = _M303_COMPENSACION_BY_PERIOD["4T"][_GENERADA]  # copy(4T) = 50.00
_NAIVE_BOX_662 = sum(  # sum(1T-3T) = 150.00
    _M303_COMPENSACION_BY_PERIOD[p][_GENERADA] for p in ("1T", "2T", "3T")
)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_PROFILE_LABEL) as profile:
        seed_test_profile_record(
            UserProfileRecord(
                setup_state=ProfileSetupState.COMPLETE,
                profile_id=_BUCKET_ID,
                facts=(
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
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
                    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
                ),
                created_at=_T0,
                updated_at=_T0,
            ),
        )
        yield profile.repository


def _seed_m303_compensacion_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist one M303/2025 filing observation per quarter carrying the FIFO compensacion casillas."""
    for period, casillas in _M303_COMPENSACION_BY_PERIOD.items():
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


def _calculate_m390_annual(secure_objects: SecureObjectRepository):
    """Run the live M390/2025/0A calculate over the seeded bucket (carry boxes left UNSET)."""
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


def test_m390_carry_boxes_are_the_fifo_partition_not_the_naive_split(
    secure_objects: SecureObjectRepository,
) -> None:
    """A carried-pending chain drives box 97/662 to the FIFO partition, diverging from the naive split.

    With four M303/2025 quarters whose credit carries forward unconsumed into 4T,
    the live M390 calculate must produce the FIFO partition (box 97 = 200.00 whole
    year pending, box 662 = 0.00), NOT the naive per-period relation split
    (box 97 = copy(4T) = 50.00, box 662 = sum(1T-3T) = 150.00). The expected
    values are derived from the carried-pending inputs and the AEAT identity, not
    the registry formula.
    """
    # Guard the fixture's own divergence premise: FIFO oracle must differ from naive.
    assert _EXPECTED_BOX_97 != _NAIVE_BOX_97, "fixture must make box 97 diverge from the naive copy(4T)"
    assert _EXPECTED_BOX_662 != _NAIVE_BOX_662, "fixture must make box 662 diverge from the naive sum(1T-3T)"
    # AEAT identity holds for both partitions (so only the partition discriminates).
    assert _EXPECTED_BOX_97 + _EXPECTED_BOX_662 == _YEAR_PENDING
    assert _NAIVE_BOX_97 + _NAIVE_BOX_662 == _YEAR_PENDING

    obs_repo = CalculationObservationRepository()
    _seed_m303_compensacion_quarters(obs_repo=obs_repo)

    result = _calculate_m390_annual(secure_objects)
    casilla_values = result.revision.casilla_values

    box_97 = Decimal(casilla_values[_M390_BOX_97])
    box_662 = Decimal(casilla_values[_M390_BOX_662])

    # The carried-pending credit all flows into the last period: box 97 carries
    # the whole year pending, box 662 is zero (the FIFO partition).
    assert box_97 == _EXPECTED_BOX_97, (
        f"M390 box 97 (compensacion-ultimo-periodo) must be the FIFO whole-year-pending {_EXPECTED_BOX_97!r} "
        f"for an all-carry chain, NOT the naive copy(4T)={_NAIVE_BOX_97!r}; got {box_97!r}"
    )
    assert box_662 == _EXPECTED_BOX_662, (
        f"M390 box 662 (compensacion-generada-ejercicio-no-97) must be the FIFO remainder {_EXPECTED_BOX_662!r} "
        f"(no credit left the chain), NOT the naive sum(1T-3T)={_NAIVE_BOX_662!r}; got {box_662!r}"
    )

    # Belt-and-braces: the result must NOT be the naive split (the un-fixed behaviour).
    assert (box_97, box_662) != (_NAIVE_BOX_97, _NAIVE_BOX_662), (
        "M390 carry boxes collapsed to the naive per-period split - the annual partition source is not firing"
    )
    # The AEAT partition identity is preserved through the full calculate.
    assert box_97 + box_662 == _YEAR_PENDING, (
        f"M390 carry partition must satisfy [97]+[662]==year pending {_YEAR_PENDING!r}; got {box_97 + box_662!r}"
    )
