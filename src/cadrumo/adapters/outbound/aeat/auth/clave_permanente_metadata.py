"""Cl@ve Permanente persisted-session metadata records.

:class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider` stores
:class:`~adapters.outbound.aeat.auth.clave_permanente_metadata.ClavePermanenteSessionMetadata`
inside the encrypted
:class:`~adapters.outbound.aeat.auth.session_store.PersistedBrowserSession`
metadata mapping. The record binds the Playwright storage state to the operator
identity, post-auth landing URL, and resume deadline observed during the
headless DNI/NIE + password login flow.

Application callers later narrow this provider-owned shape to the common
:class:`~application.auth.PersistedAuthSession` reuse contract.

See Also:
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteAuthProvider`
        Provider that writes and reloads this metadata beside browser state.
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail`
        Public session detail projected from this encrypted metadata record.
    :class:`~adapters.outbound.aeat.auth.session_store.PersistedBrowserSession`
        Encrypted browser-session envelope whose metadata mapping stores this
        provider-owned record.
    :class:`~application.auth.PersistedAuthSession`
        Application reuse contract that receives the narrowed provider detail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, Field

from .....core import AuthProviderKind
from .....core.identity import ContentDigest
from .....core.models import STRICT_FROZEN_CONFIG

AEAT_CLAVE_PERMANENTE_METADATA_SCHEMA_VERSION: Final[int] = 1
"""Schema version for Cl@ve Permanente metadata records."""


class ClavePermanenteSessionMetadata(BaseModel):
    """Provider-owned metadata stored with encrypted Cl@ve Permanente storage state.

    ``provider_kind`` keeps the encrypted object distinguishable from
    certificate and Cl@ve Móvil metadata. ``storage_state_sha256`` lets resume
    paths reject stale or mismatched browser state, while ``landing_url`` lets
    live probes verify an already-authenticated page without re-entering
    AEAT's Cl@ve selector. The same operational fields are projected into
    :class:`~adapters.outbound.aeat.auth.ClavePermanenteSessionDetail` when
    a session is rebuilt. Unlike Cl@ve Móvil, no verification code or
    non-QR-fallback flag applies — the login form carries no phone-approval
    state.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: int = Field(default=AEAT_CLAVE_PERMANENTE_METADATA_SCHEMA_VERSION, ge=1)
    provider_kind: AuthProviderKind = AuthProviderKind.CLAVE_PERMANENTE
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: ContentDigest
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
    "AEAT_CLAVE_PERMANENTE_METADATA_SCHEMA_VERSION",
    "ClavePermanenteSessionMetadata",
]
