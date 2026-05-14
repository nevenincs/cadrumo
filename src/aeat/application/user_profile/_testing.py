"""Test conveniences over the canonical user-profile orchestration.

Wraps :func:`register_active_profile` with a curated set of required
schema-validated placeholder facts so unit tests can register a profile
in one call without reciting six placeholder values every time.

This is a TEST helper and lives in the canonical package because it
composes only canonical surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...adapters.persistence.storage.sql import SecureObjectRepository
from ...domain.user_profile import ProfileAlreadyExistsError, UserProfileFact
from ..workflow._models import WorkflowState
from ._orchestration import register_active_profile, select_profile, set_active_fields

_REQUIRED_PLACEHOLDERS: Mapping[str, str] = {
    "identity.tax_id": "00000000T",
    "identity.name": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "provenance.source": "manual_cli",
}


def register_minimal_profile(
    state: WorkflowState,
    *,
    profile_id: str,
    display_name: str | None = None,
    overrides: Mapping[str, str] | None = None,
    secure_objects: SecureObjectRepository | None = None,
) -> WorkflowState:
    """Register ``profile_id`` with the minimum required schema facts.

    Args:
        state: Current :class:`WorkflowState`.
        profile_id: Canonical profile identifier (also the bucket id).
        display_name: Operator-visible label. Defaults to ``profile_id``.
        overrides: Optional schema-path → string overrides applied on top
            of the placeholder facts (also accepts paths not in the
            required set; they merge in).
        secure_objects: Optional injected secure-object repository.

    Returns:
        The state with the profile registered + activated and the
        ``profile.created`` / ``profile.selected`` workflow events
        appended.
    """

    merged: dict[str, str] = dict(_REQUIRED_PLACEHOLDERS)
    if overrides:
        merged.update(overrides)
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in merged.items() if value)
    try:
        return register_active_profile(
            state,
            profile_id=profile_id,
            display_name=display_name or profile_id,
            facts=facts,
            secure_objects=secure_objects,
        )
    except ProfileAlreadyExistsError:
        selected = select_profile(state, profile_id=profile_id, secure_objects=secure_objects)
        return set_active_fields(selected, facts, secure_objects=secure_objects)


__all__ = ["register_minimal_profile"]
