"""Exact worker human-login acknowledgements and receipt publication after session publication."""

from __future__ import annotations

import secrets
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.bucket import keystore_paths
from cadrumo.adapters.persistence.storage.custody import acceleration_keychain, filesystem_primitives
from cadrumo.adapters.persistence.storage.custody import acceleration_receipt as receipt
from cadrumo.adapters.persistence.storage.custody.errors import ProfileCustodyRecordError
from cadrumo.adapters.persistence.storage.custody.filesystem_primitives import windows_component_paths
from cadrumo.adapters.persistence.storage.custody.sign_in_generation import SignInGenerationCustody
from cadrumo.adapters.persistence.storage.custody.tests import receipt_binding_probe as binding_probe
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from cadrumo.application.user_profile.access_contracts import AccessSession, SessionKind, SessionState
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.config import override_settings
from cadrumo.core.profile_session import ProfileHumanLoginReceipt
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.tests.audited_process import run_audited_process
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginOutcome, ProfileLoginThrottledError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.receipt_proof import borrow_receipt_proof

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, worker_profiles
from .. import profile_login
from ..profile_login import ProfileWorkerHumanLogin

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


@dataclass(frozen=True)
class _Login:
    identity: ProfileWorkerIdentity
    root: Path
    store: _Keyring
    custody: ProfileWorkerCustody
    human: ProfileWorkerHumanLogin
    path: Path
    proof: bytearray


@dataclass(frozen=True)
class _Bound:
    outcome: ProfileLoginOutcome
    lease: AccessSession
    sign_in: SignInGenerationCustody


@dataclass(frozen=True)
class _Minted:
    acknowledged: ProfileHumanLoginReceipt
    record_session_id: UUID


def _refuse_throttled(login: _Login, patcher: pytest.MonkeyPatch) -> None:
    def refuse(**_kwargs: object) -> NoReturn:
        raise ProfileLoginThrottledError(remaining_seconds=23)

    patcher.setattr(profile_login, "authenticate_profile_candidate", refuse)
    with pytest.raises(ProfileAccessRefusedError) as refused:
        login.human.authenticate(login.proof)
    assert refused.value.sign_in is not None
    assert refused.value.sign_in.reason == "throttled"
    assert refused.value.sign_in.remaining_seconds == 23
    assert not login.custody.live_sessions() and not login.path.exists() and login.store.writes == 0


def _authenticate_and_bind(login: _Login, mode: str) -> _Bound:
    human, custody, path, store = login.human, login.custody, login.path, login.store
    assert human.seconds_until_expiry() is None
    candidate_id, outcome = human.authenticate(login.proof)
    assert not outcome.session_persisted and not path.exists()
    # An unbound candidate is abandoned within five minutes; idle expiry waits for exactly that.
    waiting = human.seconds_until_expiry()
    assert waiting is not None and 0 < waiting <= 300
    lease = _human_lease(login.identity, outcome)
    sign_in = SignInGenerationCustody(root=login.root, binding=login.identity.binding)
    bound, pending = human.bind(candidate_id, lease, persist_receipt=mode != "default")
    # Binding precedes publication, so it never mints.
    assert pending == (mode != "default")
    assert not bound.session_persisted and not path.exists() and store.writes == 0
    assert custody.require(lease.session_id) == lease
    return _Bound(outcome, lease, sign_in)


def _retired_before_mint(login: _Login, bound: _Bound) -> None:
    lease = bound.lease
    # The runtime refused or retired the session before minting.
    login.human.discard(lease.session_id)
    login.custody.retire(lease.session_id)
    with pytest.raises(AutomationCustodyError):
        login.human.mint_receipt(lease.session_id, bound.sign_in.establish().current)
    assert not login.path.exists() and login.store.writes == 0


def _lease_gone(login: _Login, bound: _Bound) -> None:
    login.custody.retire(bound.lease.session_id)
    gone = login.human.mint_receipt(bound.lease.session_id, bound.sign_in.establish().current)
    assert not gone.session_persisted and not login.path.exists() and login.store.writes == 0


def _advanced_before_mint(login: _Login, bound: _Bound) -> None:
    captured = bound.sign_in.establish().current
    bound.sign_in.advance()
    stale = login.human.mint_receipt(bound.lease.session_id, captured)
    assert not stale.session_persisted and not login.path.exists() and login.store.writes == 0
    with pytest.raises(AutomationCustodyError):
        login.human.mint_receipt(bound.lease.session_id, captured)


def _publication_failure(login: _Login, bound: _Bound) -> None:
    captured = bound.sign_in.establish().current
    # A malformed exact receipt leaf causes a storage publication
    # error at the mint, independently of keyring availability.
    login.path.mkdir(parents=True)
    try:
        with pytest.raises(ProfileCustodyRecordError):
            login.human.mint_receipt(bound.lease.session_id, captured)
        with pytest.raises(AutomationCustodyError):
            login.human.mint_receipt(bound.lease.session_id, captured)
    finally:
        login.path.rmdir()


_PERSISTING_MODES = frozenset({"success", "reseal_checks"})

_EARLY_MODES: dict[str, Callable[[_Login, _Bound], None]] = {
    "retired_before_mint": _retired_before_mint,
    "lease_gone": _lease_gone,
    "advanced_before_mint": _advanced_before_mint,
    "publication_failure": _publication_failure,
}


def _mint_receipt(login: _Login, bound: _Bound, mode: str) -> _Minted | None:
    lease, custody, path, store = bound.lease, login.custody, login.path, login.store
    captured = bound.sign_in.establish().current
    acknowledged = login.human.mint_receipt(lease.session_id, captured)
    assert acknowledged.authenticated_at == bound.outcome.authenticated_at
    assert acknowledged.idle_deadline == bound.outcome.idle_deadline
    assert acknowledged.absolute_deadline == bound.outcome.absolute_deadline
    assert not acknowledged.resumed
    assert acknowledged.session_persisted == (mode in _PERSISTING_MODES)
    assert custody.require(lease.session_id) == lease
    if mode == "unavailable":
        assert not path.exists() and store.writes == 0
        return None
    check = binding_probe.verify_profile_session_binding(
        sign_in=bound.sign_in, login_id=lease.originating_login_id or ""
    )
    assert check.verdict is binding_probe.ReceiptBindingVerdict.BOUND
    assert check.record is not None and check.record.sign_in == captured
    assert path.is_file() and store.writes == 1
    return _Minted(acknowledged, check.record.session_id)


def _resume_and_renew(
    login: _Login, bound: _Bound, minted: _Minted
) -> tuple[AccessSession, AccessSession, tuple[bytearray, ...]]:
    human, custody, path, store = login.human, login.custody, login.path, login.store
    original = path.read_bytes()
    with borrow_receipt_proof(profile_id=login.identity.binding.profile_id) as receipt_key:
        resumed_id, resumed_outcome = human.resume(receipt_key, login_id=bound.lease.originating_login_id)
    successor = _human_lease(login.identity, resumed_outcome)
    resumed_ack, resumed_pending = human.bind(resumed_id, successor, persist_receipt=True)
    assert not resumed_pending
    assert resumed_ack.resumed and resumed_ack.session_persisted
    assert resumed_ack.authenticated_at == minted.acknowledged.authenticated_at
    assert resumed_ack.idle_deadline == minted.acknowledged.idle_deadline
    assert resumed_ack.absolute_deadline == minted.acknowledged.absolute_deadline
    assert custody.require(successor.session_id) == successor
    assert path.read_bytes() == original and store.writes == 1
    # Both password and resumed custody retain only a wipeable sealing key.
    keys = tuple(human._sealing_keys.values())
    assert len(keys) == 2 and all(any(key) for key in keys)
    store.available = False
    renewed = successor.model_copy(
        update={
            "issued_at": now(),
            "issued_monotonic": time.monotonic(),
            "expires_at": successor.expires_at + timedelta(hours=5),
        }
    )
    human.refresh(renewed)
    updated = receipt.inspect_profile_session(storage_root=login.root, profile_id=login.identity.binding.profile_id)
    assert updated is not None
    assert updated.session_id == minted.record_session_id
    assert updated.idle_deadline == updated.absolute_deadline == renewed.expires_at
    assert store.writes == 1
    return successor, renewed, keys


def _keep_authority_after_failed_reseal(login: _Login, renewed: AccessSession) -> None:
    # A failed optional receipt write leaves current authority available.
    with pytest.MonkeyPatch.context() as failed_write:
        events: list[str] = []

        def cannot_reseal(**_kwargs: object) -> NoReturn:
            raise ProfileCustodyRecordError("synthetic persistence failure")

        failed_write.setattr(profile_login, "refresh_profile_session_with_key", cannot_reseal)
        failed_write.setattr(
            profile_login,
            "diagnostic_event",
            lambda _log, event, **_kwargs: events.append(event),
        )
        login.human.refresh(renewed)
        assert login.custody.require(renewed.session_id) == renewed
        assert events == ["profile_receipt_refresh_failed"]


def _logout_fences_resealing(
    login: _Login,
    bound: _Bound,
    successor: AccessSession,
    renewed: AccessSession,
    keys: tuple[bytearray, ...],
) -> None:
    human, custody, path = login.human, login.custody, login.path
    # Logout fences resealing even if the worker has not received retirement yet.
    bound.sign_in.advance()
    fenced = path.read_bytes()
    human.refresh(renewed)
    assert path.read_bytes() == fenced
    human.discard(bound.lease.session_id)
    custody.retire(bound.lease.session_id)
    human.discard(successor.session_id)
    custody.retire(successor.session_id)
    assert all(not any(key) for key in keys)
    # A retired session is reported as ended, the way the runtime's authority reports it.
    with pytest.raises(ProfileAccessRefusedError) as ended:
        human.refresh(renewed)
    assert ended.value.reason is AccessDenialCode.AUTHENTICATION_REQUIRED
    login.store.available = True


def _reseal_checks(login: _Login, bound: _Bound) -> None:
    """Each fence of the reseal refuses, and one reseal validates its path and verifies its root once."""
    lease, path = bound.lease, login.path
    key = login.human._sealing_keys[lease.session_id]
    later = lease.expires_at + timedelta(hours=1)

    def reseal(deadline: datetime, receipt_key: bytearray = key) -> bool:
        return receipt.refresh_profile_session_with_key(
            sign_in=bound.sign_in,
            receipt_key=receipt_key,
            login_id=lease.originating_login_id or "",
            now=now(),
            deadline=deadline,
        )

    original = path.read_bytes()
    journal = receipt.profile_session_retirement_path(
        storage_root=login.root, profile_id=login.identity.binding.profile_id
    )
    # An interrupted key swap owns the receipt until it is recovered.
    journal.write_bytes(b"pending key swap")
    try:
        assert not reseal(later)
    finally:
        journal.unlink()
    # Another key cannot open the receipt it would reseal.
    assert not reseal(later, bytearray(secrets.token_bytes(len(key))))
    # A deadline the receipt already covers writes nothing.
    assert reseal(lease.expires_at)
    assert path.read_bytes() == original
    # Without a receipt there is nothing to reseal, and none is minted.
    path.unlink()
    try:
        assert not reseal(later)
        assert not path.exists()
    finally:
        path.write_bytes(original)

    validations: list[str] = []
    opened: Counter[str] = Counter()
    validate = keystore_paths.validate_keystore_separation
    open_component = filesystem_primitives.open_verified_component

    def counting_validation(root: Path, bucket_id: str, **kwargs: Any) -> None:
        validations.append(bucket_id)
        validate(root, bucket_id, **kwargs)

    def counting_open(current: str, access: int, **kwargs: Any) -> int:
        opened[current] += 1
        return open_component(current, access, **kwargs)

    prior = receipt.inspect_profile_session(storage_root=login.root, profile_id=login.identity.binding.profile_id)
    assert prior is not None
    assert min(prior.idle_deadline, prior.absolute_deadline) < later
    with pytest.MonkeyPatch.context() as counting:
        counting.setattr(keystore_paths, "validate_keystore_separation", counting_validation)
        counting.setattr(filesystem_primitives, "open_verified_component", counting_open)
        assert reseal(later)

    # The lock, the retirement journal and the write share one validated path,
    # and the storage root is verified once for the root lock it provisions.
    assert len(validations) == 1
    assert {component: opened[component] for component in windows_component_paths(login.root)} == dict.fromkeys(
        windows_component_paths(login.root), 1
    )
    updated = receipt.inspect_profile_session(storage_root=login.root, profile_id=login.identity.binding.profile_id)
    assert updated is not None
    assert updated.idle_deadline == max(prior.idle_deadline, later)
    assert updated.absolute_deadline == max(prior.absolute_deadline, later)


def _run_mode(login: _Login, patcher: pytest.MonkeyPatch, mode: str) -> None:
    if mode == "throttled":
        _refuse_throttled(login, patcher)
        return
    bound = _authenticate_and_bind(login, mode)
    if mode == "default":
        assert login.human.seconds_until_expiry() is None
        return
    waiting = login.human.seconds_until_expiry()
    assert waiting is not None and 0 < waiting <= 300
    early = _EARLY_MODES.get(mode)
    if early is not None:
        early(login, bound)
        return
    minted = _mint_receipt(login, bound, mode)
    if minted is None:
        return
    if mode == "reseal_checks":
        _reseal_checks(login, bound)
        return
    successor, renewed, keys = _resume_and_renew(login, bound, minted)
    _keep_authority_after_failed_reseal(login, renewed)
    _logout_fences_resealing(login, bound, successor, renewed, keys)


def _exercise(tmp_path: Path, mode: str) -> None:
    # Keep the explicit keyring port installed through storage-root teardown,
    # which reaps any receipt minted by this child process.
    with pytest.MonkeyPatch.context() as patcher, profile_adapter_composition(), worker_profiles(tmp_path) as profiles:
        root, ((identity, _), _) = profiles
        with override_settings(cadrumo_storage_root=root):
            store = _Keyring(available=mode != "unavailable")
            patcher.setattr(
                acceleration_keychain, "acceleration_keychain_keyring", lambda: (store, _KeyringError, _KeyringError)
            )
            custody = ProfileWorkerCustody(identity, storage_root=root)
            human = ProfileWorkerHumanLogin(custody, decode=lambda: profile_authority_contexts()[1])
            path = receipt.profile_session_path(storage_root=root, profile_id=identity.binding.profile_id)
            proof = bytearray(PROFILE_INPUT.encode())
            try:
                _run_mode(_Login(identity, root, store, custody, human, path, proof), patcher, mode)
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
        "throttled",
        "reseal_checks",
    ],
)
def test_worker_human_login_receipt_lifecycle(tmp_path: Path, mode: str) -> None:
    result = run_audited_process(
        [sys.executable, "-m", "cadrumo_runtime.host.tests.test_human_login_receipt", str(tmp_path), mode],
        capture_output=True,
        text=True,
        timeout=None,
        check=False,
    )
    assert result.returncode == 0, result.stderr


if __name__ == "__main__":
    _exercise(Path(sys.argv[1]), sys.argv[2])
