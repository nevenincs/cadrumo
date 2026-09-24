"""Auth preflight and ``auth test`` answers against the persistence projection seam.

The probe and scope capabilities stay inward fakes; the preflight and ``auth
test`` services are composed with a real generation-pinned authority operation
and the persistence-backed state projection read ports.
"""

from __future__ import annotations

import pytest

from .....application.auth.operator_results import AuthOperationRequiresCustodySessionError
from .....application.auth.operator_scope_ports import OperatorScopeSession
from .....application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from .....core.auth_provider import AuthProviderKind
from .....core.config import load_settings, override_settings
from .operator_probe_fakes import fake_operator_probe_ports
from .operator_projection_test_support import build_live_auth_preflight_report
from .operator_projection_test_support import test_operator_auth as run_operator_auth_test
from .operator_scope_fakes import build_inward_operator_scope_ports, build_inward_operator_scope_ports_for_active_route

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]

_BUCKET_A = "6a6a6a6a-6a6a-4a6a-8a6a-6a6a6a6a6a6a"
_BUCKET_B = "6b6b6b6b-6b6b-4b6b-8b6b-6b6b6b6b6b6b"
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports(active_profile_session_bound=False)
_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports(
    session=OperatorScopeSession(
        bucket_id=_BUCKET_A,
        storage_root=load_settings().cadrumo_local_storage_root,
    ),
)
_NO_SESSION_PORTS = build_inward_operator_scope_ports(session=None)


def test_the_preflight_report_builds_without_a_session() -> None:
    """An operator asks whether auth is ready before unlocking anything."""

    report = build_live_auth_preflight_report(
        AuthProviderKind.CLAVE_MOVIL.value,
        certificate_secret_backend_factory=InMemoryCertificateSecretBackendFactory(),
        operator_probe_ports=_OPERATOR_PROBE_PORTS,
        operator_scope_ports=build_inward_operator_scope_ports_for_active_route(),
    )

    assert report.provider == AuthProviderKind.CLAVE_MOVIL.value


def test_operator_auth_test_surfaces_the_refusal_for_an_unbound_explicit_target() -> None:
    """``auth test`` on an explicit unbound profile refuses rather than reporting on A.

    The alternative -- probing whichever profile happens to be bound -- would
    report another taxpayer's certificate readiness under the requested
    profile's name.
    """
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    with pytest.raises(AuthOperationRequiresCustodySessionError):
        run_operator_auth_test(
            AuthProviderKind.CERTIFICATE.value,
            settings=settings_b,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )


def test_live_auth_preflight_answers_not_ready_when_no_session_is_open_at_all() -> None:
    """The locked workstation: nothing is unlocked, so the report answers rather than refuses.

    This is the other arm of the same narrowing, and it is pinned here beside
    the refusal so neither can be widened into the other. The operator asks
    whether auth is ready BEFORE unlocking anything; a readiness probe that
    declines to answer precisely then has no remaining purpose, and the doctor
    that consumes it emitted an error document instead of a payload when this
    last broke. Every field of the report defaults to empty or false because
    the type exists to carry exactly this degraded answer.
    """
    with override_settings(cadrumo_active_profile=_BUCKET_A):
        assert _NO_SESSION_PORTS.session.current() is None
        report = build_live_auth_preflight_report(
            AuthProviderKind.CERTIFICATE.value,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_NO_SESSION_PORTS,
        )

        assert report.provider == AuthProviderKind.CERTIFICATE.value
        assert report.configured is False
        assert report.available is False


def test_live_auth_preflight_surfaces_the_refusal_for_an_unbound_explicit_target() -> None:
    """The live-read preflight refuses when a session is open for ANOTHER profile.

    The distinction against the test above is the whole of the narrowing:
    answering here would be a claim about a profile that was never inspected,
    because a session exists and it serves someone else.
    """
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    with pytest.raises(AuthOperationRequiresCustodySessionError):
        build_live_auth_preflight_report(
            AuthProviderKind.CERTIFICATE.value,
            settings=settings_b,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
        )
