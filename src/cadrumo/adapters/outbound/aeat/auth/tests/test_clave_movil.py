"""Protocol-level tests for the Cl@ve Movil authentication provider.

Exercises :class:`cadrumo.adapters.outbound.aeat.auth._clave_movil.ClaveMovilAuthProvider`
against hand-written ``BrowserSessionLike`` stand-ins that record the
navigation and form interactions performed by the provider. The
stand-ins satisfy the same Protocol the production
:class:`cadrumo.adapters.outbound.aeat.browser.BrowserSession` presents, so the
provider's choreography (selector clicks, form fills, post-auth
landing assertions) is verified without a real browser.

These tests do not prove real AEAT authentication or operator-side
Cl@ve state; the live handshake is covered by gated probes elsewhere.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import AnyUrl, SecretStr

from ......application.user_profile import profile_create_storage_span, register_minimal_profile
from ......application.workflow import workflow_state_repository
from ......core import AuthProviderKind
from ......core.classification import SensitivityClass
from ......core.config import Settings
from ......domain.calculations.registry import RegistryValidationError, RemoteOperation, assert_remote_operation_allowed
from ......tests.aeat_literal_fixtures import CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED
from ......tests.secure_sql import isolated_runtime_profile
from .....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from .. import operator_progress_sink
from .._clave_movil import (
    CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
    ClaveMovilApprovalTimeoutError,
    ClaveMovilAuthProvider,
    ClaveMovilConfigurationError,
    ClaveMovilFailureMode,
    _auth_browser_action_policy,
    _classify_identity,
    _extract_verification_code_from_html,
    _render_progress_banner,
)
from .._providers import ClaveMovilSessionDetail
from ._clave_movil_support import (
    _CLAVE_SURFACE,
    _DOMAINS,
    _PRE303_SURFACE,
    _aeat_url,
    _CancelableClavePage,
    _HangingCloseBrowserSession,
    _HangingCloseContext,
    _NoPushWaitStatePage,
    _OwnNameInputOnlyRepresentationPage,
    _PendingPetitionPage,
    _RecordingPage,
    _RepresentationAlertPage,
    _run,
    _SelectorDispatchContext,
    _settings_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_VERIFY_SESSION_AUTHENTICATED_AT = datetime(2099, 5, 28, 15, 10, tzinfo=UTC)


def test_auth_browser_action_policy_allows_configured_own_name_representation_action(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(
            kind="browser_action",
            action=settings.external_constants().aeat.pre303.representation_own_name_action_label,
        ),
    )

    assert result.decision == "allowed"


def test_auth_browser_action_policy_rejects_unclassified_representation_action(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)

    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action="representation-gate-represented-taxpayer-continue"),
        )


def test_auth_browser_action_policy_admits_sibling_load_balancer_host(tmp_path: Path) -> None:
    """An auth navigation dispatched to a www{n} sibling beyond the enumerated hosts is allowed."""
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)
    drifted = _aeat_url(_DOMAINS.www2, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)

    result = assert_remote_operation_allowed(
        policy,
        RemoteOperation(kind="http", method="GET", url=AnyUrl(drifted)),
    )

    assert result.decision == "allowed"


def test_auth_browser_action_policy_refuses_non_aeat_host(tmp_path: Path) -> None:
    """Widening to the AEAT apex suffix must not admit an off-AEAT host."""
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)

    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
        )


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="clave-movil-test"):
        yield


# ── cleanup bounds ───────────────────────────────────────────────────────────


def test_context_cleanup_is_bounded_by_settings_timeout(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z").model_copy(
        update={"cadrumo_browser_close_timeout_ms": 1},
    )
    provider = ClaveMovilAuthProvider(settings)
    context = _HangingCloseContext(target_path=settings.aeat_sede_expedientes_path)

    async def run() -> None:
        started = time.perf_counter()
        await provider._close_context(context, reason="timeout-regression")
        assert time.perf_counter() - started < 0.5

    _run(run())


def test_browser_session_cleanup_is_bounded_by_settings_timeout(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z").model_copy(
        update={"cadrumo_browser_close_timeout_ms": 1},
    )
    provider = ClaveMovilAuthProvider(settings)
    session = _HangingCloseBrowserSession(target_path=settings.aeat_sede_expedientes_path)

    async def run() -> None:
        started = time.perf_counter()
        await provider._close_browser_session(session)
        assert time.perf_counter() - started < 0.5

    _run(run())


# ── identity classification ──────────────────────────────────────────────────


class TestIdentityClassification:
    @pytest.mark.parametrize(
        ("identity", "expected_kind"),
        (
            pytest.param("12345678Z", "DNI", id="dni"),
            pytest.param("X1234567L", "NIE", id="nie"),
        ),
    )
    def test_classifies_dni_and_nie(self, identity: str, expected_kind: str) -> None:
        assert _classify_identity(identity) == expected_kind

    @pytest.mark.parametrize(
        ("identity", "expected_message"),
        (
            pytest.param("B12345674", r"NIF|NIE|identity|CIF", id="cif"),
            pytest.param("", r"NIF|NIE|identity|empty", id="empty"),
        ),
    )
    def test_rejects_unsupported_identity(self, identity: str, expected_message: str) -> None:
        with pytest.raises(ClaveMovilConfigurationError, match=expected_message):
            _classify_identity(identity)


class TestAttemptDiagnostics:
    def test_attempt_context_uses_real_profile_storage_and_redacts_identity_values(self) -> None:
        with profile_create_storage_span("25252525-2525-4252-8252-252525252525"):
            workflow_state_repository().update(
                lambda state: register_minimal_profile(
                    state,
                    profile_id="25252525-2525-4252-8252-252525252525",
                    overrides={"identity.tax_id": "X1234567L"},
                    secure_objects=secure_object_repository_for_active_bucket(),
                    enforce_unique_tax_id=False,
                ),
            )
            settings = Settings(
                cadrumo_clave_movil_dni_nie=SecretStr("X1234567L"),
                cadrumo_clave_movil_nie_soporte=SecretStr("support-marker"),
                cadrumo_clave_prefer_non_qr=True,
                cadrumo_clave_movil_timeout_ms=120_000,
            )

            context = ClaveMovilAuthProvider(settings)._attempt_context()
        context_json = json.dumps(context, sort_keys=True)

        assert context["auth_mode"] == "non_qr"
        assert context["auth_route"] == "clave_movil_non_qr_request"
        assert context["identity_kind"] == "NIE"
        assert context["active_profile_id"] == ""
        assert str(context["active_profile_ref"]).startswith("sha256:")
        assert context["active_profile_label"] == ""
        assert context["active_profile_label_present"] is True
        assert context["active_profile_registered"] is True
        assert context["profile_record_present"] is True
        assert context["profile_tax_id_present"] is True
        assert context["identity_alignment"] == "matches"
        assert context["nie_soporte_configured"] is True
        assert context["timeout_ms"] == 120_000
        assert "X1234567L" not in context_json
        assert "support-marker" not in context_json
        assert "diagnostic-profile" not in context_json


# ── describe() ──────────────────────────────────────────────────────────────


class TestDescribe:
    def test_describe_unconfigured(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path)
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is False
        assert description.available is False
        # Round-5 B2: refusal text is user prose, never the raw
        # env-var name; severity is ``info`` for an undeclared state,
        # not the loudest ``error`` token.
        assert "CADRUMO_CLAVE_MOVIL_DNI_NIE" not in (description.health_summary or "")
        assert description.health_severity == "info"
        assert "DNI" in (description.health_summary or "") or "NIE" in (description.health_summary or "")

    def test_describe_configured(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is True
        assert description.identity_nif == "12345678Z"
        assert description.kind == AuthProviderKind.CLAVE_MOVIL

    def test_describe_invalid_identity(self, tmp_path: Path) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="BAD")
        provider = ClaveMovilAuthProvider(settings)
        description = provider.describe()
        assert description.configured is True
        assert description.available is False
        assert "not a valid DNI" in (description.health_summary or "")


def test_render_progress_banner_routes_to_operator_sink_only_when_armed() -> None:
    """The wait banner reaches an armed operator sink and no sink otherwise.

    Opt-in by construction: an unarmed call routes nothing to the caller's
    sink (production/default behaviour is log-only); an armed call routes the
    banner — carrying the verification code — exactly once. Proves the code
    surfaces to the operator channel without a value change to any other
    surface."""

    captured: list[str] = []

    _render_progress_banner(verification_code="YLL", timeout_seconds=120, used_non_qr_fallback=True)
    assert captured == [], "an unarmed banner must not route to any operator sink"

    with operator_progress_sink(captured.append):
        _render_progress_banner(verification_code="YLL", timeout_seconds=120, used_non_qr_fallback=True)

    assert len(captured) == 1
    banner = captured[0]
    assert "YLL" in banner
    assert "verification code" in banner.lower()
    assert "Cl@ve" in banner


# ── authenticate() — fresh login ─────────────────────────────────────────────


class TestAuthenticateFresh:
    def test_missing_identity_raises_configuration_error(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path)
        provider = ClaveMovilAuthProvider(settings)

        async def run() -> None:
            with pytest.raises(ClaveMovilConfigurationError, match=r"identity|NIF|NIE|configuration"):
                await provider.authenticate()

        _run(run())


class TestPostAuthLanding:
    def test_verify_clicks_selector_for_explicit_target_probe(
        self,
        tmp_path: Path,
    ) -> None:
        from .._authenticator import AeatSession

        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
        target_path = provider._target_path_from_url(target_url)
        context = _SelectorDispatchContext(target_path=target_path)
        provider._context = context
        session = AeatSession(
            authenticated_at=_VERIFY_SESSION_AUTHENTICATED_AT,
            idle_deadline=_VERIFY_SESSION_AUTHENTICATED_AT + timedelta(minutes=18),
            storage_state_path=None,
            identity_nif="12345678Z",
            provider_detail=ClaveMovilSessionDetail(
                dni_nie="12345678Z",
                used_non_qr_fallback=True,
                verification_code="YLL",
                landing_url=None,
            ),
        )

        async def run() -> None:
            assertion = await provider.verify(session, target_url=target_url)
            assert assertion.is_valid is True

        _run(run())

        page = context.pages[0]
        assert external.aeat.clave_movil.selector_access_path_marker in page.gotos[0]
        assert external.aeat.clave_movil.authorize_button_selector in page.clicks

    def test_explicit_verification_target_uses_selector_dispatch(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        target_url = f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}"
        target_path = provider._target_path_from_url(target_url)

        probe_url = provider._probe_url_for_verification(
            explicit_target_url=target_url,
            resolved_target_url=target_url,
            target_path=target_path,
        )

        assert external.aeat.clave_movil.selector_access_path_marker in probe_url
        assert probe_url != target_url

    def test_implicit_verification_target_keeps_recorded_landing(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()
        landing_url = f"{external.aeat.domains.www6}{external.aeat.sede_paths.expedientes_resumen}"
        target_path = provider._target_path_from_url(landing_url)

        probe_url = provider._probe_url_for_verification(
            explicit_target_url=None,
            resolved_target_url=landing_url,
            target_path=target_path,
        )

        assert probe_url == landing_url

    def test_authenticated_landing_accepts_pre303_post_auth_redirect(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        external = settings.external_constants()

        accepted = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.www1}{external.aeat.pre303.presentation_service_path}",
            target_path=external.aeat.pre303.presentation_service_path,
        )
        auth_gate = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.sede}{external.aeat.sede_paths.auth_gate_4033}",
            target_path=external.aeat.pre303.presentation_service_path,
        )
        selector = provider._is_authenticated_aeat_landing(
            landing_url=external.aeat.clave_movil.selector_access_url_template.format(
                target=external.aeat.pre303.presentation_service_path,
            ),
            target_path=external.aeat.pre303.presentation_service_path,
        )
        other_app = provider._is_authenticated_aeat_landing(
            landing_url=f"{external.aeat.domains.www1}{external.aeat.sede_paths.iva_compensation_wallet}",
            target_path=external.aeat.pre303.presentation_service_path,
        )

        assert accepted is True
        assert auth_gate is False
        assert selector is False
        assert other_app is False

    def test_representation_dispatcher_continues_only_own_name(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _RecordingPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path)

        async def run() -> None:
            await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=1_000)

        _run(run())
        assert page.clicks == [
            _PRE303_SURFACE.representation_own_name_label_selector,
            _PRE303_SURFACE.representation_submit_selector,
        ]

    def test_representation_dispatcher_dismisses_alert_modal_before_own_name(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _RepresentationAlertPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path)

        async def run() -> None:
            await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=1_000)

        _run(run())
        continue_selector = (
            f"{_PRE303_SURFACE.alert_modal_selector}.show "
            f'button:has-text("{_PRE303_SURFACE.alert_continue_button_text.title()}")'
        )
        assert page.clicks == [
            continue_selector,
            _PRE303_SURFACE.representation_own_name_label_selector,
            _PRE303_SURFACE.representation_submit_selector,
        ]

    def test_representation_dispatcher_accepts_own_name_input_when_label_missing(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="TEST-IDENTITY")
        provider = ClaveMovilAuthProvider(settings)
        page = _OwnNameInputOnlyRepresentationPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www6, _CLAVE_SURFACE.dialogo_representacion_path)

        async def run() -> None:
            await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=1_000)

        _run(run())
        assert page.clicks == [
            _PRE303_SURFACE.representation_own_name_selector,
            _PRE303_SURFACE.representation_submit_selector,
        ]


class TestPendingPetitionRefusal:
    def test_pending_petition_page_fails_fast_with_actionable_mode(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _PendingPetitionPage(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> str:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"Cl@ve|pending|prior|petition") as excinfo:
                await provider._raise_if_pending_request_error(page)
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert excinfo.value.context is not None
            assert excinfo.value.context["failure_mode"] == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert "detected_markers" in excinfo.value.context
            assert "diagnostic_id" in excinfo.value.context
            diagnostic_id = excinfo.value.context["diagnostic_id"]
            assert isinstance(diagnostic_id, str)
            assert excinfo.value.suggestion is not None
            return diagnostic_id

        diagnostic_id = _run(run())
        record = secure_object_repository_for_active_bucket().load(
            CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
            diagnostic_id,
            expected_class=SensitivityClass.SESSION,
            max_supported_version=1,
        )
        assert record is not None
        payload = json.loads(record.payload.decode("utf-8"))
        assert payload["diagnostic_id"] == diagnostic_id
        assert payload["reason"] == "pending-request-refusal"

    def test_post_auth_wait_detects_pending_petition_refusal_during_poll(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _PendingPetitionPage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"Cl@ve|pending|prior|refused") as excinfo:
                await provider._wait_for_post_auth_landing(page, settings.aeat_sede_expedientes_path, timeout_ms=100)
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PENDING_PETITION_BLOCKED
            assert excinfo.value.context is not None
            assert excinfo.value.context["reason"] == "aeat-refused-new-clave-movil-petition"

        _run(run())

    def test_pending_request_cancellation_waits_for_aeat_cancel_response(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _CancelableClavePage(target_path=settings.aeat_sede_expedientes_path)

        async def run() -> None:
            await provider._cancel_pending_auth_request(page)

        _run(run())

        assert page.evaluate_calls == 1
        assert page.wait_for_response_calls == 1
        assert f"window.{CLAVE_MOVIL_BROWSER_GLOBAL_EXPECTED}" not in page.evaluated_script
        assert f'window["{settings.external_constants().aeat.clave_movil.obtener_clave_movil_browser_global}"]' in (
            page.evaluated_script
        )

    def test_pending_request_cancel_confirmation_rejects_failed_response(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _CancelableClavePage(target_path=settings.aeat_sede_expedientes_path, status=500)

        async def run() -> bool:
            return await provider._wait_for_cancel_confirmation(page)

        assert _run(run()) is False


class TestClaveWaitState:
    def test_extracts_verification_code_from_rendered_non_qr_html(self) -> None:
        html = """
        <div class="negrita codigoVerificacion">Código de verificación</div>
        <div class="negrita codigoVerificacion fuenteTamanyo3em">IL9</div>
        <form><input id="inputDNIReadonly" value="00000000T"></form>
        """

        assert _extract_verification_code_from_html(html) == "IL9"

    def test_login_refuses_to_wait_without_observed_confirmation_state(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _NoPushWaitStatePage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)

        async def run() -> None:
            with pytest.raises(ClaveMovilApprovalTimeoutError, match=r"confirmation waiting state") as excinfo:
                await provider._assert_push_wait_state(
                    page,
                    target_path=settings.aeat_sede_expedientes_path,
                    verification_code=None,
                    used_non_qr_fallback=True,
                )
            assert excinfo.value.failure_mode == ClaveMovilFailureMode.PUSH_WAIT_STATE_NOT_REACHED
            assert excinfo.value.context is not None
            assert excinfo.value.context["reason"] == "aeat-clave-movil-wait-state-not-reached"
            assert excinfo.value.context["verification_code_present"] is False
            assert "diagnostic_id" in excinfo.value.context

        _run(run())

    def test_login_accepts_observed_verification_code_as_wait_state(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)
        page = _NoPushWaitStatePage(target_path=settings.aeat_sede_expedientes_path)
        page.url = _aeat_url(_DOMAINS.www12, _CLAVE_SURFACE.autentica_dni_nie_contraste_path)

        async def run() -> None:
            await provider._assert_push_wait_state(
                page,
                target_path=settings.aeat_sede_expedientes_path,
                verification_code="YLL",
                used_non_qr_fallback=True,
            )

        _run(run())


# ── authenticate() — resume path ─────────────────────────────────────────────


class TestProbePersistedSession:
    """:meth:`ClaveMovilAuthProvider.probe_persisted_session` never touches the fresh-login path."""

    def test_probe_without_persisted_session_raises(
        self,
        tmp_path: Path,
    ) -> None:
        settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
        provider = ClaveMovilAuthProvider(settings)

        async def run() -> None:
            from .._authenticator import AeatLoginAssertionError

            with pytest.raises(AeatLoginAssertionError, match="no persisted"):
                await provider.probe_persisted_session()

        _run(run())


# ── contract: auth waiting banner routes through structured logger ─────────────────


def test_render_progress_banner_emits_via_logger_not_stdout(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """_render_progress_banner must write to the logger, not to stdout/stderr."""
    import logging

    with caplog.at_level(logging.INFO, logger="cadrumo.adapters.outbound.aeat.auth._clave_movil"):
        _render_progress_banner(
            verification_code="ABC123",
            timeout_seconds=120,
            used_non_qr_fallback=False,
        )

    # Nothing must leak to the real stdout or stderr streams.
    captured = capsys.readouterr()
    assert captured.out == "", "progress banner must not write to stdout"
    assert captured.err == "", "progress banner must not write to stderr"

    # The structured log record must carry the banner text.
    assert any("auth.waiting_banner" in r.message for r in caplog.records), (
        "expected an 'auth.waiting_banner' log record"
    )


@pytest.mark.parametrize(
    ("verification_code", "timeout_seconds", "used_non_qr_fallback"),
    (
        pytest.param(None, 60, False, id="qr"),
        pytest.param("XYZ", 300, True, id="non-qr"),
    ),
)
def test_render_progress_banner_branch_logged(
    caplog: pytest.LogCaptureFixture,
    verification_code: str | None,
    timeout_seconds: int,
    used_non_qr_fallback: bool,
) -> None:
    """QR and non-QR branch banners must appear in structured log records."""
    import logging

    with caplog.at_level(logging.INFO, logger="cadrumo.adapters.outbound.aeat.auth._clave_movil"):
        _render_progress_banner(
            verification_code=verification_code,
            timeout_seconds=timeout_seconds,
            used_non_qr_fallback=used_non_qr_fallback,
        )

    assert any("auth.waiting_banner" in r.message for r in caplog.records)
