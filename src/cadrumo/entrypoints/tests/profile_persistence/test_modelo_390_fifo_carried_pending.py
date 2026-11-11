"""M390 year-end carry boxes 97/662 as a FIFO partition - the DISCRIMINATING case.

Companion to ``test_modelo_390_303_fold_in_live.py``. That module proves the
ordinary M390<-M303 relations and the annual compensation partition source run on
the live calculate path, but its fixture seeds independent per-period
``iva.compensacion-generada-periodo`` with NO carried pending chain and no
consumption (each period's disponible equals its own generated credit). In that
degenerate case the FIFO partition and the naive per-period split COINCIDE
(box 97 = copy(4T generated), box 662 = sum(1T-3T generated)), so the existing
test cannot tell whether the box-97/662 values came from the declared FIFO
annual-partition source or from the un-fixed naive relation sums.

This module closes that coverage hole with a REAL carried-pending chain in which
part of the carried credit is consumed, driven through the full operator
calculate action
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`),
choosing inputs where the FIFO partition DIVERGES from the naive split, so the
test FAILS if the annual-partition source is ever removed and the naive relation
sums leak through.

Scenario (credit carries forward, and 2T consumes part of 1T's credit):

    period  generada  aplicada  disponible(available_end)
    1T      100.00    0.00      100.00
    2T        0.00   60.00       40.00   (100 carried, 60 applied against a payable quota)
    3T       30.00    0.00       70.00   (40 carried + 30 new)
    4T       50.00    0.00      120.00   (70 carried + 50 new)

The year generated 100+30+50 = 180.00 of compensacion credit and consumed 60.00,
so 120.00 is pending at year end. Compensation is consumed oldest credit first,
so the 60.00 comes out of 1T's lot and 40.00 of it remains.

Oracle (grounded in the carried-pending inputs + the AEAT identity
``[86] = [95] - [97] - [98] - [662]`` -> ``[97] + [662] = year pending``, NOT in
the registry formula under test; the IVA manual's worked example puts in box 97
what the last period itself generated and the rest of the pending credit of the
year in box 662):
  - AEAT box 97 ``iva.anual.compensacion-ultimo-periodo-97`` = credit generated
    by the last period = 50.00 (none of it was consumed).
  - AEAT box 662 ``iva.anual.compensacion-generada-ejercicio-no-97`` = the rest
    of the year's pending credit = 120.00 - 50.00 = 70.00 (40.00 of 1T's lot and
    30.00 of 3T's).

Divergence proof (what the un-fixed naive per-period relation split would give):
  - naive box 97 = copy(4T generada) = 50.00 (the same)
  - naive box 662 = sum(1T-3T generada) = 100+0+30 = 130.00  != FIFO 70.00
The naive split ignores the 60.00 consumed, so it breaks the identity
(50 + 130 = 180 != 120 pending), and a test that only checked box 97 would not
discriminate; this test asserts the PARTITION.

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralBucketSession`, real
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

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.ready_profile_support import seed_ready_profile
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....core.result_disposition import ResultDisposition
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_POSTERIOR_CASILLA,
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from ....domain.calculations.registry.tests.authored_editions import filing_grade_exercises, filing_year_envelope
from .file_flow_test_support import calculation_ports_for_test
from .observation_seeding_support import save_local_m303_compensacion_filings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "00000000-0000-4000-8000-000000000390"
_PROFILE_LABEL = "M390 FIFO profile"
_T0 = datetime(filing_year_envelope().horizon, 1, 20, 10, 0, tzinfo=UTC)
_T1 = datetime(filing_year_envelope().horizon, 1, 20, 11, 0, tzinfo=UTC)
_YEAR = filing_grade_exercises("390")[-1]


# M303 compensacion casillas the annual partition source reads to build each period's state.
_GENERADA: CasillaId = validated_casilla_id("iva.compensacion-generada-periodo")
_APLICADA: CasillaId = validated_casilla_id("iva.compensacion-aplicada-periodo")
_DISPONIBLE: CasillaId = validated_casilla_id("iva.compensacion-disponible-fin-periodo")

# A quarter's credit comes from its own general-regime totals: a filed 303 states
# them, and the annual reconciliation slots fold them. This filer applies no
# prorrata, so its 4T filed a [44] of zero.
_DEVENGADA: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_DEDUCIBLE: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_RESULTADO_GENERAL: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_PRORRATA_REGULARIZACION: CasillaId = validated_casilla_id("44")

# M390 annual carry boxes the partition overrides.
_M390_BOX_97: CasillaId = validated_casilla_id("iva.anual.compensacion-ultimo-periodo-97")
_M390_BOX_662: CasillaId = validated_casilla_id("iva.anual.compensacion-generada-ejercicio-no-97")

# Carried-pending chain: 1T generates credit, 2T consumes part of it against a
# payable quota, and 3T and 4T generate more; each quarter's disponible is the
# prior quarter's disponible plus what it generates less what it applies.
_M303_COMPENSACION_BY_PERIOD: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _DEVENGADA: Decimal("0.00"),
        _DEDUCIBLE: Decimal("100.00"),
        _RESULTADO_GENERAL: Decimal("-100.00"),
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-100.00"),
        _GENERADA: Decimal("100.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("0.00"),
        _DISPONIBLE: Decimal("100.00"),
    },
    "2T": {
        _DEVENGADA: Decimal("60.00"),
        _DEDUCIBLE: Decimal("0.00"),
        _RESULTADO_GENERAL: Decimal("60.00"),
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("60.00"),
        _GENERADA: Decimal("0.00"),
        _APLICADA: Decimal("60.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("40.00"),
        _DISPONIBLE: Decimal("40.00"),
    },
    "3T": {
        _DEVENGADA: Decimal("0.00"),
        _DEDUCIBLE: Decimal("30.00"),
        _RESULTADO_GENERAL: Decimal("-30.00"),
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-30.00"),
        _GENERADA: Decimal("30.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("40.00"),
        _DISPONIBLE: Decimal("70.00"),
    },
    "4T": {
        _DEVENGADA: Decimal("0.00"),
        _DEDUCIBLE: Decimal("50.00"),
        _RESULTADO_GENERAL: Decimal("-50.00"),
        _PRORRATA_REGULARIZACION: Decimal("0.00"),
        M303_COMPENSATION_RESULTADO_CASILLA: Decimal("-50.00"),
        _GENERADA: Decimal("50.00"),
        _APLICADA: Decimal("0.00"),
        M303_COMPENSATION_POSTERIOR_CASILLA: Decimal("70.00"),
        _DISPONIBLE: Decimal("120.00"),
    },
}

# Oracle from the carried-pending inputs + AEAT identity (NOT the registry formula).
_YEAR_PENDING = sum(  # 100 + 30 + 50 generated, less the 60 applied = 120.00
    (v[_GENERADA] - v[_APLICADA] for v in _M303_COMPENSACION_BY_PERIOD.values()), Decimal(0)
)
_EXPECTED_BOX_97 = Decimal("50.00")  # what the last period itself generated, none consumed
_EXPECTED_BOX_662 = Decimal("70.00")  # 40.00 of 1T's lot after the 60.00 applied, plus 30.00 of 3T's

# The un-fixed naive per-period relation split (what this test must NOT see).
_NAIVE_BOX_97 = _M303_COMPENSACION_BY_PERIOD["4T"][_GENERADA]  # copy(4T) = 50.00
_NAIVE_BOX_662 = sum(  # sum(1T-3T) = 130.00, blind to the 60.00 consumed
    (_M303_COMPENSACION_BY_PERIOD[p][_GENERADA] for p in ("1T", "2T", "3T")), Decimal(0)
)


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_PROFILE_LABEL) as profile:
        seed_ready_profile(bucket_id=_BUCKET_ID, at=_T0)
        yield profile.repository


def _seed_m303_compensacion_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Persist one M303 filing observation per quarter carrying the FIFO compensacion casillas."""
    save_local_m303_compensacion_filings(
        obs_repo,
        filing_year=_YEAR,
        casillas_by_period=_M303_COMPENSACION_BY_PERIOD,
        captured_at=_T0,
        # 2T has a positive result, which it pays after applying carried credit.
        dispositions_by_period={"2T": ResultDisposition.INGRESO},
    )


def _calculate_m390_annual(secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation):
    """Run the live M390 0A calculate over the seeded bucket (carry boxes left UNSET)."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    snapshot = published_authority_operation().snapshot("390", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="390",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot.revision.id,
        ports=WorkLifecyclePorts(work_unit_repository=wu_repo, bucket_event_repository=event_repo),
        clock=_T0,
        operation=operation,
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
    ) as _calculation_ports_257:
        return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            binding_values={},
            ports=_calculation_ports_257,
            clock=_T1,
        )


def test_m390_carry_boxes_are_the_fifo_partition_not_the_naive_split(
    secure_objects: SecureObjectRepository, *, operation: PinnedAuthorityOperation
) -> None:
    """A carried-pending chain drives box 97/662 to the FIFO partition, diverging from the naive split.

    With four M303 quarters whose credit carries forward and is partly
    consumed in 2T, the live M390 calculate must produce the FIFO partition
    (box 97 = 50.00 generated by 4T, box 662 = 70.00 rest of the year pending),
    NOT the naive per-period relation split (box 97 = copy(4T) = 50.00,
    box 662 = sum(1T-3T) = 130.00). The expected values are derived from the
    carried-pending inputs and the AEAT identity, not the registry formula.
    """
    # Guard the fixture's own divergence premise: FIFO oracle must differ from naive.
    assert _EXPECTED_BOX_662 != _NAIVE_BOX_662, "fixture must make box 662 diverge from the naive sum(1T-3T)"
    # Only the FIFO partition satisfies the AEAT identity; the naive split ignores the consumption.
    assert _EXPECTED_BOX_97 + _EXPECTED_BOX_662 == _YEAR_PENDING
    assert _NAIVE_BOX_97 + _NAIVE_BOX_662 != _YEAR_PENDING

    obs_repo = CalculationObservationRepository()
    _seed_m303_compensacion_quarters(obs_repo=obs_repo)

    result = _calculate_m390_annual(secure_objects, operation=operation)
    casilla_values = result.revision.casilla_values

    box_97 = Decimal(casilla_values[_M390_BOX_97])
    box_662 = Decimal(casilla_values[_M390_BOX_662])

    # Box 97 carries what the last period itself generated; box 662 the rest of
    # the year's pending credit, after the 2T consumption (the FIFO partition).
    assert box_97 == _EXPECTED_BOX_97, (
        f"M390 box 97 (compensacion-ultimo-periodo) must be the credit the last period generated "
        f"{_EXPECTED_BOX_97!r}; got {box_97!r}"
    )
    assert box_662 == _EXPECTED_BOX_662, (
        f"M390 box 662 (compensacion-generada-ejercicio-no-97) must be the FIFO remainder {_EXPECTED_BOX_662!r} "
        f"(40.00 of 1T's lot and 30.00 of 3T's), NOT the naive sum(1T-3T)={_NAIVE_BOX_662!r}; got {box_662!r}"
    )

    # Belt-and-braces: the result must NOT be the naive split (the un-fixed behaviour).
    assert (box_97, box_662) != (_NAIVE_BOX_97, _NAIVE_BOX_662), (
        "M390 carry boxes collapsed to the naive per-period split - the annual partition source is not firing"
    )
    # The AEAT partition identity is preserved through the full calculate.
    assert box_97 + box_662 == _YEAR_PENDING, (
        f"M390 carry partition must satisfy [97]+[662]==year pending {_YEAR_PENDING!r}; got {box_97 + box_662!r}"
    )
