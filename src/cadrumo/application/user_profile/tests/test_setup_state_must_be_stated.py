"""A persisted profile record may not claim completion by omission.

``setup_state`` defaults to COMPLETE, and COMPLETE is the claim that nothing
required is missing rather than a label for a record that stopped being
edited. A record constructed without stating it therefore makes that claim by
accident; persisting one makes the accident durable, and every downstream
surface reading setup state then trusts it.

The guard lives at the single write path rather than on the model, so these
tests drive the real capsule writer against a real published profile. The two
that matter are the mechanism proofs: that the discriminator is not defeated
by the way records are actually rebuilt, and that a record read back from disk
is never refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ....domain.user_profile import ProfileSetupState, UserProfileRecord
from ....tests.secure_sql import isolated_profile_storage_root
from .. import login_profile, register_profile_with_credentials
from .._capsule_record import ProfileRecordIntegrityError, ProfileRecordStore
from .._profile_record_repository import require_profile_record_session

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_LABEL = "Setup State Statement Subject"
_PASSPHRASE = "setup-state-must-be-stated-operator-secret"  # noqa: S105 - synthetic test credential


def _live_store(profile_id: str) -> ProfileRecordStore:
    """Return a record store over the logged-in profile's own session."""
    return ProfileRecordStore(session=require_profile_record_session(profile_id))


def test_a_record_loaded_from_disk_is_never_refused(tmp_path: Path) -> None:
    """The mechanism proof that matters most: save, load, save again.

    Everything else about this guard is worthless if a record that came back
    off disk cannot be written again, because that is every edit an operator
    makes after the first. Proved by round-tripping through the real writer
    rather than by reasoning about what pydantic records in ``model_fields_set``
    when it validates a payload.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)

        loaded = _live_store(outcome.profile_id).load().record

        assert "setup_state" in loaded.model_fields_set

        # The second write is the subject: it is composed from the loaded
        # record exactly as a real edit is, and must not be refused.
        replacement = UserProfileRecord(
            schema_id=loaded.schema_id,
            schema_version=loaded.schema_version,
            profile_id=loaded.profile_id,
            facts=loaded.facts,
            setup_state=loaded.setup_state,
            record_revision=loaded.record_revision + 1,
            previous_record_digest=loaded.content_digest,
            content_digest="",
            created_at=loaded.created_at,
            updated_at=loaded.updated_at,
        )

        assert "setup_state" in replacement.model_fields_set

        from ....domain.buckets import BucketEventType
        from .._capsule_record import ProfileRecordCommandEvent

        # The actual second SAVE, through the real writer. Asserting the field
        # set alone would only re-state what pydantic did; the claim is that
        # the write is not refused, so the write has to happen.
        persisted = _live_store(outcome.profile_id).replace(
            replacement=replacement,
            event=ProfileRecordCommandEvent(
                event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                occurred_at=replacement.updated_at.isoformat(),
            ),
            expected_revision=loaded.record_revision,
            expected_content_digest=loaded.content_digest,
        )

        assert persisted.record_revision == loaded.record_revision + 1
        assert persisted.setup_state == loaded.setup_state

        # And it is readable again afterwards, which is the third leg.
        assert _live_store(outcome.profile_id).load().record.record_revision == persisted.record_revision


def test_model_copy_preserves_the_statement_so_the_guard_is_not_defeated(tmp_path: Path) -> None:
    """A rebuilt record must not lose the fact that its state was stated.

    ``model_copy(update=...)`` is the shape that would quietly defeat this
    guard: if the copy dropped ``setup_state`` from the supplied-field set,
    a legitimate write composed that way would be refused at the persistence
    boundary of a taxpayer's profile, which is worse than the hazard being
    closed. No production path rebuilds a profile record that way today --
    all four construct explicitly -- but this pins the behaviour so a future
    one can rely on it rather than discovering it.
    """
    del tmp_path
    stated = UserProfileRecord(
        profile_id="8a3c2f10-9f4d-4a5b-8c7e-1d2b3a4c5d6e", setup_state=ProfileSetupState.COMPLETE
    )

    carried = stated.model_copy(update={"record_revision": 2})

    assert "setup_state" in carried.model_fields_set

    omitted = UserProfileRecord(profile_id="8a3c2f10-9f4d-4a5b-8c7e-1d2b3a4c5d6e")

    assert "setup_state" not in omitted.model_fields_set
    # Copying does not invent a statement that was never made, either -- the
    # guard would be trivially bypassable if it did.
    assert "setup_state" not in omitted.model_copy(update={"record_revision": 2}).model_fields_set


def test_a_record_that_never_stated_its_setup_state_is_refused_at_the_writer(tmp_path: Path) -> None:
    """The guard itself, driven through the real capsule writer.

    The refused record carries the identical VALUE a stated one would -- the
    default is COMPLETE -- so this proves the discriminator is the statement
    and not the value, which is the whole point.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)
        login_profile(name=outcome.label, passphrase_callback=lambda: _PASSPHRASE)
        store = _live_store(outcome.profile_id)
        current = store.load().record

        unstated = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            schema_id=current.schema_id,
            schema_version=current.schema_version,
            profile_id=current.profile_id,
            facts=current.facts,
            record_revision=current.record_revision + 1,
            previous_record_digest=current.content_digest,
            content_digest="",
            created_at=current.created_at,
            updated_at=current.updated_at,
        )

        assert unstated.setup_state is ProfileSetupState.COMPLETE
        assert "setup_state" not in unstated.model_fields_set

        from ....domain.buckets import BucketEventType
        from .._capsule_record import ProfileRecordCommandEvent

        with pytest.raises(ProfileRecordIntegrityError, match="state its setup state"):
            store.replace(
                replacement=unstated,
                event=ProfileRecordCommandEvent(
                    event_type=BucketEventType.PROFILE_VALUES_UPDATED,
                    occurred_at=unstated.updated_at.isoformat(),
                ),
                expected_revision=current.record_revision,
                expected_content_digest=current.content_digest,
            )
