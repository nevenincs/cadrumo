"""Secret-free, exact-profile instructions for the person's AEAT setup."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from cadrumo_client.contracts.navigation import view_link

from ...core.auth_provider import AuthProviderKind
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .sync_readiness import AuthSyncReadiness
from .sync_requirement_text import sync_requirement_reason


class AuthSetupRequirement(BaseModel):
    """One missing prerequisite, explained without disclosing its value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    field: str
    explanation: str
    secret: bool


class AuthSetupHandoff(BaseModel):
    """A navigation offer, never permission to configure credentials."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["aeat_authentication"] = "aeat_authentication"
    url: str
    documentation_path: Literal["how-to/authenticate-with-aeat"] = "how-to/authenticate-with-aeat"
    supported_methods: tuple[AuthProviderKind, ...]
    missing: tuple[AuthSetupRequirement, ...]
    resume_definition: Literal["auth.local-read"] = "auth.local-read"
    resume_kind: Literal["setup"] = "setup"


def auth_setup_handoff(readiness: AuthSyncReadiness) -> AuthSetupHandoff:
    """Build a bounded handoff from the saved method's actual requirements."""
    return AuthSetupHandoff(
        url=view_link("profile/aeat-access"),
        supported_methods=tuple(AuthProviderKind),
        missing=tuple(
            AuthSetupRequirement(field=item.field, explanation=sync_requirement_reason(item.reason), secret=item.secret)
            for item in readiness.requirements
            if not item.satisfied
        ),
    )
