"""Logout removes the token and its companion metadata, or neither.

``delete_session`` issued two independent ``repo.delete`` commits. A failure on
the second left the token gone and the metadata behind, which is the worst of
the three possible outcomes: not a half-logout an operator can see and retry,
but a state where ``load_token`` reports no session while the metadata row
still describes one — so status surfaces read as logged in against a
credential that no longer exists, and the stale row survives the retry because
the retry finds nothing left to delete.

Scope note, so the coverage is not read as wider than it is. A failure landing
BETWEEN the two removals is not reproducible without patching the repository
mid-call, and a test double at that boundary would be measuring the double.
What is reproducible — and what the fix actually rests on — is the removal
primitive's own all-or-nothing behaviour, so that is measured directly, on the
real encrypted repository, with a rejection every path shares: a deletion set
containing one unacceptable member. That case discriminates. Under
``apply_batch`` nothing is removed; under the sequential deletes it replaced,
the first row is already gone before the second is refused.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from .....adapters.persistence.storage import SecureObjectDeletion, StorageValidationError
from .....adapters.persistence.storage.crypto.encrypted_columns import secure_object_key_digest
from .....tests.secure_sql import isolated_runtime_profile
from .. import session_store
from ..records import REQUIRED_SCOPES, DriveConfig, OAuthClient, OAuthMetadata, OAuthToken

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_BUCKET_ID = "80cc197a-74fe-4984-93cd-471aa29411ef"  # was 'google-logout-atomicity'
_PROFILE = "operator-google"
_ISSUED_AT = datetime(2026, 5, 26, 9, 0, 0, tzinfo=UTC)
#: A namespace no registry declares. Every write and deletion path validates
#: its namespace against the registry, so this is the one rejection reachable
#: through the real repository without patching anything.
_UNREGISTERED_NAMESPACE = "cadrumo.outbound.google.no-such-namespace"


def _client() -> OAuthClient:
    return OAuthClient(
        client_id="desktop-client.apps.googleusercontent.com",
        client_secret="gcp-client-secret",
        project_id="cadrumo-vault",
        auth_uri="https://accounts.google.com/o/oauth2/auth",
        token_uri="https://oauth2.googleapis.com/token",
        auth_provider_x509_cert_url="https://www.googleapis.com/oauth2/v1/certs",
        redirect_uris=("http://127.0.0.1:8765/callback",),
    )


def _seed() -> None:
    """Persist a complete, genuine login session through the real write path."""
    session_store.save_client(_PROFILE, _client())
    session_store.save_token(
        _PROFILE,
        OAuthToken(refresh_token="1//refresh-token", token_uri="https://oauth2.googleapis.com/token"),
    )
    session_store.save_metadata(
        _PROFILE,
        OAuthMetadata(
            account_email="operator@example.com",
            granted_scopes=REQUIRED_SCOPES,
            issued_at=_ISSUED_AT,
            last_refresh_at=_ISSUED_AT,
        ),
    )
    session_store.save_drive_config(_PROFILE, DriveConfig(root_folder_id="drive-folder-id"))


def test_a_clean_logout_clears_both_records_and_keeps_the_registration(tmp_path: Path) -> None:
    """The positive control, and the contract logout is meant to honour."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed()

        assert session_store.delete_session(_PROFILE) == (True, True)

        assert session_store.load_token(_PROFILE) is None
        assert session_store.load_metadata(_PROFILE) is None
        # Registration and Drive config are deliberately untouched, so a later
        # login reuses the Cloud Console JSON and the same root folder.
        assert session_store.load_client(_PROFILE) == _client()
        assert session_store.load_drive_config(_PROFILE) is not None


def test_logging_out_twice_reports_absence_rather_than_raising(tmp_path: Path) -> None:
    """The second call is a no-op that says so."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed()

        assert session_store.delete_session(_PROFILE) == (True, True)
        assert session_store.delete_session(_PROFILE) == (False, False)


def test_a_rejected_batch_removes_neither_row(tmp_path: Path) -> None:
    """The all-or-nothing property logout now depends on.

    The token deletion is acceptable and the second one is not, so a primitive
    that removed rows as it went would leave the token gone. The batch removes
    nothing.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed()
        repository = session_store._repository()
        digest = secure_object_key_digest(_PROFILE)

        with pytest.raises(StorageValidationError):
            repository.apply_batch(
                writes=(),
                deletions=(
                    SecureObjectDeletion(namespace=session_store._NAMESPACE_TOKEN, hashed_object_key=digest),
                    SecureObjectDeletion(namespace=_UNREGISTERED_NAMESPACE, hashed_object_key=digest),
                ),
            )

        assert session_store.load_token(_PROFILE) is not None
        assert session_store.load_metadata(_PROFILE) is not None


def test_the_sequential_deletes_it_replaced_would_have_removed_the_first(tmp_path: Path) -> None:
    """The discriminating half: the old shape fails the same case.

    Without this the assertion above could hold for a primitive that simply
    never removes anything. Issuing the same two removals as the separate
    commits ``delete_session`` used to make leaves the token gone and the
    metadata behind — exactly the split state the operator could not see or
    retry away.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _seed()
        repository = session_store._repository()

        removed_first = repository.delete(session_store._NAMESPACE_TOKEN, _PROFILE)
        with pytest.raises(StorageValidationError):
            repository.delete(_UNREGISTERED_NAMESPACE, _PROFILE)

        assert removed_first is True
        assert session_store.load_token(_PROFILE) is None
        assert session_store.load_metadata(_PROFILE) is not None
