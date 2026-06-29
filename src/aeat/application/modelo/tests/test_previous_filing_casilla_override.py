"""Modelo 130 C15 carry-forward input contract tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaId, RegistryValidationError, validated_casilla_id
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...user_profile import UserProfileLifecycleRepository
from .. import calculate_modelo_revision, create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]

_CLOCK = datetime(2026, 10, 15, 9, 0, 0, tzinfo=UTC)
_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Diego"),
    UserProfileFact(path="identity.surnames", value="Operator"),
    UserProfileFact(path="activities.description", value="economic activity"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
    UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
)


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
_M130_DIFERENCIA_PREVIA_CASILLA: CasillaId = _casilla_id("14")
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
        UserProfileLifecycleRepository(bucket_id="default", objects=objects).save(
            UserProfileRecord(
                profile_id="default",
                display_name="Diego Operator",
                facts=_READY_PROFILE_FACTS,
                created_at=_CLOCK,
                updated_at=_CLOCK,
            ),
        )
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


def _common_inputs() -> dict[CasillaId, Decimal]:
    return {
        _M130_INCOME_CASILLA: Decimal("30000"),
        _M130_EXPENSE_CASILLA: Decimal("12000"),
        _M130_PREVIOUS_PAYMENTS_CASILLA: Decimal("0"),
        _M130_WITHHELD_CASILLA: Decimal("0"),
        _M130_AGRARIAN_VOLUME_CASILLA: Decimal("0"),
        _M130_AGRARIAN_WITHHELD_CASILLA: Decimal("0"),
        _M130_HOME_DEDUCTION_CASILLA: Decimal("0"),
        _M130_PRIOR_RETURN_RESULT_CASILLA: Decimal("0"),
    }


def test_casilla_15_manual_input_is_rejected_at_3t(repos: _Repos) -> None:
    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)

    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied as inputs"):
        calculate_modelo_revision(
            work_unit.work_unit_id,
            casilla_inputs={**_common_inputs(), _M130_CARRY_FORWARD_CASILLA: Decimal("2694")},
            binding_values={
                "irpf.previous_year_economic_activity_net_income": Decimal("0"),
                "modelo-130-resultados-negativos-anteriores": Decimal("2694"),
            },
            work_unit_repository=wu_repo,
            calculation_repository=cr_repo,
            bucket_event_repository=bv_repo,
            clock=_CLOCK,
        )


def test_casilla_15_binding_flows_into_casilla_17_when_within_cap(repos: _Repos) -> None:
    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)
    common_bindings = {
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
    }
    rev_zero = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_common_inputs(),
        binding_values=common_bindings,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )
    carry = Decimal("2694")
    rev_override = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_common_inputs(),
        binding_values={**common_bindings, "modelo-130-resultados-negativos-anteriores": carry},
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )

    c17_zero = Decimal(rev_zero.casilla_values[_M130_DIFFERENCE_CASILLA])
    c17_override = Decimal(rev_override.casilla_values[_M130_DIFFERENCE_CASILLA])

    assert Decimal(rev_override.casilla_values[_M130_CARRY_FORWARD_CASILLA]) == carry
    assert c17_override == c17_zero - carry


def test_casilla_15_binding_is_capped_at_c14(repos: _Repos) -> None:
    work_unit, wu_repo, cr_repo, bv_repo = _work_unit_3t(repos)

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=_common_inputs(),
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("20000"),
            "modelo-130-resultados-negativos-anteriores": Decimal("99999"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_CLOCK,
    )

    assert revision.casilla_values[_M130_DIFERENCIA_PREVIA_CASILLA] > Decimal("0")
    assert revision.casilla_values[_M130_CARRY_FORWARD_CASILLA] == revision.casilla_values[
        _M130_DIFERENCIA_PREVIA_CASILLA
    ]
    assert revision.casilla_values[_M130_DIFFERENCE_CASILLA] == Decimal("0.00")
