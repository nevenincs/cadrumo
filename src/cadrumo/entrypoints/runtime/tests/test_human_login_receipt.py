"""Exact worker human-login acknowledgements and receipt publication after session publication."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, worker_profiles
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    AccessSession,
    SessionKind,
    SessionState,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyError
from cadrumo.application.user_profile.login_session import ProfileLoginOutcome, borrow_profile_receipt_key
from cadrumo.core.config import override_settings
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.runtime.profile_login import ProfileWorkerHumanLogin
from cadrumo.tests.audited_process import run_audited_process

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires Windows profile custody"),
    pytest.mark.usefixtures("authority_operation"),
]


class _KeyringError(Exception):
    """Explicit unavailable native credential facility."""


class _Keyring:
    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.entries: dict[tuple[str, str], str] = {}
        self.writes = 0

    def get_password(self, service_name: str, username: str) -> str | None:
        if not self.available:
            raise _KeyringError("unavailable")
        return self.entries.get((service_name, username))

    def set_password(self, service_name: str, username: str, password: str) -> None:
        if not self.available:
            raise _KeyringError("unavailable")
        self.writes += 1
        self.entries[(service_name, username)] = password

    def delete_password(self, service_name: str, username: str) -> None:
        self.entries.pop((service_name, username), None)


def _human_lease(identity: ProfileWorkerIdentity, outcome: ProfileLoginOutcome) -> AccessSession:
    instant = now()
    return AccessSession(
        session_id=uuid4(),
        binding=identity.binding,
        runtime_boot_id=identity.runtime_boot_id,
        profile_lock_generation=0,
        connection_id=uuid4(),
        client_id=uuid4(),
        kind=SessionKind.HUMAN,
        state=SessionState.ACTIVE,
        scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(AccessAction),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        originating_login_id="synthetic-current-os-login",
        issued_at=instant,
        issued_monotonic=time.monotonic(),
        expires_at=min(outcome.idle_deadline, outcome.absolute_deadline),
    )


def _exercise(tmp_path: Path, mode: str) -> None:
    # Keep the explicit keyring port installed through storage-root teardown,
    # which reaps any receipt minted by this child process.
    with pytest.MonkeyPatch.context() as patcher, profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, _), _) = profiles
        with override_settings(cadrumo_local_storage_root=root):
            store = _Keyring(available=mode != "unavailable")
            patcher.setattr(receipt, "_keyring", lambda: (store, _KeyringError, _KeyringError))
            custody = ProfileWorkerCustody(identity, storage_root=root)
            human = ProfileWorkerHumanLogin(custody, decode=lambda: profile_authority_contexts()[1])
            path = receipt.profile_session_path(storage_root=root, profile_id=identity.binding.profile_id)
            proof = bytearray(PROFILE_INPUT.encode())
            try:
                candidate_id, outcome = human.authenticate(proof)
                assert not outcome.session_persisted and not path.exists()
                lease = _human_lease(identity, outcome)
                sign_in = SignInGenerationCustody(root=root, binding=identity.binding)
                bound, pending = human.bind(candidate_id, lease, persist_receipt=mode != "default")
                # Binding precedes publication, so it never mints.
                assert pending == (mode != "default")
                assert not bound.session_persisted and not path.exists() and store.writes == 0
                assert custody.require(lease.session_id) == lease
                if mode == "default":
                    return
                if mode == "retired_before_mint":
                    # The runtime refused or retired the session before minting.
                    human.discard(lease.session_id)
                    custody.retire(lease.session_id)
                    with pytest.raises(AutomationCustodyError):
                        human.mint_receipt(lease.session_id, sign_in.establish().current)
                    assert not path.exists() and store.writes == 0
                    return
                if mode == "lease_gone":
                    custody.retire(lease.session_id)
                    gone = human.mint_receipt(lease.session_id, sign_in.establish().current)
                    assert not gone.session_persisted and not path.exists() and store.writes == 0
                    return
                captured = sign_in.establish().current
                if mode == "advanced_before_mint":
                    sign_in.advance()
                    stale = human.mint_receipt(lease.session_id, captured)
                    assert not stale.session_persisted and not path.exists() and store.writes == 0
                    with pytest.raises(AutomationCustodyError):
                        human.mint_receipt(lease.session_id, captured)
                    return
                if mode == "publication_failure":
                    # A malformed exact receipt leaf causes a storage publication
                    # error at the mint, independently of keyring availability.
                    path.mkdir(parents=True)
                    try:
                        with pytest.raises(ProfileCustodyRecordError):
                            human.mint_receipt(lease.session_id, captured)
                        with pytest.raises(AutomationCustodyError):
                            human.mint_receipt(lease.session_id, captured)
                    finally:
                        path.rmdir()
                    return
                acknowledged = human.mint_receipt(lease.session_id, captured)
                assert acknowledged.authenticated_at == outcome.authenticated_at
                assert acknowledged.idle_deadline == outcome.idle_deadline
                assert acknowledged.absolute_deadline == outcome.absolute_deadline
                assert not acknowledged.resumed
                assert acknowledged.session_persisted == (mode == "success")
                assert custody.require(lease.session_id) == lease
                if mode == "unavailable":
                    assert not path.exists() and store.writes == 0
                    return
                check = receipt.verify_profile_session_binding(
                    sign_in=sign_in, login_id=lease.originating_login_id or ""
                )
                assert check.verdict is receipt.ReceiptBindingVerdict.BOUND
                assert check.record is not None and check.record.sign_in == captured
                assert path.is_file() and store.writes == 1
                original = path.read_bytes()
                with borrow_profile_receipt_key(bucket_id=identity.binding.profile_id) as receipt_key:
                    resumed_id, resumed_outcome = human.resume(receipt_key)
                successor = _human_lease(identity, resumed_outcome)
                resumed_ack, resumed_pending = human.bind(resumed_id, successor, persist_receipt=True)
                assert not resumed_pending
                assert resumed_ack.resumed and resumed_ack.session_persisted
                assert resumed_ack.authenticated_at == acknowledged.authenticated_at
                assert resumed_ack.idle_deadline == acknowledged.idle_deadline
                assert resumed_ack.absolute_deadline == acknowledged.absolute_deadline
                assert custody.require(successor.session_id) == successor
                assert path.read_bytes() == original and store.writes == 1
            finally:
                proof[:] = bytes(len(proof))
                human.close()
                custody.close()


@pytest.mark.parametrize(
    "mode",
    [
        "success",
        "default",
        "unavailable",
        "publication_failure",
        "retired_before_mint",
        "lease_gone",
        "advanced_before_mint",
    ],
)
def test_worker_human_login_receipt_lifecycle(tmp_path: Path, mode: str) -> None:
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.test_human_login_receipt", str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]), sys.argv[2])
