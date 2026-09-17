"""Real-behavior tests for the auth operation custody-session precondition.

Every auth operator surface routes its storage access through
:func:`application.auth.operator_scope.active_profile_storage_span`. The span
no longer opens a session for whichever bucket the caller named: it requires the
target profile's custody session to already be open, and refuses otherwise.

These tests exercise the refusal against the application-owned scope ports.
The fake carries translated session identity facts, so the policy stays
inward without importing a storage root or a concrete bucket session.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ....core.auth_provider import AuthProviderKind
from ....core.bucket_pointer import BucketPointer, write_pointer
from ....core.config import load_settings, override_settings
from ....core.errors.error_codes import get_registered_error_code, resolve_error_message
from ..operator_probes import probe_local_session
from ..operator_results import AuthOperationRequiresCustodySessionError
from ..operator_scope import active_profile_storage_span
from ..operator_scope_ports import OperatorScopeSession
from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_scope_fakes import build_inward_operator_scope_ports
from .operator_projection_test_support import (
    build_live_auth_preflight_report,
)
from .operator_projection_test_support import (
    test_operator_auth as run_operator_auth_test,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

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


def test_span_yields_the_target_when_its_custody_session_is_open() -> None:
    """The guard is conditional: an open session for the target still resolves.

    Without this positive control the refusal tests below would pass against a
    span that refused unconditionally, which is a different (and broken)
    behaviour from the one under test.
    """
    with (
        override_settings(cadrumo_active_profile=_BUCKET_A) as settings,
        active_profile_storage_span(settings, operator_scope_ports=_OPERATOR_SCOPE_PORTS) as bucket_id,
    ):
        assert bucket_id == _BUCKET_A


def test_span_yields_none_when_no_target_bucket_resolves(tmp_path: Path) -> None:
    """A cold root with no pointer and no override has no target to guard."""
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None) as settings,
        active_profile_storage_span(settings, operator_scope_ports=_OPERATOR_SCOPE_PORTS) as bucket_id,
    ):
        assert bucket_id is None


def test_span_refuses_a_bucket_the_open_session_does_not_serve() -> None:
    """Bucket A's session cannot be borrowed to reach bucket B."""
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    with (
        pytest.raises(AuthOperationRequiresCustodySessionError) as raised,
        active_profile_storage_span(settings_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS),
    ):
        pytest.fail("the span must refuse before yielding a borrowed session")

    context = raised.value.context
    assert context is not None
    assert context["bucket_id"] == _BUCKET_B


def test_span_refuses_an_explicit_target_bucket_argument_it_cannot_serve() -> None:
    """The ``target_bucket_id`` argument is guarded on the same terms as the route."""
    with (
        pytest.raises(AuthOperationRequiresCustodySessionError) as raised,
        active_profile_storage_span(
            load_settings(), target_bucket_id=_BUCKET_B, operator_scope_ports=_OPERATOR_SCOPE_PORTS
        ),
    ):
        pytest.fail("an explicit target bucket must not bypass the custody guard")

    context = raised.value.context
    assert context is not None
    assert context["bucket_id"] == _BUCKET_B


def test_span_refuses_the_same_bucket_id_on_a_different_storage_root(
    tmp_path: Path,
) -> None:
    """A matching UUID on another root is a different profile's key material.

    This is the cross-taxpayer confusion the guard exists to stop: the bucket
    identity comparison alone would pass, and only the storage-root arm of
    :func:`_can_reuse_active_session` distinguishes the two.
    """
    other_root = tmp_path / "second-root"
    with override_settings(
        cadrumo_local_storage_root=other_root,
        cadrumo_active_profile=_BUCKET_A,
    ) as settings_other_root:
        pass

    ambient_before = _OPERATOR_SCOPE_PORTS.session.current()
    assert ambient_before is not None
    assert ambient_before.bucket_id == _BUCKET_A

    with (
        pytest.raises(AuthOperationRequiresCustodySessionError) as raised,
        active_profile_storage_span(settings_other_root, operator_scope_ports=_OPERATOR_SCOPE_PORTS),
    ):
        pytest.fail("a same-id bucket on another root must not reuse this root's session")

    context = raised.value.context
    assert context is not None
    assert context["bucket_id"] == _BUCKET_A
    assert Path(str(context["storage_root"])).name == other_root.name
    assert _OPERATOR_SCOPE_PORTS.session.current() is ambient_before


def test_span_refuses_a_pointer_target_whose_session_was_never_opened(
    tmp_path: Path,
) -> None:
    """Pointer-driven resolution is guarded too, not only the settings override.

    ``open_test_profile_session`` deliberately does not write the pointer, so
    this test writes it explicitly: the guard must fire on the bucket the
    pointer names, which is the route a real operator command follows.
    """
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None) as settings:
        write_pointer(
            settings.cadrumo_local_storage_root,
            BucketPointer.selected(bucket_id=_BUCKET_B, transition_revision=1),
        )

        with (
            pytest.raises(AuthOperationRequiresCustodySessionError) as raised,
            active_profile_storage_span(settings, operator_scope_ports=_OPERATOR_SCOPE_PORTS),
        ):
            pytest.fail("a pointer to an unopened profile must not resolve a session")

    context = raised.value.context
    assert context is not None
    assert context["bucket_id"] == _BUCKET_B


def test_refusal_carries_its_own_code_and_an_actionable_remedy() -> None:
    """The operator is told to authenticate, not to pick between two flags.

    The refusal previously reused ``AuthOperationScopeConflictError``, whose
    registered message is the ``--provider``/``--all`` instruction. That
    instruction cannot resolve a missing custody session, so the code and the
    message are both asserted here rather than only the exception type.
    """
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    with (
        pytest.raises(AuthOperationRequiresCustodySessionError) as raised,
        active_profile_storage_span(settings_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS),
    ):
        pytest.fail("the span must refuse before yielding a borrowed session")

    error = raised.value
    assert get_registered_error_code(error).code == "REFUSED_AUTH_OPERATION_REQUIRES_CUSTODY_SESSION"

    message = resolve_error_message(error)
    assert "aeat config login" in message
    assert "--all" not in message
    assert _BUCKET_B in message


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


def test_local_session_probe_degrades_to_absent_instead_of_raising() -> None:
    """The persisted-session probe reports "no session", never a crash.

    The probe is a diagnostic on a status surface, so the refusal must arrive
    as an absent session rather than aborting the whole report. This holds only
    while the refusal stays a ``CadrumoError`` subclass.
    """
    with override_settings(cadrumo_active_profile=_BUCKET_B) as settings_b:
        pass

    probe = probe_local_session(
        AuthProviderKind.CERTIFICATE.value, settings=settings_b, operator_scope_ports=_OPERATOR_SCOPE_PORTS
    )

    assert probe.present is False
    assert probe.state == "no_session"
