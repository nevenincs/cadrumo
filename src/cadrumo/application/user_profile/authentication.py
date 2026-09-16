"""Non-oracular application outcome for existing profile-password proofs."""

from __future__ import annotations

from enum import StrEnum

from ...core.errors.hierarchy import CadrumoError


class ProfilePasswordProofOperation(StrEnum):
    """Existing-credential capabilities that deliberately share one public refusal."""

    LOGIN = "login"
    RESTORE = "password_restore"
    RECOVERY_ENROLL = "recovery_enroll"
    RECOVERY_REVOKE = "recovery_revoke"
    RECOVERY_RESET = "recovery_reset"
    ROTATION = "password_rotation"


class ProfileAuthenticationRefusedError(CadrumoError):
    """Refuse an existing-password proof without revealing shape or measurements."""

    def __init__(self) -> None:
        """Construct the single secret-free public authentication outcome."""
        super().__init__(translated_message="application.user_profile.errors.profile_authentication_refused")


__all__ = ["ProfileAuthenticationRefusedError", "ProfilePasswordProofOperation"]
