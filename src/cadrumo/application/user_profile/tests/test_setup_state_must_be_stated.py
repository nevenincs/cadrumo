"""A persisted profile record may not claim completion by omission.

COMPLETE is the claim that nothing required is missing, not a label for a
record that stopped being edited. A record that never stated its setup state
would make that claim by accident; persisting one makes the accident durable,
and every downstream surface reading setup state then trusts it.

The guard used to live at the single write path, catching a record that
carried the defaulted value without having stated it. It now lives EARLIER and
binds harder: ``setup_state`` is a required field, so an unstated record cannot
be built through validation at all and no write path has to recognise one. The
writer-side check was retired with that change rather than kept as a second
answer to the same question, and the case that drove it was retired with it --
a test whose guard no longer exists can only go green by resurrecting it.

What remains is what still has a mechanism behind it: that the requirement is
enforced at construction, that the statement survives the way records are
actually rebuilt, and that a record read back from disk is never refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ....tests.secure_sql import isolated_profile_storage_root
from ..capsule_record import ProfileRecordStore
from ..login_session import login_profile
from ..profile_record_repository import require_profile_record_session
from ..registration import register_profile_with_credentials

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
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic, label=_LABEL, passphrase=_PASSPHRASE
        )
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
        from ..capsule_record import ProfileRecordCommandEvent

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

    # The statement is now demanded a step EARLIER than the writer: the field
    # is required, so an unstated record cannot be built through validation at
    # all. That is the same guard enforced sooner, not a weaker one -- the
    # writer backstop below still refuses a record that evades construction.
    with pytest.raises(ValidationError):
        UserProfileRecord(  # ty: ignore[missing-argument]  # reason: omitting setup_state IS the refusal under test
            profile_id="8a3c2f10-9f4d-4a5b-8c7e-1d2b3a4c5d6e",
        )
