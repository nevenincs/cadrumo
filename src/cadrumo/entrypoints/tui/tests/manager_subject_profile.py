"""The registered subject profile the profile-manager screen tests open.

Each label and passphrase is registered once through the production door, and
every test receives its own copy of that settled profile with its session
published, as registration leaves it. A test whose subject is registration
itself calls the door directly instead.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from ....adapters.persistence.profile.tests.sealed_profile_world import (
    SealedProfileWorld,
    copied_profile_world,
    publish_world_session,
    sealed_profile_world,
)
from ....adapters.persistence.storage.tests.profile_capsule_runtime import profile_authority_contexts
from ....application.user_profile.registration import register_profile_with_credentials
from ....domain.calculations.registry.authority import bundled_indexed_authority

__all__ = ["manager_subject_world", "publish_manager_subject_session", "registered_manager_subject"]


def manager_subject_world(*, label: str, passphrase: str) -> SealedProfileWorld:
    """Return the settled world holding the subject registered under ``label`` and ``passphrase``."""

    def register() -> str:
        # Registration validates facts against registry authority, so it runs under a real lease.
        with bundled_indexed_authority().operation():
            create_context, decode_context = profile_authority_contexts()
            return register_profile_with_credentials(
                label=label,
                passphrase=passphrase,
                profile_create_context=create_context,
                profile_decode_context=decode_context,
            ).profile_id

    return sealed_profile_world(("tui manager subject", label, passphrase), register)


@contextmanager
def registered_manager_subject(tmp_path: Path, *, label: str, passphrase: str) -> Generator[None]:
    """Open this test's own copy of the subject, signed in and not yet set up; the session ends with the scope."""
    world = manager_subject_world(label=label, passphrase=passphrase)
    with copied_profile_world(world, tmp_path, profile_decode_context=profile_authority_contexts()[1]):
        yield


def publish_manager_subject_session(*, label: str, passphrase: str) -> None:
    """Publish the subject's session again in the caller's authority lease, as a login would."""
    publish_world_session(
        manager_subject_world(label=label, passphrase=passphrase),
        profile_decode_context=profile_authority_contexts()[1],
    )
