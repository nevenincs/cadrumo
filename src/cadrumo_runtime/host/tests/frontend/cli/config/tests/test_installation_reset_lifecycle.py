"""The reset commands drive one durable journal through the running runtime: start, pause on retention, resume."""

from __future__ import annotations

import json
import sys
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.bucket.directory_layout import bucket_paths
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.filing.retention import try_record_filing_retention_snapshot
from cadrumo.core.config import override_settings
from cadrumo.core.period import Period
from cadrumo.domain.modelos.codes import ModeloCode
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordCatalogue,
    derive_filing_record_id,
)
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.host.installation_reset import register_reset_acts
from cadrumo_runtime.host.tests.frontend.cli.cli_runner import invoke_cached_cli
from cadrumo_runtime.host.tests.installation_registered_runtime import serving_registered_runtime
from cadrumo_runtime.host.tests.installation_runtime import InstallationLogin

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

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
        origin=FilingOrigin.LOCAL,
        confirmation=AeatConfirmationState.PENDIENTE,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
    )
    with open_test_profile_session(_PROFILE_ID):
        repository = ModeloRecordCatalogueRepository(bucket_id=_PROFILE_ID)
        catalogue = repository.load()
        saved = ModeloRecordCatalogue(records={**catalogue.records, record_id: record})
        repository.save(saved)
        # Production refreshes the retention snapshot at the moment a filing is
        # persisted (`modelo.revision_persistence`), because the deletion
        # preflight cannot read a bucket it has not unlocked and reads this
        # plaintext record instead. Writing the catalogue directly skips that
        # producer, leaving a profile whose filing exists but whose snapshot
        # still says "no filings" -- a state production never reaches, and one
        # in which the preflight sees nothing to retain and the reset runs
        # straight to completion.
        try_record_filing_retention_snapshot(
            bucket_id=_PROFILE_ID,
            records=tuple(saved.records.values()),
            observed_at=datetime(2025, 7, 1, tzinfo=UTC),
        )


def _invoke_json(args: list[str]):
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@contextmanager
def _serving_resets(root: Path) -> Generator[None]:
    """Serve the reset acts over ``root`` as the installed cohort, so the commands find the runtime."""
    with serving_registered_runtime(
        WindowsEndpoint(storage_root=root),
        root,
        InstallationLogin(owner=owner_id()),
        register_reset_acts,
        product_version=version("cadrumo"),
    ):
        yield


def test_the_reset_commands_start_pause_and_resume_one_durable_journal_through_the_running_runtime(
    tmp_path: Path,
) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root, _serving_resets(root):
        with open_test_profile_session(_PROFILE_ID):
            # `config reset` runs the custody-transaction deletion preflight,
            # which joins the legal and filing hold owners. An ABSENT legal-hold
            # snapshot fails closed by design -- it means nobody was asked, not
            # that no case is open -- so a profile seeded without one refuses
            # here for a reason that is not this test's subject. This is the
            # opt-in the seeding door documents for exactly that case.
            register_minimal_profile(profile_id=_PROFILE_ID, record_empty_legal_hold=True)
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
