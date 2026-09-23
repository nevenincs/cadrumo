"""A sealed bucket session grants no profile record material.

Logout seals the live session in place: it keeps naming its bucket while its
key is zeroised. Reproduction: in a process that had logged out, ``config
profile status`` read the sealed session's key and failed with a locked-bucket
error (exit 7) instead of the not-logged-in refusal a fresh process gives.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from .....application.user_profile.custody_ports import profile_custody_record_session_material
from .....core.config import override_settings
from .....core.paths import effective_storage_root
from ..custody.errors import ProfileCustodyRecordError
from ..master_key.active_session import activate_session
from ..master_key.bucket_session import BucketSession
from .profile_capsule_runtime import derive_test_bucket_key

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]


def _open_session(identity: str) -> BucketSession:
    opened_at = datetime.now(UTC)
    return BucketSession.open_resumed(
        bucket_id=identity,
        dek=derive_test_bucket_key(identity, purpose="dek"),
        idle_minutes=15,
        opened_at=opened_at,
        idle_deadline=opened_at + timedelta(minutes=15),
        absolute_deadline=opened_at + timedelta(minutes=240),
        storage_root=effective_storage_root(),
    )


def test_a_sealed_session_is_no_session() -> None:
    profile_id = uuid4()
    session = _open_session(str(profile_id))
    with override_settings(cadrumo_active_profile=str(profile_id)), activate_session(session):
        session.close()
        assert session.sealed
        assert profile_custody_record_session_material(profile_id) is None


def test_a_live_session_goes_on_to_read_the_custody_material() -> None:
    """Teeth: the absence above comes from the seal, not from an unrelated early return.

    The same unsealed session proceeds to read the profile's committed custody
    material; this profile has none, so that read refuses.
    """
    profile_id = uuid4()
    session = _open_session(str(profile_id))
    with override_settings(cadrumo_active_profile=str(profile_id)), activate_session(session):
        try:
            with pytest.raises(ProfileCustodyRecordError):
                profile_custody_record_session_material(profile_id)
        finally:
            session.close()
