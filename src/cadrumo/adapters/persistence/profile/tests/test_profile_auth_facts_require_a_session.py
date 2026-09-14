"""The active profile's Cl@ve facts are readable only under its own session.

The profile record is encrypted under the profile's own DEK, and that key
exists only inside the session its password envelope unwrapped.  This reader
used to reach for the shared-master provider whenever no per-profile session
was live, which opened a bucket with no password at all -- a second custody
lifecycle answering for a taxpayer's profile beside the capsule that owns it.

Proving the branch is gone needs the record to be genuinely readable, because
an assertion that sealed facts come back empty passes just as well when nothing
was ever written.  Each test below therefore seeds ONE record and reads it
twice, varying only whether a session serves it; the unlocked read is what
makes the sealed read mean something.

The branch was also broken where it was reached.  A capsule-published bucket
carries no shared-master manifest, so resolving the provider against one raises
``MasterKeyMaterialMissingError`` -- which the reader's ``ProfileNotFoundError``
handler does not catch, so it propagated out of a function documented to
degrade quietly to the settings surface.  The sealed read below is therefore
also the regression test for that escape: an exception reaching the caller
fails these assertions exactly as a leaked credential would.
"""

from __future__ import annotations

import pytest

from cadrumo.core.auth_provider import ClaveMovilRoute
from cadrumo.core.config import override_settings
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.profile_storage_root_fixture import isolated_profile_storage_fixture
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.application.auth.sessions import ClaveAuthFacts, clave_auth_facts_from_profile_values
from cadrumo.application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    profile_record_session_if_authenticated,
)
from cadrumo.application.user_profile.projections import record_to_path_values
from cadrumo.core.bucket_pointer import resolve_active_bucket_id
from cadrumo.domain.user_profile.errors import ProfileNotFoundError

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "3f3f3f3f-3f3f-4f3f-8f3f-3f3f3f3f3f3f"
_OTHER_BUCKET_ID = "4a4a4a4a-4a4a-4a4a-8a4a-4a4a4a4a4a4a"
_PROFILE_LABEL = "session-bound-operator"
_TAX_ID = "12345678Z"
_SOPORTE = "E12345678"

#: Isolate the storage root without opening any session.
_isolated_storage = isolated_profile_storage_fixture()


def _read_active_profile_auth_facts() -> ClaveAuthFacts:
    """Read profile auth facts through public session-bound application doors."""
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return ClaveAuthFacts()
    session = profile_record_session_if_authenticated(bucket_id)
    if session is None:
        return ClaveAuthFacts()
    try:
        record = ProfileRecordRepository(session=session).load(bucket_id)
    except ProfileNotFoundError:
        return ClaveAuthFacts()
    return clave_auth_facts_from_profile_values(
        record_to_path_values(record),
        profile_setup_state=record.setup_state,
    )


def _seed_profile(bucket_id: str = _BUCKET_ID, *, label: str = _PROFILE_LABEL) -> None:
    """Write one real encrypted profile record carrying Cl@ve credentials."""
    with open_test_profile_session(bucket_id):
        register_minimal_profile(
            profile_id=bucket_id,
            display_name=label,
            overrides={
                "identity.tax_id": _TAX_ID,
                "auth.dni_nie": _TAX_ID,
                "auth.numero_soporte": _SOPORTE,
                "auth.clave_movil_route": ClaveMovilRoute.QR.value,
            },
        )


def test_the_same_record_reads_under_its_session_and_stays_sealed_without_one() -> None:
    """One record, two reads; the session is the only thing that differs.

    The unlocked read is the anti-tautology half: it proves the record exists
    and carries the credentials, so the sealed read returning empty facts can
    only be the missing session rather than missing data.
    """
    _seed_profile()

    with open_test_profile_session(_BUCKET_ID), override_settings(cadrumo_active_profile=_BUCKET_ID):
        unlocked = _read_active_profile_auth_facts()

    with override_settings(cadrumo_active_profile=_BUCKET_ID):
        sealed = _read_active_profile_auth_facts()

    assert unlocked.tax_id == _TAX_ID
    assert unlocked.dni_nie == _TAX_ID
    assert unlocked.numero_soporte == _SOPORTE
    assert unlocked.clave_movil_route is ClaveMovilRoute.QR

    assert sealed == ClaveAuthFacts()


def test_a_session_bound_to_another_profile_does_not_unseal_this_one() -> None:
    """A foreign session is not a key to this record.

    Without this the reader could satisfy its own guard with whatever session
    happens to be bound and decrypt under the wrong profile's DEK.
    """
    _seed_profile()
    _seed_profile(_OTHER_BUCKET_ID, label="other-operator")

    with open_test_profile_session(_OTHER_BUCKET_ID), override_settings(cadrumo_active_profile=_BUCKET_ID):
        facts = _read_active_profile_auth_facts()

    assert facts == ClaveAuthFacts()
