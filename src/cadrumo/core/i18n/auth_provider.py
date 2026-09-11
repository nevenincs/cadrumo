"""Localized operator-impact rendering for AEAT auth providers."""

from __future__ import annotations

from ..auth_provider import AuthProviderDescription, AuthProviderKind
from .render import tr


def describe_auth_provider_operator_impact(description: AuthProviderDescription) -> str:
    """Return the canonical localized operator impact for ``description``."""
    if not description.configured:
        return tr("application.auth.provider_impact.unconfigured")
    if not description.available:
        return tr("application.auth.provider_impact.unavailable", label=description.label)
    if description.kind is AuthProviderKind.CERTIFICATE:
        return tr("application.auth.provider_impact.certificate_ready")
    return tr("application.auth.provider_impact.generic_ready", label=description.label)


__all__ = ["describe_auth_provider_operator_impact"]
