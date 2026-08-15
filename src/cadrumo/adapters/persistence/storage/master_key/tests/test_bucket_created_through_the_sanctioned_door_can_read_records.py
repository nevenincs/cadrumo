"""A profile created the sanctioned way must be able to read its own records.

EXPECTED RED. This test names a live defect and is expected to fail until the
owner rules on the key-schedule question it pins. It is not an unattributed
failure and it is not flaky: it fails deterministically, for one reason, stated
in its assertion message.

The defect: a bucket counts as registered purely because its profile capsule
exists, and registration is read as enrolment in the master-key schedule. The
sanctioned credential door never enrols a bucket in that schedule -- it mints
the key and wraps it into the password custody envelope -- so the read path
demands a wrapped key that nothing was ever asked to write, and refuses.

The key is not missing. It is present, wrapped under the operator's passphrase,
where profile custody puts it. What is wrong is the statement of which custody
the bucket is under.

Deliberately NOT written as xfail or skip. Both would report success and hide a
state in which an operator's profile exists, is discoverable, and can hold no
readable records. The failure is the artefact.

It is also written to fail LATE rather than early. Everything up to the record
access is asserted first, so the output distinguishes "the profile was never
created" from "the profile was created and its records are unreachable" -- and
only the second is this defect. A test that stopped before touching a record
would pass and prove nothing, which is how this survived.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ......application.user_profile._registration import register_profile_with_credentials
from ......application.workflow import workflow_state_repository
from ......core.config import override_settings
from ......tests.secure_sql import isolated_profile_storage_root
from .._master_key_bucket_dek import bucket_dek_path, bucket_key_schedule

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_PASSPHRASE = "correct horse battery staple"  # noqa: S105 - synthetic test credential, not a secret


def test_a_profile_created_through_the_sanctioned_door_can_read_its_records(tmp_path: Path) -> None:
    """Create a profile the only supported way, then read a record through it."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        registered = register_profile_with_credentials(label="sanctioned-door", passphrase=_PASSPHRASE)
        profile_id = str(getattr(registered, "profile_id", registered))

        # Creation itself succeeds, and the capsule is real: asserting this
        # before the record access is what makes the failure below specific.
        assert profile_id
        schedule = bucket_key_schedule(storage_root=storage_root, bucket_id=profile_id)
        assert schedule is not None, "a published capsule must register its bucket"

        wrapped_dek = bucket_dek_path(storage_root=storage_root, bucket_id=profile_id)

        with override_settings(cadrumo_active_profile=profile_id):
            try:
                state = workflow_state_repository().load()
            except Exception as exc:
                pytest.fail(
                    "EXPECTED RED, live defect: a profile created through the sanctioned credential "
                    "door cannot read its own records.\n"
                    f"  profile            : {profile_id}\n"
                    f"  schedule reported  : {schedule}\n"
                    f"  wrapped DEK on disk: {wrapped_dek.is_file()}\n"
                    f"  record read raised : {type(exc).__name__}: {exc}\n"
                    "The key is not missing -- it is wrapped under the operator's passphrase in the "
                    "profile capsule. The schedule resolver reports master-key custody because a "
                    "capsule exists, while the door that created it enrolled the bucket in password "
                    "custody. Fixing this by minting the master-key-wrapped copy is refused: it would "
                    "put a second wrapped copy of the same key under a different key-encryption key, "
                    "so a keychain compromise would open the bucket without the passphrase.",
                )

        assert state is not None
