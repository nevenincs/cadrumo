"""Cl@ve Móvil persisted-session metadata records.

:class:`adapters.outbound.aeat.auth.ClaveMovilAuthProvider` stores
:class:`ClaveMovilSessionMetadata` inside the encrypted
:class:`adapters.outbound.aeat.auth.session_store.PersistedBrowserSession`
metadata mapping. The record binds the Playwright storage state to the
operator identity, post-auth landing URL, verification code, and resume
deadline observed during the human-in-the-loop login flow.

Application callers later narrow this provider-owned shape to the common
:class:`application.auth.PersistedAuthSession` reuse contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from .....core.auth_provider import AuthProviderKind
from .....core.identity import ContentDigest
from .....core.models import STRICT_FROZEN_CONFIG

AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION: Final[int] = 2
"""Schema version for Cl@ve Móvil :class:`ClaveMovilSessionMetadata` records."""


class ClaveMovilSessionMetadata(BaseModel):
    """Provider-owned metadata stored with encrypted Cl@ve Móvil storage state.

    ``provider_kind`` keeps the encrypted object distinguishable from
    certificate-auth metadata. ``storage_state_sha256`` lets resume paths reject
    stale or mismatched browser state, while ``landing_url`` lets live probes
    verify an already-authenticated page without re-entering AEAT's Cl@ve
    selector. The same operational fields are projected into
    :class:`adapters.outbound.aeat.auth.ClaveMovilSessionDetail` when a
    session is rebuilt.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION, ge=2)
    provider_kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: ContentDigest
    used_non_qr_fallback: bool = False
    verification_code: str | None = None
    landing_url: str | None = Field(
        default=None,
        description=(
            "Concrete URL Playwright observed after AEAT dispatched the "
            "successful login. "
            "Used as the probe target by auth-session readiness checks because AEAT's "
            "Cl@ve selector page is a static dispatch page that always returns 200 "
            "regardless of auth state."
        ),
    )


__all__ = [
    "AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION",
    "ClaveMovilSessionMetadata",
]
