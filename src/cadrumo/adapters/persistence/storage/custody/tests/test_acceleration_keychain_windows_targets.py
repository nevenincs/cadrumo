"""Each acceleration key owns its own Windows Credential Manager target.

The Windows credential store addresses a generic credential by its target name
alone. Every acceleration key once shared the service's single target, and the
keyring backend re-saves that target by reading it, moving the previous holder
aside and writing the new one, so two concurrent sign-ins could each move the
same holder and one of the two new keys was overwritten and lost.

The cases below drive the real Credential Manager under a service token unique
to each case, never the production token, and remove only the targets that
token names.
"""

from __future__ import annotations

import base64
import json
import secrets
import sys
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import keyring
import pytest

from cadrumo.tests.audited_process import run_audited_process

from ......tests.os_keychain_hook import require_os_credential_store
from .. import acceleration_keychain

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_GENERIC_CREDENTIAL = 1
_NOT_FOUND = 1168
_KEYS_PER_PROCESS = 20

_SIGN_IN_SCRIPT = """
import base64, json, secrets, sys, time
from pathlib import Path
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.custody import acceleration_keychain

service, profile_id, ready, go, count = sys.argv[1], UUID(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), int(sys.argv[5])
acceleration_keychain.PROFILE_SESSION_KEYCHAIN_SERVICE = service
keys = {}
errors = []
ready.write_text("ready", encoding="utf-8")
while not go.exists():
    time.sleep(0.001)
for _ in range(count):
    session_id = uuid4()
    key = secrets.token_bytes(32)
    try:
        acceleration_keychain.store_acceleration_secret(profile_id=profile_id, session_id=session_id, session_key=key)
    except Exception as exc:
        errors.append(f"store {session_id}: {type(exc).__name__}: {exc}")
    keys[str(session_id)] = base64.b64encode(key).decode("ascii")
print(json.dumps({"keys": keys, "errors": errors}))
"""


@dataclass(frozen=True, slots=True)
class _TestService:
    """A service token no production entry uses, and the targets it names."""

    name: str

    def owns(self, target: str) -> bool:
        return target == self.name or target.endswith(f"@{self.name}")


@dataclass(frozen=True, slots=True)
class _SignInReport:
    """The keys one sign-in process stored, by session UUID, and any store it saw refused."""

    keys: dict[str, str]
    errors: list[str]


def _credentials() -> list[dict[str, object]]:
    import pywintypes
    import win32cred

    try:
        return list(win32cred.CredEnumerate(None, 0) or [])
    except pywintypes.error as error:
        if error.winerror == _NOT_FOUND:
            return []
        raise


def _credential(target: str) -> dict[str, object] | None:
    import pywintypes
    import win32cred

    try:
        credential = win32cred.CredRead(target, _GENERIC_CREDENTIAL, 0)
    except pywintypes.error as error:
        if error.winerror == _NOT_FOUND:
            return None
        raise
    return dict(credential)


def _secret(credential: dict[str, object]) -> str:
    blob = credential["CredentialBlob"]
    assert isinstance(blob, bytes)
    return blob.decode("utf-16")


@pytest.fixture
def test_service(monkeypatch: pytest.MonkeyPatch) -> Iterator[_TestService]:
    require_os_credential_store()
    service = _TestService(f"cadrumo-test-acceleration-keychain:{uuid4()}")
    assert service.name != acceleration_keychain.PROFILE_SESSION_KEYCHAIN_SERVICE
    monkeypatch.setattr(acceleration_keychain, "PROFILE_SESSION_KEYCHAIN_SERVICE", service.name)
    try:
        yield service
    finally:
        import win32cred

        for credential in _credentials():
            target = credential["TargetName"]
            if credential["Type"] == _GENERIC_CREDENTIAL and isinstance(target, str) and service.owns(target):
                win32cred.CredDelete(target, _GENERIC_CREDENTIAL, 0)


def _sign_in_process(service: str, profile_id: UUID, ready: Path, go: Path) -> _SignInReport:
    completed = run_audited_process(
        [sys.executable, "-c", _SIGN_IN_SCRIPT, service, str(profile_id), str(ready), str(go), str(_KEYS_PER_PROCESS)],
        cwd=Path.cwd(),
        check=False,
        capture_output=True,
        encoding="utf-8",
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    assert isinstance(completed.stdout, str)
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    return _SignInReport(
        keys={str(session): str(key) for session, key in report["keys"].items()},
        errors=[str(error) for error in report["errors"]],
    )


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_concurrent_sign_ins_on_two_roots_keep_both_keys(test_service: _TestService, tmp_path: Path) -> None:
    profiles = (uuid4(), uuid4())
    ready = tuple(tmp_path / f"ready-{index}" for index in range(len(profiles)))
    go = tmp_path / "go"
    with ThreadPoolExecutor(max_workers=len(profiles)) as pool:
        running = [
            pool.submit(_sign_in_process, test_service.name, profile_id, ready_path, go)
            for profile_id, ready_path in zip(profiles, ready, strict=True)
        ]
        deadline = time.monotonic() + 120
        while not all(path.exists() for path in ready):
            assert time.monotonic() < deadline, "a sign-in process never started"
            assert not any(future.done() for future in running), [future.result() for future in running]
            time.sleep(0.01)
        go.write_text("go", encoding="utf-8")
        reports = [future.result() for future in running]

    for report in reports:
        assert report.errors == [], report.errors
    accounts: list[tuple[UUID, UUID, bytes]] = []
    for profile_id, report in zip(profiles, reports, strict=True):
        assert len(report.keys) == _KEYS_PER_PROCESS
        accounts.extend((profile_id, UUID(session), base64.b64decode(key)) for session, key in report.keys.items())

    for profile_id, session_id, key in accounts:
        assert acceleration_keychain.read_acceleration_secret(profile_id=profile_id, session_id=session_id) == key
        account = f"{profile_id}:{session_id}"
        stored = _credential(f"{account}@{test_service.name}")
        assert stored is not None
        assert stored["UserName"] == account
        assert base64.b64decode(_secret(stored)) == key
    # No write touched the shared target any more.
    assert _credential(test_service.name) is None

    for profile_id, session_id, _key in accounts:
        acceleration_keychain.delete_acceleration_secret(
            profile_id=profile_id, session_id=session_id, suppress_unavailable=False
        )
        assert acceleration_keychain.read_acceleration_secret(profile_id=profile_id, session_id=session_id) is None
    assert [
        credential["TargetName"]
        for credential in _credentials()
        if isinstance(credential["TargetName"], str) and test_service.owns(credential["TargetName"])
    ] == []


@pytest.mark.os_keychain
@pytest.mark.windows_only
def test_a_key_under_the_legacy_shared_target_moves_to_its_own_target(test_service: _TestService) -> None:
    profile_id, session_id = uuid4(), uuid4()
    other_profile, other_session = uuid4(), uuid4()
    account = f"{profile_id}:{session_id}"
    key = secrets.token_bytes(32)
    other_key = secrets.token_bytes(32)
    encoded = base64.b64encode(key).decode("ascii")
    # The released writer stored every key through the shared service, which
    # leaves the latest key on the shared target and moves the one before it
    # to ``<account>@<service>``.
    keyring.set_password(test_service.name, f"{other_profile}:{other_session}", base64.b64encode(other_key).decode())
    keyring.set_password(test_service.name, account, encoded)
    legacy = _credential(test_service.name)
    assert legacy is not None
    assert legacy["UserName"] == account
    assert _credential(f"{account}@{test_service.name}") is None

    assert acceleration_keychain.read_acceleration_secret(profile_id=profile_id, session_id=session_id) == key

    migrated = _credential(f"{account}@{test_service.name}")
    assert migrated is not None
    assert migrated["UserName"] == account
    assert _secret(migrated) == encoded
    # The migration only reads the shared target; the entry stays until its
    # own account is deleted.
    residue = _credential(test_service.name)
    assert residue is not None
    assert _secret(residue) == encoded
    # The key the released writer had already moved aside is read in place.
    assert (
        acceleration_keychain.read_acceleration_secret(profile_id=other_profile, session_id=other_session) == other_key
    )

    acceleration_keychain.delete_acceleration_secret(
        profile_id=profile_id, session_id=session_id, suppress_unavailable=False
    )
    assert _credential(f"{account}@{test_service.name}") is None
    assert _credential(test_service.name) is None
    assert acceleration_keychain.read_acceleration_secret(profile_id=profile_id, session_id=session_id) is None
    assert (
        acceleration_keychain.read_acceleration_secret(profile_id=other_profile, session_id=other_session) == other_key
    )
    acceleration_keychain.delete_acceleration_secret(
        profile_id=other_profile, session_id=other_session, suppress_unavailable=False
    )
    assert _credential(f"{other_profile}:{other_session}@{test_service.name}") is None
