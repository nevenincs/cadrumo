"""Real CLI coverage for durable all-profile reset start, status, and resume."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.storage.bucket._layout import bucket_paths
from ....core.config import override_settings
from ....core.period import Period
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.filing_record import ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id
from ....tests.cli_runner import invoke_cached_cli
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from .._bootstrap_exempt import is_bootstrap_exempt

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_OVERRIDE_REASON = "Court order authorises deletion before the retention floor."


def _persist_retained_filing() -> None:
    work_unit_id = "a" * 64
    revision_id = "b" * 64
    record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat.cli.modelo.file",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=_PROFILE_ID,
        modelo=ModeloCode("303"),
        filing_year=2025,
        period=Period.from_year_and_code(2025, "2T"),
        filed_at=datetime(2025, 7, 1, tzinfo=UTC),
        filed_by="aeat.cli.modelo.file",
    )
    with open_test_profile_session(_PROFILE_ID):
        repository = ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID)
        catalogue = repository.load()
        repository.save(
            ModeloRecordCatalogue(
                records={**catalogue.records, record_id: record},
            ),
        )


def _invoke_json(args: list[str]):
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_config_reset_group_has_exact_sessionless_bootstrap_ownership() -> None:
    for path in (
        "config reset start",
        "config reset status",
        "config reset resume",
    ):
        assert is_bootstrap_exempt(path)
    assert is_bootstrap_exempt("config auth reset") is False


def test_config_reset_start_status_and_resume_exact_durable_journal(
    tmp_path: Path,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        with open_test_profile_session(_PROFILE_ID):
            register_minimal_profile(profile_id=_PROFILE_ID)
        _persist_retained_filing()

        empty_status = _invoke_json(["config", "reset", "status"])
        assert empty_status["result"]["operation"] is None

        started = _invoke_json(["config", "reset", "start", "--yes"])
        started_operation = started["result"]["operation"]
        operation_id = started_operation["operation_id"]
        assert started["command"] == "config.reset.start"
        assert len(operation_id) == 64
        assert started_operation["status"] == "paused"
        assert started_operation["pause_reason"] == "retention_unresolved"
        assert started_operation["paused_target_ids"] == [_PROFILE_ID]
        assert started_operation["targets"][0]["phase"] == "snapshotted"
        assert bucket_paths(root, _PROFILE_ID).bucket_dir.is_dir()

        default_status = _invoke_json(["config", "reset", "status"])
        exact_status = _invoke_json(
            [
                "config",
                "reset",
                "status",
                "--operation-id",
                operation_id,
            ],
        )
        assert default_status["result"] == exact_status["result"]
        assert exact_status["command"] == "config.reset.status"

        missing_reason = invoke_cached_cli(
            [
                "config",
                "reset",
                "resume",
                "--yes",
                "--override-retention",
            ],
        )
        assert missing_reason.exit_code != 0
        assert "--reason" in missing_reason.output

        resumed = _invoke_json(
            [
                "config",
                "reset",
                "resume",
                "--yes",
                "--override-retention",
                "--reason",
                _OVERRIDE_REASON,
            ],
        )
        resumed_operation = resumed["result"]["operation"]
        assert resumed["command"] == "config.reset.resume"
        assert resumed_operation["operation_id"] == operation_id
        assert resumed_operation["status"] == "complete"
        summary = resumed_operation["summary"]
        assert isinstance(summary, dict)
        assert summary["target_count"] == 1
        assert summary["deleted_count"] == 1
        assert summary["already_absent_count"] == 0
        assert summary["retention_override_count"] == 1
        assert summary["completed_at"]
        assert bucket_paths(root, _PROFILE_ID).bucket_dir.exists() is False

        no_incomplete = invoke_cached_cli(
            ["config", "reset", "resume", "--yes"],
        )
        assert no_incomplete.exit_code != 0
        assert "no incomplete" in no_incomplete.output.lower()
