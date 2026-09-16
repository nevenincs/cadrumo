"""Creating a profile leaves it unlocked, through the same truth a login uses.

The operator chose the passphrase and the create span proved it against the
custody envelope it had just written. Asking for that same passphrase again
before the new profile can be used answers a question already answered, and it
is what happened: the create span held the unlocked key locally and dropped it,
so every surface that asked afterwards was correctly told nobody was logged in.
The installed workbench showed it plainly -- register, and the very next
admission pass reported ``CREDENTIALS_REQUIRED`` and sent the operator back to
a Login screen for the profile they had just made.

These are proofs against the real door and a real isolated storage root; no
session substrate is mocked. The record check deliberately uses a decode
context from a DIFFERENT pinned authority operation than the registration ran
under, because the authority a surface composes for the workbench is never the
same operation object the credential screen used, and an authority that only
survives its own operation would pass a weaker test and fail in production.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody.acceleration_receipt import profile_session_path
from ....adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from ....core.paths import effective_storage_root
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ..login_session_port import profile_current_bucket_session, profile_session_serves_bucket
from ..profile_record_repository import require_profile_record_session
from ..registration import register_profile_with_credentials

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CREDENTIAL = "registration-admits-the-profile-it-creates"


def test_registration_leaves_a_live_session_serving_the_created_profile(tmp_path: Path) -> None:
    """DISCRIMINATING: the absence that sent a just-registered operator back to Login."""
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation():
        create_context, decode_context = profile_authority_contexts()

        assert profile_current_bucket_session() is None

        outcome = register_profile_with_credentials(
            label="Registered And Admitted",
            passphrase=_CREDENTIAL,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        )

        live = profile_current_bucket_session()
        assert live is not None
        assert profile_session_serves_bucket(live, outcome.bucket_id)
        assert live.sealed is False


def test_the_created_profile_s_record_reads_under_a_later_operation(tmp_path: Path) -> None:
    """The authority must outlive the operation the registration ran under.

    A record session is pinned to a decode context and refuses a read that
    crosses a generation boundary. The workbench composes its own operation
    after the credential screen has closed, so the context it presents is a
    different object from the one registration used -- equal in generation and
    schema, which is what the guard actually requires. Proving the read here
    settles that the guard compares meaning rather than identity.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        with bundled_indexed_authority().operation():
            create_context, decode_context = profile_authority_contexts()
            outcome = register_profile_with_credentials(
                label="Readable After Registration",
                passphrase=_CREDENTIAL,
                profile_create_context=create_context,
                profile_decode_context=decode_context,
            )

        # A second, genuinely separate lease: the workbench composes its own
        # operation after the credential screen has closed.
        with bundled_indexed_authority().operation() as later_operation:
            session = require_profile_record_session(
                outcome.profile_id,
                profile_decode_context=later_operation.profile_decode_context(),
            )

            assert session.profile_id == UUID(outcome.profile_id)
            assert session.closed is False


def test_registration_mints_no_acceleration_receipt(tmp_path: Path) -> None:
    """Unlocking this process is not a decision about the next one.

    A receipt is what carries a session across process boundaries with no
    passphrase, which is a separate question from whether the operator who
    just created a profile should be able to use it. Minting one here would
    answer that question on their behalf.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path), bundled_indexed_authority().operation():
        create_context, decode_context = profile_authority_contexts()
        outcome = register_profile_with_credentials(
            label="No Receipt On Creation",
            passphrase=_CREDENTIAL,
            profile_create_context=create_context,
            profile_decode_context=decode_context,
        )

        receipt = profile_session_path(
            storage_root=effective_storage_root(),
            profile_id=UUID(outcome.profile_id),
        )

        assert profile_current_bucket_session() is not None
        assert not receipt.exists()
