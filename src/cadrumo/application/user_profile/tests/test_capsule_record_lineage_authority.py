"""The session-level guards that make a profile record un-substitutable.

``ProfileRecordSession`` is the short-lived authority bound to one unlocked
custody envelope. Three of its guards decide whether a record may be written at
all, and each answers a question the record model itself cannot:

- ``encryption_key`` must refuse once the session is retired. ``close``
  zeroises the DEK in place and leaves the object intact, so a retired
  authority is indistinguishable from a live one by inspection. Without the
  refusal a caller does not get an error -- it gets thirty-two zero bytes and
  encrypts with them.
- ``assert_initial_record`` must refuse a record that is not the start of a
  chain.
- ``assert_replacement`` must refuse a successor that does not descend from the
  record it claims to replace, which is the anti-fork and anti-replay
  invariant.

The record model already refuses shapes that are internally impossible -- a
revision-one record carrying a predecessor, a mismatched ``content_digest``.
These guards cover what it cannot see: whether a well-formed record belongs to
THIS session and THIS chain. The forked record below is the case that matters,
because it is valid in isolation and wrong only in context.

Every refusal is paired with the acceptance it must not break, so a session
that refused everything would fail rather than pass.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from cadrumo.application.user_profile.capsule_record import ProfileRecordIntegrityError, ProfileRecordSession

from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _session(profile_id: UUID) -> ProfileRecordSession:
    """Build the real authority, bypassing only the envelope it binds to."""
    return ProfileRecordSession(
        profile_id=profile_id,
        envelope_digest="a" * 64,
        password_generation=1,
        dek_epoch="e" * 32,
        _dek=bytearray(b"k" * 32),
    )


def _record(
    profile_id: UUID,
    *,
    revision: int = 1,
    predecessor: str | None = None,
    state: ProfileSetupState = ProfileSetupState.INCOMPLETE,
) -> UserProfileRecord:
    """Build a record that is internally valid, whatever chain it belongs to."""
    return UserProfileRecord(
        profile_id=str(profile_id),
        setup_state=state,
        record_revision=revision,
        previous_record_digest=predecessor,
    )


def test_a_retired_session_refuses_to_hand_out_its_key() -> None:
    """DISCRIMINATING: the failure mode is silent, not loud.

    A zeroised DEK is still thirty-two bytes. Without this refusal the caller
    encrypts the profile record under an all-zero key and no error is raised
    anywhere.
    """
    session = _session(uuid4())
    session.close()

    with pytest.raises(ProfileRecordIntegrityError, match="closed"):
        session.encryption_key()


def test_a_live_session_still_hands_out_its_key() -> None:
    """ANTI-TAUTOLOGY: refusing always would satisfy the test above."""
    session = _session(uuid4())

    assert session.encryption_key() == b"k" * 32


def test_the_initial_record_of_this_profile_is_accepted() -> None:
    """The chain start the guard exists to admit."""
    profile_id = uuid4()

    _session(profile_id).assert_initial_record(_record(profile_id))


def test_an_initial_record_naming_another_profile_is_refused() -> None:
    """A record valid in itself, addressed to a different custody session."""
    session = _session(uuid4())

    with pytest.raises(ProfileRecordIntegrityError, match="UUID differs"):
        session.assert_initial_record(_record(uuid4()))


def test_a_later_record_is_refused_as_an_initial_record() -> None:
    """A mid-chain record must not be accepted as the start of one.

    Admitting it would let a capsule be created already carrying history it
    never performed.
    """
    profile_id = uuid4()
    first = _record(profile_id)
    later = _record(profile_id, revision=2, predecessor=first.content_digest)

    with pytest.raises(ProfileRecordIntegrityError, match="exactly revision one"):
        _session(profile_id).assert_initial_record(later)


def test_the_true_successor_is_accepted() -> None:
    """The one replacement that genuinely descends from the current record."""
    profile_id = uuid4()
    current = _record(profile_id)
    successor = _record(
        profile_id,
        revision=2,
        predecessor=current.content_digest,
        state=ProfileSetupState.COMPLETE,
    )

    _session(profile_id).assert_replacement(current, successor)


def test_a_replacement_descending_from_another_record_is_refused() -> None:
    """DISCRIMINATING: the fork, and the reason this guard exists.

    This record is internally valid -- correct revision, a real predecessor
    digest, a consistent content digest. It is wrong only in that its
    predecessor is a DIFFERENT record, so accepting it would splice a foreign
    branch onto this profile's history and drop the current record silently.
    """
    profile_id = uuid4()
    current = _record(profile_id)
    other_branch = _record(profile_id, state=ProfileSetupState.COMPLETE)
    forked = _record(profile_id, revision=2, predecessor=other_branch.content_digest)

    assert forked.previous_record_digest != current.content_digest

    with pytest.raises(ProfileRecordIntegrityError, match="authenticated predecessor"):
        _session(profile_id).assert_replacement(current, forked)


def test_a_replacement_that_skips_a_revision_is_refused() -> None:
    """A successor must be the next revision, not merely a later one."""
    profile_id = uuid4()
    current = _record(profile_id)
    skipped = _record(profile_id, revision=3, predecessor=current.content_digest)

    with pytest.raises(ProfileRecordIntegrityError, match="authenticated predecessor"):
        _session(profile_id).assert_replacement(current, skipped)


def test_a_replacement_naming_another_profile_is_refused() -> None:
    """The session binding is checked on replacement, not only on creation."""
    profile_id = uuid4()
    current = _record(profile_id)
    foreign = _record(uuid4(), revision=2, predecessor=current.content_digest)

    with pytest.raises(ProfileRecordIntegrityError, match="UUID differs"):
        _session(profile_id).assert_replacement(current, foreign)
