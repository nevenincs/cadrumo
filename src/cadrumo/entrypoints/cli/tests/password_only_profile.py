"""Register one password-only profile for CLI integration suites.

Several CLI suites — the machine-secret channel transports here, and the
scripted ``config profile create`` suite below ``config`` — need a real
encrypted profile on disk before the verb under test runs. They share this
one registration so the fixture passphrase and the pinned authority operation
have a single home.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.user_profile.registration import ProfileRegistrationOutcome, register_profile_with_credentials
from ....core.config import override_settings

#: The synthetic passphrase every password-only fixture profile is created
#: with. It is test scaffolding and must never appear in captured output.
FIXTURE_PROFILE_INPUT: Final = "s13-profile-passphrase-that-must-never-escape"


def register_password_only_profile(
    storage_root: Path,
    *,
    label: str = "s13-operator",
    passphrase: str = FIXTURE_PROFILE_INPUT,
) -> ProfileRegistrationOutcome:
    """Register one password-only profile and close its session, as the CLI would.

    Registration validates facts against governed registry vocabularies, which
    resolve only inside a pinned authority operation. The CLI holds one for the
    whole invocation; registering outside one raised before any subprocess ran.
    """
    from ....domain.calculations.registry.authority import bundled_indexed_authority

    with (
        override_settings(cadrumo_local_storage_root=storage_root),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label=label,
            passphrase=passphrase,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        close_active_bucket_session()
    return outcome


__all__ = [
    "FIXTURE_PROFILE_INPUT",
    "register_password_only_profile",
]
