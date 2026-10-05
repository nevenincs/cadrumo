"""Profile-owned authentication intent, shared by configuration and live reads.

Core types: :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from ...core.auth_provider import DEFAULT_CLAVE_MOVIL_ROUTE, AuthProviderKind, ClaveMovilRoute
from ...domain.user_profile.values import UserProfileFact
from ..user_profile.capsule_record import ProfileRecordConflictError
from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from ..user_profile.profile_record_repository import ProfileRecordRepository
from ..user_profile.projections import record_to_effective_facts, record_to_path_values

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from ...domain.user_profile.values import UserProfileRecord


def profile_auth_provider(values: Mapping[str, str]) -> AuthProviderKind | None:
    """Resolve the declared preference without guessing an unknown stored token."""
    value = values.get("auth.provider", "").strip()
    return AuthProviderKind(value) if value else None


def set_profile_auth_preference(
    *,
    profile_id: str,
    provider: AuthProviderKind,
    route: ClaveMovilRoute | None,
    profile_decode_context: ProfileDecodeContext,
    expected_revision: int | None = None,
    expected_content_digest: str | None = None,
) -> tuple[UserProfileRecord, bool]:
    """Validate and publish method and route in one revision-bound fact command.

    Choosing Cl@ve Movil without a route records the default route when the
    profile never held one, so the profile shows the route that will be used.
    A route the operator chose, or deliberately cleared, is left as it is; a
    cleared route resolves to the same default at sign-in.
    """
    repository = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=profile_decode_context)
    current = repository.load(profile_id)
    if (expected_revision is None) != (expected_content_digest is None):
        raise ProfileRecordConflictError("auth edit requires a complete baseline")
    if expected_revision is not None and (
        current.record_revision != expected_revision or current.content_digest != expected_content_digest
    ):
        raise ProfileRecordConflictError("auth edit baseline is stale")
    changes = [UserProfileFact(path="auth.provider", value=provider.value)]
    if (
        route is None
        and provider is AuthProviderKind.CLAVE_MOVIL
        and "auth.clave_movil_route" not in record_to_effective_facts(current)
    ):
        route = DEFAULT_CLAVE_MOVIL_ROUTE
    if route is not None:
        changes.append(UserProfileFact(path="auth.clave_movil_route", value=route.value))
    applied = apply_profile_fact_changes(
        profile_id=profile_id,
        changes=tuple(changes),
        door=ProfileFactWriteDoor.AUTH_CONFIGURE,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )
    return applied, applied.record_revision != current.record_revision


def clear_profile_auth_preference(
    *,
    profile_id: str,
    providers: tuple[str, ...],
    profile_decode_context: ProfileDecodeContext,
) -> bool:
    """Clear only intent owned by the providers the auth reset actually targets."""
    repository = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=profile_decode_context)
    current = repository.load(profile_id)
    if record_to_path_values(current).get("auth.provider") not in providers:
        return False
    applied = apply_profile_fact_changes(
        profile_id=profile_id,
        changes=(UserProfileFact(path="auth.provider", value=None),),
        door=ProfileFactWriteDoor.AUTH_CONFIGURE,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )
    return applied.record_revision != current.record_revision
