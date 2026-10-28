"""Retiring a profile's last lease fences its key under the custody lock and closes its store after.

A profile is unlocked in worker custody, its secure SQL store is filled with a
realistic volume of encrypted records through the real repository, and its only
lease is retired through the real path. Closing the store's last connection
checkpoints its WAL and waits on the disk. While each connection closes, the
key is already zeroised and unbound and another thread can take the custody
lock. Each release step reports how long it took, and storage refuses once
retirement answers.
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import override
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry

from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    ProfileAccessBinding,
    SessionKind,
    SessionState,
)
from cadrumo.core.classification.policies import SensitivityClass
from cadrumo.core.config import override_settings
from cadrumo.core.logging import flush_logging
from cadrumo.core.secure_object_write import SecureObjectWrite
from cadrumo.core.time.clock import now
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity

from ...custody.capsule import load_committed_profile_password_material
from ...errors import StorageValidationError
from ...profile_persistence_composition import composed_profile_persistence_ports
from ...runtime_repository import secure_object_repository_for_active_bucket
from ...secure_object_namespaces import LLM_CACHE_NAMESPACE
from ...tests.profile_capsule_runtime import derive_test_bucket_key, publish_test_profile_capsule
from ...tests.secure_sql import isolated_profile_storage_root
from ..active_session import current_active_bucket_session
from ..bucket_session import KEY_RELEASE_PHASE_EVENT, BucketSession
from ..profile_worker_custody import ProfileWorkerCustody

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_MODULE = "cadrumo.adapters.persistence.storage.master_key.tests.test_profile_worker_custody_release_timing"
_BATCHES = 40
_BATCH_SIZE = 100
_PAYLOAD_BYTES = 1536
_WRITTEN_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


class _PhaseRecords(logging.Handler):
    """Keep every release-phase record this process emits."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self._records: dict[int, logging.LogRecord] = {}

    @override
    def emit(self, record: logging.LogRecord) -> None:
        # The first record a process emits can reach a root handler twice as the same object.
        if record.getMessage() == KEY_RELEASE_PHASE_EVENT:
            self._records[id(record)] = record

    def phases(self) -> list[dict[str, object]]:
        return [
            {
                name: record.__dict__.get(name)
                for name in ("phase", "elapsed_seconds", "item_count", "checked_out_count", "wal_bytes")
            }
            for record in sorted(self._records.values(), key=lambda record: record.created)
        ]


def _lease(identity: ProfileWorkerIdentity) -> AccessSession:
    issued = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.HUMAN,
        originating_login_id="synthetic-os-login",
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        grant_id=None,
        grant_generation=None,
        key_id=None,
        key_generation=None,
        issued_at=issued,
        issued_monotonic=0.0,
        expires_at=issued + timedelta(minutes=15),
    )


def _fill_store() -> None:
    repository = secure_object_repository_for_active_bucket()
    filler = bytes(range(256)) * (_PAYLOAD_BYTES // 256)
    for batch in range(_BATCHES):
        repository.save_many(
            tuple(
                SecureObjectWrite(
                    namespace=LLM_CACHE_NAMESPACE.namespace,
                    object_key=f"release-timing|provider|model|{batch:064x}|{index:064x}",
                    classification=SensitivityClass.DIAGNOSTIC,
                    schema_version=LLM_CACHE_NAMESPACE.schema_version,
                    written_at=_WRITTEN_AT,
                    payload=filler,
                )
                for index in range(_BATCH_SIZE)
            )
        )
    assert len(repository.list_keys(LLM_CACHE_NAMESPACE.namespace)) == _BATCHES * _BATCH_SIZE


def _observe_connection_closes(custody: ProfileWorkerCustody, session: BucketSession) -> list[dict[str, bool]]:
    """Record, as each pooled connection of the store closes, whether the key is fenced and custody is free."""
    observed: list[dict[str, bool]] = []

    def closing(_connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
        answered: list[float | None] = []
        # Another custody request, on another thread, must not wait for this close.
        probe = Thread(target=lambda: answered.append(custody.seconds_until_expiry()), name="custody-probe")
        probe.start()
        probe.join(timeout=10)
        observed.append(
            {
                "key_sealed": session.sealed,
                "key_unbound": current_active_bucket_session() is None,
                "custody_answered": answered == [None],
            }
        )

    event.listen(secure_object_repository_for_active_bucket().engine, "close", closing)
    return observed


def _exercise(tmp_path: Path) -> None:
    # A spawned interpreter has none of the ports the test session composes.
    with composed_profile_persistence_ports(), isolated_profile_storage_root(tmp_path=tmp_path) as root:
        root.mkdir(parents=True, exist_ok=True)
        profile_id = uuid4()
        publish_test_profile_capsule(profile_id, label="Release timing subject", root=root)
        envelope = load_committed_profile_password_material(profile_id, root=root).envelope
        identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=profile_id,
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=envelope.password_generation,
                dek_epoch=UUID(bytes=base64.b64decode(envelope.dek_epoch)),
            ),
        )
        with override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(profile_id)):
            custody = ProfileWorkerCustody(identity, storage_root=root, monotonic=lambda: 0.0)
            try:
                admitted = _lease(identity)
                custody.install(admitted, bytearray(derive_test_bucket_key(str(profile_id), purpose="dek")))
                _fill_store()
                session = current_active_bucket_session()
                assert session is not None
                closes = _observe_connection_closes(custody, session)

                recorder = _PhaseRecords()
                logging.getLogger().addHandler(recorder)
                previous_level = logging.getLogger().level
                logging.getLogger().setLevel(logging.DEBUG)
                try:
                    assert custody.retire(admitted.session_id) == frozenset({admitted.session_id})
                    # Records reach handlers from a dispatch thread.
                    assert flush_logging(timeout=5)
                finally:
                    logging.getLogger().removeHandler(recorder)
                    logging.getLogger().setLevel(previous_level)

                assert session.sealed and current_active_bucket_session() is None
                try:
                    secure_object_repository_for_active_bucket()
                except StorageValidationError:
                    pass
                else:
                    raise AssertionError("storage stayed ready after its only lease was retired")
                sys.stdout.write(json.dumps({"phases": recorder.phases(), "closes": closes}) + "\n")
            finally:
                custody.close()


def test_retiring_the_last_lease_closes_the_store_after_the_key_is_fenced_and_custody_is_free(tmp_path: Path) -> None:
    """A fresh child keeps the process-wide worker pin to this case."""
    result = run_audited_process(
        [sys.executable, "-m", _MODULE, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout.strip().splitlines()[-1])
    closes = observed["closes"]
    assert closes
    assert all(close == {"key_sealed": True, "key_unbound": True, "custody_answered": True} for close in closes)
    phases = observed["phases"]
    names = [phase["phase"] for phase in phases]
    assert names.index("record_authority_zeroise") < names.index("dek_zeroise") < names.index("bucket_session_seal")
    assert names.index("bucket_session_seal") < names.index("engine_pool_dispose") < names.index("engine_dispose")
    for phase in phases:
        assert isinstance(phase["elapsed_seconds"], float)
    (dispose,) = (phase for phase in phases if phase["phase"] == "engine_pool_dispose")
    assert dispose["item_count"] == len(closes)
    assert dispose["checked_out_count"] == 0
    assert isinstance(dispose["wal_bytes"], int) and dispose["wal_bytes"] > 0


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]))
