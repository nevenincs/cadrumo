"""Locale regression coverage for malformed modelo work KEY=VALUE inputs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.workflow.persistence import workflow_state_repository
from ....core import Period
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
_WORK_UNIT_CREATED_AT = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)

_isolated_backend = active_profile_isolated_backend_fixture(bucket_id=_PROFILE_ID, dispose_engine_around=True)


def _seed_work_unit() -> str:
    state = workflow_state_repository().load()
    bucket_id = state.active_profile_bucket_id()
    assert bucket_id is not None
    revision_id = "r" + "1" * 63
    period = Period.from_year_and_code(2026, "1T")
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=_WORK_UNIT_CREATED_AT,
        updated_at=_WORK_UNIT_CREATED_AT,
    )
    repo = WorkUnitCatalogueRepository()
    repo.save(upsert_work_unit(repo.load(), work_unit))
    return work_unit_id


def test_malformed_binding_kv_spec_uses_requested_output_language() -> None:
    """Malformed ``--binding`` input reaches the operator as localized prose."""

    work_unit_id = _seed_work_unit()
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "calculate",
            work_unit_id,
            "--binding",
            "missing-equals",
            "--output-language",
            "hu",
        ],
    )

    assert result.exit_code != 0, result.output
    collapsed = " ".join(result.output.split())
    assert "--binding" in collapsed
    assert "missing-equals" in collapsed
    assert "kulcs-érték bejegyzés" in collapsed
    assert "A kulcs a bal oldalon" in collapsed
    assert "--binding must be KEY=VALUE" not in collapsed
