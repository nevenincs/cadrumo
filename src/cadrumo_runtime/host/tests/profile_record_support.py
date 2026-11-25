"""Read a served profile's view facts and its stored encrypted record for the profile mutation tests."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    load_test_profile_record,
    profile_authority_contexts,
)
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.domain.user_profile.values import UserProfileRecord
from cadrumo_client.transport.frontend_client import FrontendClient

from ...adapters.tests.profile_worker_support import PROFILE_INPUT


def profile_view_facts(client: FrontendClient) -> tuple[int, str, dict[str, str]]:
    """Read the facts page and return its record revision, content digest and fact values by path."""
    page = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=90)
    items = page.items(ProfileViewPageKind.FACTS)
    assert all(isinstance(item, ProfileViewFactItem) for item in items)
    facts = {item.path: item.value for item in items if isinstance(item, ProfileViewFactItem)}
    assert len(facts) == len(items)
    return page.record_revision, page.content_digest, facts


def stored_profile_record(profile_id: UUID, *, root: Path) -> UserProfileRecord:
    """Read the real encrypted record, then release process-local custody."""
    _, decode = profile_authority_contexts()
    authenticate_profile_for_invocation(
        name=str(profile_id), passphrase_callback=lambda: PROFILE_INPUT, profile_decode_context=decode
    )
    try:
        return load_test_profile_record(profile_id, root=root)
    finally:
        close_active_bucket_session()
