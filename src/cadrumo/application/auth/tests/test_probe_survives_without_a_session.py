"""Application auth-probe policy tests with an explicit real composition seam.

The probe and scope capabilities remain inward fakes because these cases
exercise the application answer for an unbound session. The preflight service
is composed through the shared test seam with a real generation-pinned
authority operation and persistence projection read ports.
"""

from __future__ import annotations

import pytest

from cadrumo.application.auth.operator_probes import (
    _active_profile_path_values,
    live_auth_identity_state,
    probe_clave_credentials,
)
from cadrumo.application.auth.tests._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.core.auth_provider import AuthProviderKind
from cadrumo.core.config import override_settings

from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_projection_support import build_live_auth_preflight_report

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCKED_OPERATOR_PROBE_PORTS = fake_operator_probe_ports(active_profile_session_bound=False)
_CERTIFICATE_SECRET_BACKEND_FACTORY = InMemoryCertificateSecretBackendFactory()


def test_the_profile_read_is_declined_when_no_session_is_bound() -> None:
    """The guarantee itself: no session means no read is attempted."""

    assert _active_profile_path_values(operator_probe_ports=_LOCKED_OPERATOR_PROBE_PORTS) == {}


def test_the_credential_probe_reports_nothing_from_an_unread_profile() -> None:
    """A locked workstation reports no profile-borne credential."""

    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        credentials = probe_clave_credentials(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
            operator_probe_ports=_LOCKED_OPERATOR_PROBE_PORTS,
        )

    assert credentials is not None
    assert credentials.dni_nie == ""


def test_the_identity_state_probe_answers_without_a_session() -> None:
    """The alignment ladder reports a state rather than refusing."""

    with override_settings(cadrumo_clave_movil_dni_nie=None) as settings:
        profile_present, provider_present, alignment = live_auth_identity_state(
            AuthProviderKind.CLAVE_MOVIL,
            settings=settings,
            operator_probe_ports=_LOCKED_OPERATOR_PROBE_PORTS,
        )

    assert profile_present is False
    assert provider_present is False
    assert alignment


def test_the_preflight_report_builds_without_a_session() -> None:
    """An operator asks whether auth is ready before unlocking anything."""

    report = build_live_auth_preflight_report(
        AuthProviderKind.CLAVE_MOVIL.value,
        certificate_secret_backend_factory=_CERTIFICATE_SECRET_BACKEND_FACTORY,
        operator_probe_ports=_LOCKED_OPERATOR_PROBE_PORTS,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

    assert report.provider == AuthProviderKind.CLAVE_MOVIL.value
