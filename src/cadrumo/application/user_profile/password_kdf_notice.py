"""Tell the person when their profile's password protection sits at the fixed minimum.

Enrolment calibration adopts the fixed fallback key-derivation point whenever
it cannot confirm a stronger one on a busy host. The profile stays protected at
that floor until its password envelope is re-minted. Changing the password
re-calibrates on purpose, and re-entering the same password is accepted, so the
existing password-change door is the strengthening path this notice points to.

The read touches only the committed envelope's non-secret parameters.
"""

from __future__ import annotations

from uuid import UUID

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ..operator_actions.catalogue import next_action
from .custody_ports import profile_custody_password_kdf_at_fallback

PROFILE_KDF_AT_FALLBACK_NOTICE_CODE = "profile.custody.kdf_at_fallback"
PROFILE_KDF_STRENGTHEN_ACTION_ID = "operator.profile.passphrase.change"
_PROFILE_KDF_AT_FALLBACK_LOCALE_KEY = "application.user_profile.notices.kdf_at_fallback"


def profile_kdf_floor_notice(profile_id: UUID) -> Notice | None:
    """Return the warning for a password envelope at the fixed fallback point, else ``None``."""
    if not profile_custody_password_kdf_at_fallback(profile_id):
        return None
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=PROFILE_KDF_AT_FALLBACK_NOTICE_CODE,
        message=tr(_PROFILE_KDF_AT_FALLBACK_LOCALE_KEY),
        action=next_action(PROFILE_KDF_STRENGTHEN_ACTION_ID),
    )


__all__ = [
    "PROFILE_KDF_AT_FALLBACK_NOTICE_CODE",
    "PROFILE_KDF_STRENGTHEN_ACTION_ID",
    "profile_kdf_floor_notice",
]
