"""Canonical exact-profile language reads and registered preference writes."""

from dataclasses import dataclass

from cadrumo.application.user_profile.profile_operation_contracts import ProfileFieldMutationOperationRequest
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.identity.digest import ContentDigest
from cadrumo.domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH

from .frontend_client import FrontendClient
from .operation_settlement import PinnedConnection
from .profile_mutations import run_profile_mutation


@dataclass(frozen=True, slots=True)
class ProfileLanguage:
    """Language and concurrency witness from one authenticated canonical view."""

    language: OutputLanguage | None
    record_revision: int
    content_digest: ContentDigest


def read_profile_language(client: FrontendClient) -> ProfileLanguage:
    """Read the encrypted preference through the registered exact-profile view."""
    pinned = PinnedConnection.of(client)
    viewed = client.read_profile_view((ProfileViewPageKind.FACTS,))
    pinned.require_held(client)
    language = next(
        (
            OutputLanguage(item.value)
            for item in viewed.items(ProfileViewPageKind.FACTS)
            if isinstance(item, ProfileViewFactItem) and item.path == PROFILE_OUTPUT_LANGUAGE_PATH
        ),
        None,
    )
    return ProfileLanguage(language, viewed.record_revision, viewed.content_digest)


def set_profile_language(client: FrontendClient, language: OutputLanguage) -> ProfileLanguage:
    """Set only the language through the existing guarded CAS fact operation."""
    pinned = PinnedConnection.of(client)
    current = read_profile_language(client)
    pinned.require_held(client)
    run_profile_mutation(
        client,
        ProfileFieldMutationOperationRequest(
            profile_id=client.profile_id,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            path=PROFILE_OUTPUT_LANGUAGE_PATH,
            value=language.value,
        ),
    )
    pinned.require_held(client)
    return read_profile_language(client)
