"""Creation must retire the profile whose selection it takes away.

Registering a profile compare-and-swaps the active pointer onto the new capsule
inside the create transaction's own durable journal. Whatever the pointer named
before is displaced by that swap, and until the transaction retired it, the
displaced profile kept a resumable acceleration receipt: its bucket key stayed
recoverable with no passphrase for the whole window until some later login
happened to observe the boundary, and permanently for a registration that no
login ever follows.

Every profile here is created through the production credential door and
unlocked through the public login service against an isolated real storage
root. Each operator step runs in its own interpreter, because that is what an
``aeat`` invocation is and it is the only configuration in which no live
in-process session can name the profile being displaced -- a single-process
proof of this property is a proof of a different property that shares its name.

The measurement is on RECOVERED KEY MATERIAL rather than on a vanished file: a
variant that unlinks the receipt while leaving the key reachable by some other
route would satisfy a file-absence check and be the same defect.
"""

from __future__ import annotations

from multiprocessing import get_context
from multiprocessing.queues import Queue
from pathlib import Path
from typing import TypedDict
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import profile_session_path
from ....core import read_pointer
from ....tests.secure_sql import isolated_profile_storage_root
from .._registration import ProfileRegistrationError, register_profile_with_credentials
from .test_login_handover import (
    _assert_no_resumable_material,
    _child_settings,
    _close_child_login,
    _login_in_separate_process,
    _probe_resumable_session,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD_DISPLACED = "registration-displaced-password-one"  # noqa: S105 - real test credential
_PASSWORD_ENTERING = "registration-displaced-password-two"  # noqa: S105 - real test credential


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
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=label, passphrase=password
        )
        result_queue.put({"profile_id": outcome.profile_id, "label": outcome.label})
    finally:
        _close_child_login(token)


def _register_in_separate_process(storage_root: Path, label: str, password: str) -> _ChildRegistrationResult:
    """Run one registration in its own interpreter, which is what every ``aeat`` call is."""
    context = get_context("spawn")
    result_queue: Queue[_ChildRegistrationResult] = context.Queue()
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
    settings, token = _child_settings(storage_root)
    _ = settings
    try:
        try:
            register_profile_with_credentials(
                recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=label, passphrase=password
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
        _close_child_login(token)


def _attempt_registration_in_separate_process(storage_root: Path, label: str, password: str) -> _ChildRefusalResult:
    context = get_context("spawn")
    result_queue: Queue[_ChildRefusalResult] = context.Queue()
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
def test_registration_retires_the_profile_it_displaces_without_waiting_for_a_login(
    tmp_path: Path,
) -> None:
    """The displaced profile holds no recoverable key material once creation returns.

    No login runs after the registration, which is the case the login-side
    retirement can never cover: a registration that nothing follows would
    otherwise leave the displaced profile resumable for good.

    The probe deliberately runs before any further authentication, so what it
    measures is the create transaction's own effect rather than a later login's.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Displacement One", _PASSWORD_DISPLACED)["profile_id"]
        opened = _login_in_separate_process(storage_root, displaced, _PASSWORD_DISPLACED)
        assert opened["bucket_id"] == displaced

        entering = _register_in_separate_process(storage_root, "Displacement Two", _PASSWORD_ENTERING)["profile_id"]

        selected = read_pointer(storage_root)
        assert selected is not None
        assert selected.bucket_id == entering, "creation is expected to select the new capsule"

        _assert_no_resumable_material(
            storage_root,
            displaced,
            after="a registration that displaced the selected profile",
        )


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_the_displaced_profile_is_resumable_until_the_registration_displaces_it(
    tmp_path: Path,
) -> None:
    """The anti-tautology arm: the same probe DOES recover the key while the profile is selected.

    Without this, the refusal above would be satisfied by a probe that can never
    reach the material from another process at all, and the suite would pass
    with the defect fully intact.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        selected = _register_in_separate_process(storage_root, "Resumable One", _PASSWORD_DISPLACED)["profile_id"]
        _login_in_separate_process(storage_root, selected, _PASSWORD_DISPLACED)

        probe = _probe_resumable_session(storage_root, selected)

        assert probe["resumed"] is True
        assert probe["dek_length"] == 32, "a selected profile's own receipt must still resume its session"
        assert probe["refusal"] is None


def test_a_registration_that_displaces_nothing_still_publishes_its_profile(
    tmp_path: Path,
) -> None:
    """A first registration has no predecessor to retire and must not refuse.

    The retirement reads the pointer value the transaction journalled before it
    staged anything. On the very first registration there is none, and on a
    re-registration of the already-selected profile the predecessor is the
    profile being published. Neither is a displacement, and treating either as
    one would refuse the profile-creation door outright.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        assert read_pointer(storage_root) is None

        first = _register_in_separate_process(storage_root, "Unopposed One", _PASSWORD_DISPLACED)

        selected = read_pointer(storage_root)
        assert selected is not None
        assert selected.bucket_id == first["profile_id"]
        assert first["label"] == "Unopposed One"

        opened = _login_in_separate_process(storage_root, first["profile_id"], _PASSWORD_DISPLACED)
        assert opened["bucket_id"] == first["profile_id"]


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_the_entering_profile_keeps_the_session_the_registration_gave_it(
    tmp_path: Path,
) -> None:
    """Retirement reaches the displaced profile and stops there.

    A retirement that resolved the wrong identity -- the profile being published
    rather than the one being displaced -- would satisfy the non-resurrection
    proof above while destroying the session of the profile the operator just
    created. This pins the opposite direction: after the displacement, the new
    profile authenticates and its own receipt resumes.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Survivor One", _PASSWORD_DISPLACED)["profile_id"]
        _login_in_separate_process(storage_root, displaced, _PASSWORD_DISPLACED)

        entering = _register_in_separate_process(storage_root, "Survivor Two", _PASSWORD_ENTERING)["profile_id"]
        opened = _login_in_separate_process(storage_root, entering, _PASSWORD_ENTERING)
        assert opened["bucket_id"] == entering

        probe = _probe_resumable_session(storage_root, entering)
        assert probe["resumed"] is True
        assert probe["dek_length"] == 32


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_a_retirement_that_cannot_complete_refuses_the_registration_in_its_own_words(
    tmp_path: Path,
) -> None:
    """A retirement that did not complete must refuse, and must say what happened.

    The refusal itself is the safety property: the removal is ordered ahead of
    the pointer compare-and-swap, so a failure leaves the pointer on the
    displaced profile rather than selecting the new capsule over a session that
    is still live. What this pins beyond that is the ACCOUNT the operator gets.
    The create transaction refuses a label collision and a failed retirement
    through one exception family, and reporting the second as the first sends
    the operator off to rename a brand-new profile whose label was never the
    problem.

    The obstruction is a real filesystem state rather than a patched function:
    the receipt path is occupied by a non-empty directory, so the unlink cannot
    succeed on any platform and the primitive's own absence check reports it.
    The unobstructed control is the displacement test at the top of this module
    -- without it this case would be satisfied by a registration door that
    refuses unconditionally.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        displaced = _register_in_separate_process(storage_root, "Obstructed One", _PASSWORD_DISPLACED)["profile_id"]
        _login_in_separate_process(storage_root, displaced, _PASSWORD_DISPLACED)

        receipt = profile_session_path(storage_root=storage_root, profile_id=UUID(displaced))
        assert receipt.exists(), "the displaced profile must hold a receipt for the retirement to reach"
        receipt.unlink()
        receipt.mkdir()
        (receipt / "occupant.bin").write_bytes(b"an occupied receipt path cannot be unlinked")

        refusal = _attempt_registration_in_separate_process(storage_root, "Obstructed Two", _PASSWORD_ENTERING)

        assert refusal["refused"] is True
        assert refusal["cause"] == "ProfileCustodyDisplacedSessionRetirementError"
        assert refusal["translated_message"] == (
            "application.user_profile.errors.registration_displaced_session_not_retired"
        )
        assert refusal["translated_message"] != "application.user_profile.errors.profile_already_exists"

        selected = read_pointer(storage_root)
        assert selected is not None
        assert selected.bucket_id == displaced, (
            "a refused retirement must leave the pointer on the profile it failed to retire"
        )
