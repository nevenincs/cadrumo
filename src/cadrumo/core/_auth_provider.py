"""Layer-neutral AEAT authentication provider contracts.

The closed provider kind and provider-readiness description are shared by
configuration, application services, domain preflight, and outbound adapters.
Keeping both contracts in core gives every layer one typed authority without
an application-layer import or a duplicate settings-only enumeration.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from .models import STRICT_FROZEN_CONFIG


class AuthProviderKind(StrEnum):
    """Closed enumeration of supported AEAT authentication providers."""

    CERTIFICATE = "certificate"
    CLAVE_MOVIL = "clave_movil"
    CLAVE_PERMANENTE = "clave_permanente"


class ClaveMovilRoute(StrEnum):
    """Operator-selectable Cl@ve Movil interaction route."""

    QR = "qr"
    APP_REQUEST = "app_request"


class AuthProviderDescription(BaseModel):
    """Safe operator-facing readiness description for one auth provider."""

    model_config = STRICT_FROZEN_CONFIG

    kind: AuthProviderKind
    label: str = Field(min_length=1)
    configured: bool
    available: bool
    identity_nif: str | None = None
    subject: str | None = None
    expires_on: date | None = None
    health_severity: str | None = None
    days_until_expiry: int | None = None
    health_summary: str | None = None


__all__ = ["AuthProviderDescription", "AuthProviderKind", "ClaveMovilRoute"]
