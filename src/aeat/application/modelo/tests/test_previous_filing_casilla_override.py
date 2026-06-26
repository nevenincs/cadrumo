"""Oracle tests: --casilla override for previous_filing-bound casillas (Diego #218).

M130 casilla 15 (Resultados negativos de trimestres anteriores) is bound via
``source = "previous_filing"``.  Before this fix the operator-supplied
``--casilla "15=2694"`` was silently zeroed (or raised a cryptic
RegistryValidationError after consistency hardening) because no upstream resolver
populated the matching ``binding_values["modelo-130-resultados-negativos-anteriores"]``
entry when working from a fresh bucket without local prior-quarter filings.

Fix path A: ``_lift_previous_filing_casilla_overrides_to_bindings`` promotes the
operator casilla value into the binding map so the engine's twin invariants are
satisfied (smuggle-rejection guard and consistency check both pass).

Oracle: 3T scenario, cumulative carry-forward override of €2,694.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, validated_casilla_id
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from .. import calculate_modelo_revision, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]

_CLOCK = datetime(2026, 10, 15, 9, 0, 0, tzinfo=UTC)


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_M130_INCOME_CASILLA: CasillaId = _casilla_id("01")
_M130_EXPENSE_CASILLA: CasillaId = _casilla_id("02")
_M130_PREVIOUS_PAYMENTS_CASILLA: CasillaId = _casilla_id("05")
_M130_WITHHELD_CASILLA: CasillaId = _casilla_id("06")
_M130_AGRARIAN_VOLUME_CASILLA: CasillaId = _casilla_id("08")
_M130_AGRARIAN_WITHHELD_CASILLA: CasillaId = _casilla_id("10")
_M130_CARRY_FORWARD_CASILLA: CasillaId = _casilla_id("15")
_M130_HOME_DEDUCTION_CASILLA: CasillaId = _casilla_id("16")
_M130_DIFFERENCE_CASILLA: CasillaId = _casilla_id("17")
_M130_PRIOR_RETURN_RESULT_CASILLA: CasillaId = _casilla_id("18")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over an isolated profile — no mocks."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, bv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _work_unit_3t(repos: _Repos):
    wu_repo, cr_repo, bv_repo = repos
    return (
        create_work_unit(
            bucket_id="default",
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "3T"),
            revision_id="2019-y-siguientes",
            repository=wu_repo,
            clock=_CLOCK,
        ),
        wu_repo,
        cr_repo,
        bv_repo,
    )


# ---------------------------------------------------------------------------
# Oracle scenario — Diego #218 (3T override accepted)
# ---------------------------------------------------------------------------


def test_casilla_15_override_accepted_at_3t(repos: _Repos) -> None:
    """``--casilla "15=2694"`` at 3T is accepted when no prior-quarter binding is available.

    When the operator manually declares the cumulative carry-forward (casilla 15)
    via ``--casilla`` without feeding prior-quarter filings into the local store,
    the application layer MUST accept the value and propagate it through the
    calculation.  Casilla 15 in the result must equal the supplied override.

    Oracle authority: the override is supplied as an exact decimal; casilla 15 is
    an ``op=copy`` binding whose only source is the prior quarter's
    ``saldo-negativo-fin-periodo``.  When the operator asserts the cumulative amount
    directly, the engine must honour it verbatim (no re-derivation).
    """
    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)
    override = Decimal("2694")

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            _M130_INCOME_CASILLA: Decimal("30000"),
            _M130_EXPENSE_CASILLA: Decimal("12000"),
            _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
            _M130_WITHHELD_CASILLA: Decimal("0"),
            _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
            _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
            _M130_CARRY_FORWARD_CASILLA: override,
            _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
            _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
        },
        # Previous year M100 binding required for casilla-13 minoración
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            # modelo-130-resultados-negativos-anteriores deliberately NOT supplied —
            # the fix under test must promote _M130_CARRY_FORWARD_CASILLA into this slot.
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )

    casilla_15_value = Decimal(revision.casilla_values[_M130_CARRY_FORWARD_CASILLA])
    assert casilla_15_value == override, (
        f"Casilla 15 must equal the supplied override {override}; got {casilla_15_value}"
    )


def test_casilla_15_override_flows_into_casilla_17(repos: _Repos) -> None:
    """Casilla 17 (diferencia) reflects the casilla-15 override at 3T.

    Formula: casilla 17 = casilla 14 - casilla 15 - casilla 16.
    When casilla 15 = 2694 the diferencia must be strictly less than
    when casilla 15 = 0, by exactly 2694.  This is the anti-tautology
    probe: changing the override changes the downstream result proportionally.

    The expected delta derives from the registry formula, not from
    re-implementing it — it is the override amount itself.
    """
    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)

    common_inputs = {
        _M130_INCOME_CASILLA: Decimal("30000"),
        _M130_EXPENSE_CASILLA: Decimal("12000"),
        _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
        _M130_WITHHELD_CASILLA: Decimal("0"),
        _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
        _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
        _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
        _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
    }
    common_bindings = {"irpf.previous_year_economic_activity_net_income": Decimal("0")}

    # Baseline: casilla 15 = 0
    rev_zero = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**common_inputs, _M130_CARRY_FORWARD_CASILLA: Decimal("0")},
        binding_values=common_bindings,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )

    # Override: casilla 15 = 2694  (same work unit; a new DRAFT revision)
    override = Decimal("2694")
    rev_override = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={**common_inputs, _M130_CARRY_FORWARD_CASILLA: override},
        binding_values=common_bindings,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )

    c17_zero = Decimal(rev_zero.casilla_values[_M130_DIFFERENCE_CASILLA])
    c17_override = Decimal(rev_override.casilla_values[_M130_DIFFERENCE_CASILLA])

    # The formula for casilla 17 subtracts casilla 15 from casilla 14.
    # Increasing casilla 15 by ``override`` must reduce casilla 17 by the same
    # amount (when casilla 17 remains non-negative, which it does given the
    # chosen inputs: 30000 income x 20% = 6000 gross pago, casilla 14 = 6000,
    # casilla 14 - 2694 = 3306 > 0).
    assert c17_override == c17_zero - override, (
        f"Expected casilla 17 to decrease by {override} when casilla 15 is set to "
        f"{override}: c17_zero={c17_zero}, c17_override={c17_override}"
    )


def test_casilla_15_binding_already_supplied_is_not_overwritten(repos: _Repos) -> None:
    """When ``--binding modelo-130-resultados-negativos-anteriores=X`` is explicitly
    supplied the lift helper must NOT overwrite it with the casilla-15 override.

    The engine's consistency check will then reject if they diverge — the operator
    committed to a specific binding value and passing a conflicting casilla override
    is a mistake that should surface as an error, not be silently reconciled.
    """
    from ....domain.calculations.registry import RegistryValidationError

    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)

    with pytest.raises(RegistryValidationError, match="inconsistent"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={
                _M130_INCOME_CASILLA: Decimal("30000"),
                _M130_EXPENSE_CASILLA: Decimal("12000"),
                _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
                _M130_WITHHELD_CASILLA: Decimal("0"),
                _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
                _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
                _M130_CARRY_FORWARD_CASILLA: Decimal("2694"),
                _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
                _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
            },
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("0"),
                # Explicit binding diverges from casilla override — engine must reject.
                "modelo-130-resultados-negativos-anteriores": Decimal("999"),
            },
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_CLOCK,
        )
