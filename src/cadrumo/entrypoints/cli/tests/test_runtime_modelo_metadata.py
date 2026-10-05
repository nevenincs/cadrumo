"""Installed CLI modelo metadata actions use the canonical native worker."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.period import Period
from cadrumo.domain.modelos.repository import upsert_work_unit
from cadrumo.domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "cli-modelo-metadata-test-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _seed_unit(profile_id: str) -> WorkUnit:
    period = Period.from_year_and_code(2026, "1T")
    created = datetime(2020, 1, 1, tzinfo=UTC)
    unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=profile_id,
            modelo="130",
            filing_year=2026,
            period=period,
            revision_id="2019-y-siguientes",
        ),
        bucket_id=profile_id,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id="2019-y-siguientes",
        name="Original metadata",
        created_at=created,
        updated_at=created,
    )
    repository = WorkUnitCatalogueRepository(bucket_id=profile_id, objects=secure_object_repository_for_active_bucket())
    repository.save(upsert_work_unit(repository.load(), unit))
    return unit


def _invoke(*args: str):
    return invoke_cached_cli(
        ("--format", "json", "--profile", "Enrollment tests", "--profile-secrets-stdin", *args),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )


def test_installed_cli_rename_and_discard_use_exact_worker_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        original = _seed_unit(str(profile_id))
        create, decode = profile_authority_contexts()
        hot_profile = register_profile_with_credentials(
            label="Different hot profile",
            passphrase=PROFILE_INPUT,
            profile_create_context=create,
            profile_decode_context=decode,
        )
        assert hot_profile.profile_id != str(profile_id)
        close_active_bucket_session()

        stop, boot, native = Event(), uuid4(), MemoryNativePort()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                renamed = _invoke(
                    "app",
                    "modelo",
                    "work",
                    "rename",
                    "--modelo",
                    "130",
                    "--year",
                    "2026",
                    "--period",
                    "1T",
                    "--revision",
                    "2019-y-siguientes",
                    "--name",
                    "Renamed through worker",
                )
                assert renamed.exit_code == 0, renamed.output
                rename_result = json.loads(renamed.stdout)["result"]
                assert rename_result["work_unit_id"] == original.work_unit_id
                assert rename_result["bucket_id"] == "<bucket-id>"
                assert rename_result["name"] == "Renamed through worker"
                assert rename_result["created_at"] == original.created_at.isoformat()
                assert rename_result["updated_at"] != original.updated_at.isoformat()
                assert PROFILE_INPUT not in renamed.output

                status = _invoke("app", "modelo", "work", "status", original.work_unit_id)
                assert status.exit_code == 0, status.output
                status_result = json.loads(status.stdout)["result"]
                assert status_result["operation"] == "modelo.work.status"
                assert status_result["work_unit_id"] == original.work_unit_id
                assert status_result["name"] == "Renamed through worker"
                assert status_result["bucket_id"] == "<bucket-id>"
                assert status_result["period"] == {"filing_year": 2026, "code": "1T"}
                assert status_result["updated_at"] == rename_result["updated_at"]
                assert PROFILE_INPUT not in status.output

                foreign = _invoke(
                    "app",
                    "modelo",
                    "work",
                    "discard",
                    original.work_unit_id,
                    "--bucket-id",
                    str(uuid4()),
                    "--yes",
                )
                assert foreign.exit_code != 0
                assert PROFILE_INPUT not in foreign.output

                discarded = _invoke(
                    "app",
                    "modelo",
                    "work",
                    "discard",
                    original.work_unit_id,
                    "--reason",
                    "Duplicate work",
                    "--yes",
                )
                assert discarded.exit_code == 0, discarded.output
                discard_result = json.loads(discarded.stdout)["result"]
                assert discard_result["work_unit_id"] == original.work_unit_id
                assert discard_result["name"] == "Renamed through worker"
                assert discard_result["state"] == "descartado"
                assert discard_result["discard_reason"] == "Duplicate work"
                assert discard_result["discarded_at"] is not None
                assert PROFILE_INPUT not in discarded.output

                repeated = _invoke("app", "modelo", "work", "discard", original.work_unit_id, "--yes")
                assert repeated.exit_code != 0
                assert repeated.stdout == ""
                repeated_error = json.loads(repeated.stderr)["error"]
                assert repeated_error["context"]["operation_id"]
                assert PROFILE_INPUT not in repeated.output

                renamed_after_discard = _invoke(
                    "app", "modelo", "work", "rename", original.work_unit_id, "--name", "Must not change"
                )
                assert renamed_after_discard.exit_code != 0
                assert renamed_after_discard.stdout == ""
                assert PROFILE_INPUT not in renamed_after_discard.output

                no_target = _invoke("app", "modelo", "work", "rename", "--name", "Missing target")
                assert no_target.exit_code != 0
                assert no_target.stdout == ""
            finally:
                stop.set()
                running.result(timeout=15)
                endpoint.close()
