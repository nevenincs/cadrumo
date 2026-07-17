"""Result-summary labels follow the active output language."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.modelo import calculation_result_summary
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core import Period
from ....core.config import override_settings
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    ModeloCode,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._modelo_rendering import result_summary_lines, result_summary_payload

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "33333333-3333-4333-8333-333333333333"
_NOW = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")
_REVISION_ID = "2019-y-siguientes"


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        try:
            workflow_state_repository().update(
                lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID),
            )
            yield
        finally:
            dispose_engine()


def _seed_m130_work_unit() -> WorkUnit:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        name="130-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
    )
    repository = WorkUnitCatalogueRepository()
    repository.save(upsert_work_unit(repository.load(), work_unit))
    return work_unit


def _m130_revision(work_unit: WorkUnit) -> CalculationRevision:
    casilla_values = {"03": Decimal("123.45")}
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values=casilla_values,
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        casilla_values=casilla_values,
        observations=registry_grounded_observations(
            modelo=str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=casilla_values,
        ),
        created_at=_NOW,
        updated_at=_NOW,
    )


def test_result_summary_rows_render_requested_localized_label() -> None:
    """Modelo result summaries keep official labels while rendering localized display labels."""

    work_unit = _seed_m130_work_unit()
    revision = _m130_revision(work_unit)

    summary = calculation_result_summary(revision)
    assert summary is not None
    row = next(item for item in summary.rows if item.casilla_id == "03")
    assert row.label == "Rendimiento neto"
    assert row.localized_labels["ca"] == "Rendiment net"

    with override_settings(cadrumo_output_language="ca"):
        lines = result_summary_lines(revision)
        payload = result_summary_payload(revision)

    rendered = "\n".join(lines)
    assert "key_figure\t03\t123.45\tRendiment net" in rendered
    assert "Rendimiento neto" not in rendered

    payload_row = next(item for item in payload if item.casilla_id == "03")
    assert payload_row.label == "Rendiment net"
    assert payload_row.localized_labels["ca"] == "Rendiment net"
    assert payload_row.localized_labels["en"] == "Net yield"
