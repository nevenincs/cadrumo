"""Registration changes selection while preserving runtime-owned human sign-in.

Each registration and proof-borrowing probe uses a fresh interpreter and real
isolated storage. Selecting another profile does not authorize receipt deletion.
"""

from __future__ import annotations

from multiprocessing import get_context
from multiprocessing.queues import Queue
from pathlib import Path
from typing import TypedDict
from uuid import UUID

import pytest

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.user_profile.registration import ProfileRegistrationError, register_profile_with_credentials
from cadrumo.core.bucket_pointer import read_pointer
from cadrumo.tests.os_keychain_hook import require_os_credential_store

from .test_login_handover import (
    _child_settings,
    _close_child_login,
    _login_in_separate_process,
    _probe_resumable_session,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CREDENTIAL_DISPLACED = "registration-displaced-password-one"
_CREDENTIAL_ENTERING = "registration-displaced-password-two"


class _ChildRegistrationResult(TypedDict):
    profile_id: str
    label: str


class _ChildRefusalResult(TypedDict):
    refused: bool
    translated_message: str | None
    cause: str | None


def _register_in_separate_process_child(
    storage_root: Path,
    label: str,
    password: str,
    result_queue: Queue[_ChildRegistrationResult],
) -> None:
    """Create one profile the way an operator invocation does: a fresh process."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    settings, token, composition = _child_settings(storage_root)
    _ = settings
    try:
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=password,
            profile_create_context=_profile_create_context_for_test,
            profile_decode_context=_profile_decode_context_for_test,
        )
        result_queue.put({"profile_id": outcome.profile_id, "label": outcome.label})
    finally:
        _close_child_login(token, composition)


def _register_in_separate_process(storage_root: Path, label: str, password: str) -> _ChildRegistrationResult:
    """Run one registration in its own interpreter, which is what every ``aeat`` call is."""
    context = get_context("spawn")
    result_queue: Queue[_ChildRegistrationResult] = Queue(ctx=context)
    child = context.Process(
        target=_register_in_separate_process_child,
        args=(storage_root, label, password, result_queue),
    )
    child.start()
    try:
        result = result_queue.get(timeout=180)
        child.join(timeout=30)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


def _attempt_registration_in_separate_process_child(
    storage_root: Path,
    label: str,
    password: str,
    result_queue: Queue[_ChildRefusalResult],
) -> None:
    """Report whatever the registration door tells the operator, refusal included."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()
    settings, token, composition = _child_settings(storage_root)
    _ = settings
    try:
        try:
            register_profile_with_credentials(
                label=label,
                passphrase=password,
                profile_create_context=_profile_create_context_for_test,
                profile_decode_context=_profile_decode_context_for_test,
            )
        except ProfileRegistrationError as exc:
            result_queue.put(
                {
                    "refused": True,
                    "translated_message": exc.translated_message,
                    "cause": type(exc.__cause__).__name__ if exc.__cause__ is not None else None,
                }
            )
        else:
            result_queue.put({"refused": False, "translated_message": None, "cause": None})
    finally:
        _close_child_login(token, composition)


def _attempt_registration_in_separate_process(storage_root: Path, label: str, password: str) -> _ChildRefusalResult:
    context = get_context("spawn")
    result_queue: Queue[_ChildRefusalResult] = Queue(ctx=context)
    child = context.Process(
        target=_attempt_registration_in_separate_process_child,
        args=(storage_root, label, password, result_queue),
    )
    child.start()
    try:
        result = result_queue.get(timeout=180)
        child.join(timeout=30)
        assert child.exitcode == 0
        return result
    finally:
        if child.is_alive():
            child.terminate()
            child.join(timeout=30)


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_registration_preserves_the_displaced_profiles_signed_in_receipt(
    tmp_path: Path,
) -> None:
    """A selection change preserves both receipt bytes and usable proof."""
    require_os_credential_store()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Displacement One", _CREDENTIAL_DISPLACED)["profile_id"]
        opened = _login_in_separate_process(storage_root, displaced, _CREDENTIAL_DISPLACED)
        assert opened["bucket_id"] == displaced
        receipt = profile_session_path(storage_root=storage_root, profile_id=UUID(displaced))
        saved = receipt.read_bytes()

        entering = _register_in_separate_process(storage_root, "Displacement Two", _CREDENTIAL_ENTERING)["profile_id"]

        selected = read_pointer(storage_root)
        assert selected.bucket_id == entering, "creation is expected to select the new capsule"

        assert receipt.read_bytes() == saved
        probe = _probe_resumable_session(storage_root, displaced)
        assert probe["resumed"] is True
        assert probe["dek_length"] == 32
        assert probe["refusal"] is None


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_a_selected_profiles_saved_sign_in_is_resumable(
    tmp_path: Path,
) -> None:
    """The same cross-process probe can recover an explicitly saved sign-in."""
    require_os_credential_store()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        selected = _register_in_separate_process(storage_root, "Resumable One", _CREDENTIAL_DISPLACED)["profile_id"]
        _login_in_separate_process(storage_root, selected, _CREDENTIAL_DISPLACED)

        probe = _probe_resumable_session(storage_root, selected)

        assert probe["resumed"] is True
        assert probe["dek_length"] == 32, "a selected profile's own receipt must still resume its session"
        assert probe["refusal"] is None


def test_a_registration_that_displaces_nothing_still_publishes_its_profile(
    tmp_path: Path,
) -> None:
    """First registration publishes a capsule that can authenticate."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        assert read_pointer(storage_root).bucket_id is None

        first = _register_in_separate_process(storage_root, "Unopposed One", _CREDENTIAL_DISPLACED)

        selected = read_pointer(storage_root)
        assert selected.bucket_id == first["profile_id"]
        assert first["label"] == "Unopposed One"

        opened = _login_in_separate_process(storage_root, first["profile_id"], _CREDENTIAL_DISPLACED)
        assert opened["bucket_id"] == first["profile_id"]


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_the_entering_profile_keeps_the_session_the_registration_gave_it(
    tmp_path: Path,
) -> None:
    """The newly selected profile can authenticate and explicitly save sign-in."""
    require_os_credential_store()
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Survivor One", _CREDENTIAL_DISPLACED)["profile_id"]
        _login_in_separate_process(storage_root, displaced, _CREDENTIAL_DISPLACED)

        entering = _register_in_separate_process(storage_root, "Survivor Two", _CREDENTIAL_ENTERING)["profile_id"]
        opened = _login_in_separate_process(storage_root, entering, _CREDENTIAL_ENTERING)
        assert opened["bucket_id"] == entering

        probe = _probe_resumable_session(storage_root, entering)
        assert probe["resumed"] is True
        assert probe["dek_length"] == 32


def test_registration_does_not_delete_an_obstructed_foreign_receipt(
    tmp_path: Path,
) -> None:
    """Selection changes neither inspect nor mutate another profile's receipt."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Obstructed One", _CREDENTIAL_DISPLACED)["profile_id"]
        receipt = profile_session_path(storage_root=storage_root, profile_id=UUID(displaced))
        assert not receipt.exists()
        receipt.mkdir(parents=True)
        sentinel = b"runtime-owned receipt location must survive registration"
        (receipt / "occupant.bin").write_bytes(sentinel)

        refusal = _attempt_registration_in_separate_process(storage_root, "Obstructed Two", _CREDENTIAL_ENTERING)

        assert refusal == {"refused": False, "translated_message": None, "cause": None}
        selected = read_pointer(storage_root)
        assert selected.bucket_id is not None and selected.bucket_id != displaced
        assert (receipt / "occupant.bin").read_bytes() == sentinel
