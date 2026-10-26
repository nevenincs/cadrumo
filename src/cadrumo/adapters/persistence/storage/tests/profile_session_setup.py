"""Release local fixture custody and reset its selected profile."""

from __future__ import annotations

from .....application.user_profile.language_resolver import refresh_active_profile_output_language
from .....application.user_profile.profile_pointer import active_profile_pointer_transaction
from .....application.user_profile.profile_record_repository import close_active_profile_record_session
from ..master_key.active_session import close_active_bucket_session


def reset_test_profile_session() -> None:
    """Reset isolated test state without touching a runtime-owned sign-in."""
    close_active_bucket_session()
    close_active_profile_record_session()
    with active_profile_pointer_transaction() as pointer:
        pointer.clear()
    refresh_active_profile_output_language()
