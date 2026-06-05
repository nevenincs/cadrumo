"""Persisted Cl@ve Móvil session metadata records."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from ._providers import AuthProviderKind

AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION: Final[int] = 2
"""Distinct from certificate metadata v1 so stale certificate objects are rejected."""


class ClaveMovilSessionMetadata(BaseModel):
    """Encrypted metadata stored with the Cl@ve Móvil storage state."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: int = Field(default=AEAT_CLAVE_MOVIL_METADATA_SCHEMA_VERSION, ge=2)
    provider_kind: AuthProviderKind = AuthProviderKind.CLAVE_MOVIL
    identity_nif: str = Field(min_length=1)
    authenticated_at: datetime
    idle_deadline: datetime
    storage_state_sha256: str = Field(min_length=64, max_length=64)
    used_non_qr_fallback: bool = False
    verification_code: str | None = None
    landing_url: str | None = Field(
        default=None,
        description=(
            "Concrete URL Playwright observed after AEAT dispatched the "
            "successful login. "
            "Used as the probe target by auth-session readiness checks because AEAT's "
            "the Cl@ve selector page is a static dispatch page that always "
            "returns 200 regardless of auth state."
        ),
    )
