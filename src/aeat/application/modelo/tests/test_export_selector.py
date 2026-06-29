"""Modelo export revision-selector tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.modelos._calculation_repository import (
    CalculationRevisionCatalogueRepository,
    upsert_calculation_revision,
)
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....tests.registry_observations import registry_grounded_observations
from .. import create_work_unit
from .._selectors import ModeloCalculationRevisionSelectorStateError, select_exportable_revision
from ._export_test_support import _M130_INPUT_CASILLA, _seed_profile, isolated_backend_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_backend_context(tmp_path):
        yield


def test_exportable_selector_refuses_verified_fallback_when_current_draft_conflicts(
    isolated_backend: None,
) -> None:
    bucket_id = _seed_profile()
    work_repo = WorkUnitCatalogueRepository()
    calc_repo = CalculationRevisionCatalogueRepository()
    work_unit = create_work_unit(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2019-y-siguientes",
        repository=work_repo,
        clock=datetime(2026, 6, 4, 10, 0, tzinfo=UTC),
    )
    verified_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_M130_INPUT_CASILLA: "10"},
        binding_overrides={},
        casilla_values={_M130_INPUT_CASILLA: Decimal("10")},
    )
    draft_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={_M130_INPUT_CASILLA: "20"},
        binding_overrides={},
        casilla_values={_M130_INPUT_CASILLA: Decimal("20")},
    )
    verified = CalculationRevision(
        calculation_revision_id=verified_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_M130_INPUT_CASILLA: "10"},
        casilla_values={_M130_INPUT_CASILLA: Decimal("10")},
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={_M130_INPUT_CASILLA: Decimal("10")},
        ),
        created_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        updated_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        verified_at=datetime(2026, 6, 4, 10, 1, tzinfo=UTC),
        verified_by="operator",
    )
    draft = CalculationRevision(
        calculation_revision_id=draft_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={_M130_INPUT_CASILLA: "20"},
        casilla_values={_M130_INPUT_CASILLA: Decimal("20")},
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={_M130_INPUT_CASILLA: Decimal("20")},
        ),
        created_at=datetime(2026, 6, 4, 10, 2, tzinfo=UTC),
        updated_at=datetime(2026, 6, 4, 10, 2, tzinfo=UTC),
    )
    catalogue = upsert_calculation_revision(calc_repo.load(), verified)
    calc_repo.save(upsert_calculation_revision(catalogue, draft))
    work_unit = work_unit.model_copy(update={"current_calculation_revision_id": draft.calculation_revision_id})
    work_repo.save(upsert_work_unit(work_repo.load(), work_unit))

    with pytest.raises(ModeloCalculationRevisionSelectorStateError, match="still draft"):
        select_exportable_revision(work_unit, calculation_repository=calc_repo)
