"""Unit tests for provider-agnostic auth helpers."""

from __future__ import annotations

import pytest

from ......core.auth_provider import AuthProviderDescription, AuthProviderKind
from ......core.i18n import describe_auth_provider_operator_impact

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _description(
    *,
    configured: bool,
    available: bool,
    kind: AuthProviderKind = AuthProviderKind.CERTIFICATE,
) -> AuthProviderDescription:
    return AuthProviderDescription(
        kind=kind,
        label="AEAT certificate" if kind is AuthProviderKind.CERTIFICATE else "Cl@ve Móvil",
        configured=configured,
        available=available,
        identity_nif="X1234567L" if available else None,
        subject="CN=operator" if available else None,
        health_severity="OK" if available else None,
        health_summary="OK:200" if available else "credential not loaded",
    )


def test_operator_impact_returns_a_non_empty_string_for_every_branch() -> None:
    for description in (
        _description(configured=False, available=False),
        _description(configured=True, available=False),
        _description(configured=True, available=True, kind=AuthProviderKind.CERTIFICATE),
        _description(configured=True, available=True, kind=AuthProviderKind.CLAVE_MOVIL),
    ):
        message = describe_auth_provider_operator_impact(description)
        assert message
        assert message.strip() == message


def test_operator_impact_distinguishes_every_branch() -> None:
    """Each (configured, available, kind) combination must produce a unique message."""
    branches = {
        describe_auth_provider_operator_impact(_description(configured=False, available=False)),
        describe_auth_provider_operator_impact(_description(configured=True, available=False)),
        describe_auth_provider_operator_impact(
            _description(configured=True, available=True, kind=AuthProviderKind.CERTIFICATE),
        ),
        describe_auth_provider_operator_impact(
            _description(configured=True, available=True, kind=AuthProviderKind.CLAVE_MOVIL),
        ),
    }
    assert len(branches) == 4


def test_operator_impact_is_deterministic() -> None:
    description = _description(configured=True, available=True)
    assert describe_auth_provider_operator_impact(description) == describe_auth_provider_operator_impact(description)
