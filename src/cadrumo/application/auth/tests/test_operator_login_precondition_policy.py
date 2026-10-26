"""Inward auth login-precondition policy tests.

The profile-backed credential resolution and readiness integration tests live
with the persistence adapter.  These cases keep the local precondition policy
inward and inject the already-resolved application credential as a fake.
"""

from __future__ import annotations

import pytest

from cadrumo.application.auth import operator
from cadrumo.application.auth.sessions import ClaveCredentials
from cadrumo.application.auth.tests._operator_probe_fakes import fake_operator_probe_ports
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import override_settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TAX_ID = "12345678Z"
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports()


def test_login_precondition_admits_a_resolved_profile_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The local login gate admits a credential resolved from the profile seam."""

    def _resolved_profile_credential(
        provider_kind: AuthProviderKind,
        *,
        settings: object,
        operator_probe_ports: object,
    ) -> ClaveCredentials:
        del settings, operator_probe_ports
        return ClaveCredentials(provider_kind=provider_kind, dni_nie=_TAX_ID)

    monkeypatch.setattr(operator, "probe_clave_credentials", _resolved_profile_credential)
    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        operator._assert_login_precondition(
            settings,
            AuthProviderKind.CLAVE_MOVIL,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
        )


def test_login_precondition_still_refuses_when_no_credential_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The precondition still refuses when the credential capability is empty."""
    from cadrumo.application.auth.operator_results import AuthLoginPreconditionError

    def _no_credential(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(operator, "probe_clave_credentials", _no_credential)
    with (
        override_settings(cadrumo_clave_movil_dni_nie=None) as settings,
        pytest.raises(AuthLoginPreconditionError) as raised,
    ):
        operator._assert_login_precondition(
            settings,
            AuthProviderKind.CLAVE_MOVIL,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
        )

    assert raised.value.translated_message == "application.auth.operator.login.refused_clave_movil_identity_unset"
