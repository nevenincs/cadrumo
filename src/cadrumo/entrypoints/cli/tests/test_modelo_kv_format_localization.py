"""Locale regression coverage for malformed modelo work KEY=VALUE inputs."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.workflow.persistence import workflow_state_repository
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.repository import upsert_work_unit
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ._modelo_work_ux_support import operator_profile_facts
from ._runtime_profile_cli_fixture import native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_PROFILE_LABEL = "Malformed binding locale profile"
_WORK_UNIT_CREATED_AT = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)


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


def test_malformed_binding_kv_spec_uses_requested_output_language(tmp_path: Path) -> None:
    """Malformed ``--binding`` input reaches the operator as localized prose."""

    with native_cli_profile_scope(tmp_path) as profile:
        profile.register(label=_PROFILE_LABEL, facts=operator_profile_facts())
        work_unit_id = _seed_work_unit()
        close_active_bucket_session()
        result = invoke_cached_cli(
            [
                "--profile",
                _PROFILE_LABEL,
                "--profile-secrets-stdin",
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
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )

    assert result.exit_code != 0, result.output
    collapsed = " ".join(result.output.split())
    assert "--binding" in collapsed
    assert "missing-equals" in collapsed
    assert "kulcs-érték bejegyzés" in collapsed
    assert "A kulcs a bal oldalon" in collapsed
    assert "--binding must be KEY=VALUE" not in collapsed
    assert "runtime_unavailable" not in collapsed
