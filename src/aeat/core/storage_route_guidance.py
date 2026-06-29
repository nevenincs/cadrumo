"""Operator-facing guidance for storage route refusals."""

from __future__ import annotations

EXPLICIT_DATABASE_URL_PROFILE_RECOVERY = (
    "Unset AEAT_DATABASE_URL before profile setup or profile-bound writes; "
    "use AEAT_LOCAL_STORAGE_ROOT to choose the local storage root, then create "
    "or switch the profile so AEAT can derive the active bucket database."
)

__all__ = ["EXPLICIT_DATABASE_URL_PROFILE_RECOVERY"]
