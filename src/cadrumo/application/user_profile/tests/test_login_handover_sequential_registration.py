"""Recovery classification across a registration that moves the active pointer.

The sibling handover suite registers every profile it needs before its first
login, so the durable pointer only ever moves inside a login's own handover.
That topology hides a state the recovery classifier is never shown there: an
operator registers a profile, logs into it, registers a SECOND one, and logs
into that. Profile creation compare-and-swaps the active pointer onto the new
capsule as part of its own durable transaction, so between the first login's
completed handover and the second login the pointer moves for a reason the
handover journal cannot describe.

Every profile here is registered through the production credential door and
unlocked through the public login service against an isolated real storage
root. The cross-process cases spawn a real interpreter per login, because that
is what an operator invocation is and it is the only configuration in which the
retirement identity cannot be read from a live in-process session.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core import capture_pointer, read_pointer
from ....core.time import now as _now
from ....tests.secure_sql import isolated_profile_storage_root
from .._login_session import (
    _clear_handover_journal,
    _handover_journal_path,
    _HandoverPhase,
    _load_handover_journal,
    _ProfileLoginHandoverJournal,
    _save_handover_journal,
    login_profile,
)
from .._profile_pointer_transaction import ActiveProfilePointerTransactionError
from .._registration import register_profile_with_credentials
from .test_login_handover import (
    _assert_no_resumable_material,
    _close_live_login,
    _login_in_separate_process,
    _probe_resumable_session,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_PASSWORD_FIRST = "sequential-registration-password-one"  # noqa: S105 - real test credential
_PASSWORD_SECOND = "sequential-registration-password-two"  # noqa: S105 - real test credential


def _register(label: str, password: str) -> str:
    """Create one profile through the production credential door."""
    return register_profile_with_credentials(label=label, passphrase=password).profile_id


def _forge_interrupted_handover(*, storage_root: Path, profile_a: str, profile_b: str, phase: _HandoverPhase) -> None:
    """Publish a real journal chain up to ``phase`` over unrelated pointer bytes.

    Written through the production receipt writer, phase by phase, so the
    witness on disk is byte-identical to one a crashed handover would leave.
    The pointer witnesses deliberately name neither the live pointer nor
    anything reachable from it: that is the state the classifier must keep
    refusing.
    """
    journal = _ProfileLoginHandoverJournal.prepare(
        profile_a=profile_a,
        profile_b=profile_b,
        pointer_before=b'bucket_id = "unrelated-before"\nschema_version = 1\n',
        pointer_after=b'bucket_id = "unrelated-after"\nschema_version = 1\n',
        activation_at=_now(),
    )
    _save_handover_journal(storage_root=storage_root, journal=journal)
    for step in (
        _HandoverPhase.POINTER_PUBLISHED,
        _HandoverPhase.B_BOUND,
        _HandoverPhase.ACCELERATED,
        _HandoverPhase.ACTIVATED,
    ):
        journal = journal.at_phase(step)
        _save_handover_journal(storage_root=storage_root, journal=journal)
        if journal.phase is phase:
            return


def test_registering_a_second_profile_does_not_make_the_next_login_an_interrupted_handover(
    tmp_path: Path,
) -> None:
    """A clean register-login-register-login sequence authenticates the second profile.

    The first login leaves its terminal receipt on disk deliberately, for the
    next login to observe. Registering the second profile then moves the
    pointer through the create transaction's own compare-and-swap, so that
    retained receipt witnesses neither the current pointer nor its own
    predecessor. It records a handover that RAN TO COMPLETION, which is why the
    pointer it happened to leave behind is no longer the pointer's business.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        first = _register("Sequential One", _PASSWORD_FIRST)
        try:
            login_profile(name=first, passphrase_callback=lambda: _PASSWORD_FIRST)

            terminal = _load_handover_journal(storage_root=storage_root)
            assert terminal is not None
            assert terminal.phase is _HandoverPhase.A_RETIRED

            second = _register("Sequential Two", _PASSWORD_SECOND)
            # The create transaction has moved the pointer, so the retained
            # terminal receipt now matches neither of its own witnesses.
            moved = capture_pointer(storage_root)
            assert moved != terminal.pointer_before()
            assert moved != terminal.pointer_after()

            outcome = login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)

            assert outcome.bucket_id == second
            assert outcome.already_authenticated is False
            selected = read_pointer(storage_root)
            assert selected is not None
            assert selected.bucket_id == second
        finally:
            _close_live_login()


def test_a_completed_handover_receipt_is_retired_by_the_next_login_after_a_pointer_move(
    tmp_path: Path,
) -> None:
    """The observed terminal receipt is cleared, not carried into the next handover.

    The receipt exists so exactly one later login can observe the terminal
    boundary. A login that classified it and then left it on disk would hand
    the same stale witness to every subsequent login.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        first = _register("Retire One", _PASSWORD_FIRST)
        try:
            login_profile(name=first, passphrase_callback=lambda: _PASSWORD_FIRST)
            second = _register("Retire Two", _PASSWORD_SECOND)

            login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)

            surviving = _load_handover_journal(storage_root=storage_root)
            assert surviving is not None, "the second login must leave its own terminal receipt"
            assert surviving.phase is _HandoverPhase.A_RETIRED
            assert surviving.profile_b == second
            assert surviving.profile_a == first, (
                "the second login moved away from the first profile and must witness it"
            )
        finally:
            _close_live_login()


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_registration_displaced_profile_keeps_no_resumable_material_after_the_next_login(
    tmp_path: Path,
) -> None:
    """The profile a registration displaced must not stay resumable without its passphrase.

    Every login runs in its own interpreter, because that is the operator flow
    and the only configuration in which no live in-process session can name the
    profile being moved away from. The registration between the two logins
    moves the durable pointer onto the new capsule, so the pointer captured at
    the second login names the profile being logged INTO rather than the one
    being left -- which is precisely the observation gap that lets a surviving
    acceleration receipt hand back a 32-byte bucket key with no passphrase.

    The recovered material is measured rather than the receipt file, because a
    variant that unlinks the receipt while leaving the key recoverable by any
    other route would satisfy a file-absence check and be the same defect.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        first = _register("Displaced One", _PASSWORD_FIRST)

        opened = _login_in_separate_process(storage_root, first, _PASSWORD_FIRST)
        assert opened["bucket_id"] == first

        # Anti-tautology: the receipt IS resumable from a third process while
        # the first profile is the selected one, so the refusal below can only
        # come from the retirement rather than from cross-process reach.
        live = _probe_resumable_session(storage_root, first)
        assert live["resumed"] is True
        assert live["dek_length"] == 32

        second = _register("Displaced Two", _PASSWORD_SECOND)
        displaced = read_pointer(storage_root)
        assert displaced is not None
        assert displaced.bucket_id == second, "profile creation is expected to select the new capsule"

        entered = _login_in_separate_process(storage_root, second, _PASSWORD_SECOND)
        assert entered["bucket_id"] == second

        _assert_no_resumable_material(
            storage_root,
            first,
            after="a login that followed a registration-displaced pointer",
        )


def test_a_genuinely_interrupted_handover_still_refuses_when_the_pointer_matches_neither_state(
    tmp_path: Path,
) -> None:
    """A pre-terminal witness over an unrecognisable pointer keeps failing closed.

    This is the guard the completed-receipt classification must not widen. The
    journal is published through the production writer up to activation, so it
    is exactly what a process death at that phase leaves behind, and its
    pointer witnesses name neither the live pointer nor its predecessor. There
    is real outstanding work recorded against a pointer state that cannot be
    reconciled, and refusing is the only safe answer.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        first = _register("Interrupted One", _PASSWORD_FIRST)
        second = _register("Interrupted Two", _PASSWORD_SECOND)
        try:
            login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)
            terminal = _load_handover_journal(storage_root=storage_root)
            assert terminal is not None
            _clear_handover_journal(storage_root=storage_root, journal=terminal)

            _forge_interrupted_handover(
                storage_root=storage_root,
                profile_a=first,
                profile_b=second,
                phase=_HandoverPhase.ACTIVATED,
            )

            with pytest.raises(ActiveProfilePointerTransactionError) as refusal:
                login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)

            assert refusal.value.context["owner"] == "profile-login-handover"
            assert refusal.value.context["reason"] == "pointer no longer matches either witnessed handover state"
            # The refusal is fail-closed: the witness it could not classify is
            # left exactly where it was for an operator to inspect.
            assert _handover_journal_path(storage_root).is_file()
        finally:
            _close_live_login()


@pytest.mark.os_keychain  # cross-process resume needs a minted acceleration receipt
def test_a_completed_receipt_over_an_unrecognisable_pointer_still_revokes_its_retired_profile(
    tmp_path: Path,
) -> None:
    """Classifying a terminal receipt still runs the retirement it records.

    Recognising the completed receipt must not become a route that merely drops
    it. The retirement it witnesses is a durable delete needing no key, so
    replaying it is idempotent, and running it is what keeps the classification
    fail-closed rather than merely permissive.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        first = _register("Revoked One", _PASSWORD_FIRST)
        second = _register("Revoked Two", _PASSWORD_SECOND)
        try:
            login_profile(name=first, passphrase_callback=lambda: _PASSWORD_FIRST)
            _close_live_login()
            login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)
            _close_live_login()

            # The second login retired the first profile and left the terminal
            # receipt naming it. Re-mint that profile's receipt behind the
            # journal's back so the classification has something real to revoke.
            login_profile(name=first, passphrase_callback=lambda: _PASSWORD_FIRST)
            _close_live_login()
            assert _probe_resumable_session(storage_root, first)["dek_length"] == 32

            witness = _ProfileLoginHandoverJournal.prepare(
                profile_a=first,
                profile_b=second,
                pointer_before=b'bucket_id = "unrelated-before"\nschema_version = 1\n',
                pointer_after=b'bucket_id = "unrelated-after"\nschema_version = 1\n',
                activation_at=_now(),
            )
            existing = _load_handover_journal(storage_root=storage_root)
            if existing is not None:
                _clear_handover_journal(storage_root=storage_root, journal=existing)
            for step in (
                _HandoverPhase.PREPARED,
                _HandoverPhase.POINTER_PUBLISHED,
                _HandoverPhase.B_BOUND,
                _HandoverPhase.ACCELERATED,
                _HandoverPhase.ACTIVATED,
                _HandoverPhase.A_RETIRED,
            ):
                witness = witness.at_phase(step)
                _save_handover_journal(storage_root=storage_root, journal=witness)

            login_profile(name=second, passphrase_callback=lambda: _PASSWORD_SECOND)

            assert _probe_resumable_session(storage_root, first)["dek_length"] == 0
        finally:
            _close_live_login()
