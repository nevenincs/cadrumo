"""Locale regression coverage for malformed modelo work KEY=VALUE inputs."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core import Period
from ....domain.modelos import (
    ModeloCode,
    WorkUnit,
    derive_work_unit_id,
    upsert_work_unit,
)
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "22222222-2222-4222-8222-222222222222"
_WORK_UNIT_CREATED_AT = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)


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
