"""Unit tests for provider-agnostic auth helpers."""

from __future__ import annotations

import pytest

from .....application.auth import (
    AuthProviderDescription,
    AuthProviderKind,
    describe_provider_operator_impact,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def test_operator_impact_explains_local_fallback_when_unconfigured() -> None:
    description = AuthProviderDescription(
        kind=AuthProviderKind.CERTIFICATE,
        label="AEAT certificate",
        configured=False,
        available=False,
        health_summary="certificate path not configured",
    )

    message = describe_provider_operator_impact(description)

    assert "produce, verify, and export" in message
    assert "unavailable until an auth provider is configured" in message


def test_operator_impact_explains_protocol_value_for_ready_certificate() -> None:
    description = AuthProviderDescription(
        kind=AuthProviderKind.CERTIFICATE,
        label="AEAT certificate",
        configured=True,
        available=True,
        identity_nif="X1234567L",
        subject="CN=Kent",
        health_severity="OK",
        health_summary="OK:200",
    )

    message = describe_provider_operator_impact(description)

    assert "same CLI filing flow" in message
    assert "future providers can plug into the same commands" in message
