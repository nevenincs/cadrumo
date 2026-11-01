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
from ....adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    profile_authority_contexts,
)
from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.login_session import authenticate_profile_for_invocation
from ....application.user_profile.overview import ProfileOverview, build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....core.bucket_pointer import require_active_bucket_id
from ....domain.calculations.registry.authority import bundled_indexed_authority

__all__ = [
    "manager_subject_logged_in",
    "manager_subject_overview",
    "manager_subject_stored_facts",
    "manager_subject_world",
    "publish_manager_subject_session",
    "registered_manager_subject",
    "write_manager_subject_field",
]


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


def manager_subject_logged_in(*, label: str, passphrase: str) -> None:
    """Unlock the registered subject so the capsule will serve its record.

    Registration closes its own session and the custody capsule is the sole
    profile authority, so every read or write door needs an authenticated
    session. Logging in derives the same DEK the capsule was sealed under.
    """
    authenticate_profile_for_invocation(
        name=label,
        passphrase_callback=lambda: passphrase,
        profile_decode_context=profile_authority_contexts()[1],
    )


def manager_subject_overview(*, label: str, passphrase: str) -> ProfileOverview:
    """Build the subject's overview from the stored record, under a lease taken on the calling thread."""
    with bundled_indexed_authority().operation():
        manager_subject_logged_in(label=label, passphrase=passphrase)
        record = load_test_profile_record(require_active_bucket_id())
        return build_profile_overview(record, label=label, schema=profile_authority_contexts()[1].schema)


def write_manager_subject_field(
    *,
    label: str,
    passphrase: str,
    path: str,
    value: str,
    expected_revision: int | None = None,
    expected_content_digest: str | None = None,
) -> ProfileOverview:
    """Write one field through the production door, so an edit travels the real path."""
    with bundled_indexed_authority().operation():
        manager_subject_logged_in(label=label, passphrase=passphrase)
        record = apply_manager_profile_field_mutation(
            profile_id=require_active_bucket_id(),
            path=path,
            value=value,
            expected_revision=expected_revision,
            expected_content_digest=expected_content_digest,
            profile_decode_context=profile_authority_contexts()[1],
        )
        return build_profile_overview(record, label=label, schema=profile_authority_contexts()[1].schema)


def manager_subject_stored_facts(*, label: str, passphrase: str) -> dict[str, object | None]:
    """Return every stored fact of the subject keyed by path."""
    manager_subject_logged_in(label=label, passphrase=passphrase)
    reloaded = load_test_profile_record(require_active_bucket_id())
    return {fact.path: fact.value for fact in reloaded.facts}
