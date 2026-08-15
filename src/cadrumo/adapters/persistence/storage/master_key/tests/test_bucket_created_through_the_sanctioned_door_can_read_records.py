"""The sanctioned creation door yields a bucket whose records read back.

This module exists because the same wrong claim was measured twice, and both
times the measurement stopped one step short. A probe created a profile and
then read a record *without authenticating*, saw a refusal, and reported it as
"the door creates a bucket the storage layer will never open". Registration
closes its record session in a ``finally`` and returns
``ProfileSetupState.INCOMPLETE``, so a freshly created profile is LOCKED. That
is the contract, not a defect.

The property worth holding is therefore the WHOLE door, and nothing shorter:
create, **authenticate**, then decrypt an actual persisted record. Each of the
three reads below crosses a different boundary -- the raw secure-object
namespace listing, a typed workflow record, and the profile record itself --
because the earlier probes each happened to pick a read whose refusal was
ambiguous between "locked" and "no key exists anywhere".

Everything here is real: a real custody envelope, a real Argon2id-derived
wrap, a real per-bucket encrypted SQLite store, on an isolated storage root.
No substitute provider and no synthetic session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ......application.user_profile import (
    login_profile,
    register_profile_with_credentials,
    require_profile_record_session,
)
from ......application.user_profile._capsule_record import ProfileRecordStore
from ......application.workflow import workflow_state_repository
from ......domain.user_profile import ProfileNotFoundError, ProfileSetupState
from ......tests.secure_sql import isolated_profile_storage_root
from ...custody import ProfileCustodyRecordError
from ...runtime_repository import secure_object_repository_for_active_bucket

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


_LABEL = "sanctioned-door-readback"
_PASSPHRASE = "sanctioned-door-readback-passphrase"  # noqa: S105 - real test credential

_PROFILE_VALUE_NAMESPACE = "cadrumo.application.user_profile.value"


def test_bucket_created_through_the_sanctioned_door_can_read_records(tmp_path: Path) -> None:
    """Create, authenticate, then decrypt three real records off disk."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)
        assert outcome.setup_state is ProfileSetupState.INCOMPLETE

        login_profile(name=_LABEL, passphrase_callback=lambda: _PASSPHRASE)

        namespaces = set(secure_object_repository_for_active_bucket().list_namespaces())
        assert _PROFILE_VALUE_NAMESPACE in namespaces

        assert workflow_state_repository().load() is not None

        session = require_profile_record_session(outcome.bucket_id)
        record = ProfileRecordStore(session=session).load().record
        assert record.profile_id == outcome.bucket_id
        assert record.setup_state is ProfileSetupState.INCOMPLETE


def test_record_read_before_authentication_refuses_rather_than_succeeding(tmp_path: Path) -> None:
    """The lock the earlier probes mistook for a defect is real and holds.

    Without this the test above proves nothing: a door that never locks would
    satisfy it just as well as a door that locks and then opens. Asserting the
    refusal is what makes the login step in the test above load-bearing.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)

        with pytest.raises(ProfileNotFoundError, match="authenticated session"):
            ProfileRecordStore(session=require_profile_record_session(outcome.bucket_id)).load()


def test_readback_depends_on_the_on_disk_custody_envelope(tmp_path: Path) -> None:
    """Anti-tautology: destroy the persisted custody material and lose the read.

    Without this, the passing readback above could in principle be served by
    something the create span left in process memory, and the whole module
    would prove nothing about what is on disk. Corrupting
    ``custody/envelope.v1.json`` is the narrowest edit that must cost the
    operator their key, so a login that still succeeds afterwards would mean
    the wrap is not the thing gating access.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(label=_LABEL, passphrase=_PASSPHRASE)

        envelope = storage_root / "buckets" / outcome.bucket_id / "custody" / "envelope.v1.json"
        assert envelope.is_file()
        envelope.write_text("{}", encoding="utf-8")

        # The refusal names the CURRENT format rather than reaching for an
        # older one, which is the ``no-legacy-compatibility`` posture: a
        # custody envelope that does not parse as the current record is
        # corruption now, not a shape to tolerate.
        with pytest.raises(ProfileCustodyRecordError, match="current-format record"):
            login_profile(name=_LABEL, passphrase_callback=lambda: _PASSPHRASE)
