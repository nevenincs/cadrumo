"""Whether an auth revocation can reach a profile, and what it removes when it does.

Auth custody for one profile is split across two key regimes, and a caller
erasing a profile it has not unlocked has to know which half it can touch. The
AEAT browser session and the auth workflow state are encrypted rows inside the
profile's own store; the certificate-source secret is held outside the capsule
but addressed through a digest derived from the profile's key. Both therefore
need the key. The acquisition lock is the only key-free artefact, and it is the
only one that survives the capsule's destruction.

:func:`operator_auth_revocation_is_reachable` is the question a caller asks
before choosing between the two halves, and it is asserted here in both
directions against one real profile: a predicate that always answered "locked"
would look exactly as green as one that always answered "open", and each is a
different silent failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from ....core import AuthProviderKind, BucketPointer, write_pointer
from ....core.config import load_settings
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_OTHER_PROFILE_ID = "22222222-2222-4222-8222-222222222222"


def _certificate_secret_present(bucket_id: str) -> bool:
    from .._certificate_secret_backend import SecureStorageCertificateSecretBackend

    return SecureStorageCertificateSecretBackend(bucket_id=bucket_id).get("personal") is not None


def test_reachability_answers_both_ways_and_an_open_session_removes_the_out_of_bucket_secret(
    tmp_path: Path,
) -> None:
    from .. import (
        operator_auth_revocation_is_reachable,
        register_operator_certificate_source,
        reset_operator_auth,
        set_operator_certificate_source_secret,
    )

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        with open_test_profile_session(_PROFILE_ID):
            register_minimal_profile(profile_id=_PROFILE_ID, display_name="Alpha operator")
        write_pointer(root, BucketPointer.selected(bucket_id=_PROFILE_ID, transition_revision=1))

        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"test certificate")
        with open_test_profile_session(_PROFILE_ID):
            register_operator_certificate_source(name="personal", certificate_path=certificate_path)
            set_operator_certificate_source_secret(name="personal", secret=SecretStr("test-passphrase"))
            assert _certificate_secret_present(_PROFILE_ID) is True

        # Cold: no session serves the profile, so a revocation cannot open it.
        assert operator_auth_revocation_is_reachable(bucket_id=_PROFILE_ID) is False

        with open_test_profile_session(_PROFILE_ID):
            assert operator_auth_revocation_is_reachable(bucket_id=_PROFILE_ID) is True
            # An open session for ONE profile is not an open session for another:
            # a predicate that reported reachability from any session at all
            # would let a caller revoke against whichever bucket happened to be
            # bound, which is the confusion the underlying span refuses.
            assert operator_auth_revocation_is_reachable(bucket_id=_OTHER_PROFILE_ID) is False

            result = reset_operator_auth(all_providers=True, target_bucket_id=_PROFILE_ID)

        assert result.removed_certificate_secrets == 1
        settings = load_settings()
        blob_root = settings.cadrumo_blob_store_dir
        assert tuple(path for path in blob_root.rglob("*") if path.is_file()) == ()


def test_a_locked_profile_refuses_the_revocation_that_reachability_predicted(
    tmp_path: Path,
) -> None:
    """The predicate and the operation agree, so the choice it drives is sound.

    Asserted against the same profile the previous test revokes successfully:
    without this, a predicate reporting "locked" would be consistent with a
    revocation that quietly worked anyway, and the caller's branch would be
    protecting against nothing.
    """
    from .. import AuthOperationRequiresCustodySessionError, operator_auth_revocation_is_reachable, reset_operator_auth
    from .._acquisition_lock import clear_auth_acquisition_lock
    from .._operator_cleanup import clear_operator_auth_acquisition_locks

    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        with open_test_profile_session(_PROFILE_ID):
            register_minimal_profile(profile_id=_PROFILE_ID, display_name="Alpha operator")
        write_pointer(root, BucketPointer.selected(bucket_id=_PROFILE_ID, transition_revision=1))
        settings = load_settings()

        assert operator_auth_revocation_is_reachable(bucket_id=_PROFILE_ID) is False
        with pytest.raises(AuthOperationRequiresCustodySessionError) as refused:
            reset_operator_auth(all_providers=True, target_bucket_id=_PROFILE_ID)
        assert refused.value.translated_message == "application.auth.operator.errors.revoke_requires_custody_session"

        # The key-free half proceeds against the very profile the revocation
        # just refused, which is the whole reason the two are separable.
        from .. import acquire_auth_acquisition_lock

        with acquire_auth_acquisition_lock(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            ttl_seconds=60,
            operation="test-locked-profile-key-free-half",
        ):
            # Mirrors the erase caller: this is the reset's key-free half, which
            # is the one path entitled to take a lock somebody still holds.
            cleared = clear_operator_auth_acquisition_locks(
                settings,
                bucket_id=_PROFILE_ID,
                allow_held=True,
            )
        assert cleared == (AuthProviderKind.CLAVE_PERMANENTE.value,)
        assert (
            clear_auth_acquisition_lock(
                settings,
                AuthProviderKind.CLAVE_PERMANENTE,
                reason="test-assert-absent",
                bucket_id=_PROFILE_ID,
            ).state.value
            == "absent"
        )
