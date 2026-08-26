"""Production-direct policy, configuration, and diagnostics tests for Cl@ve Movil."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from pydantic import AnyUrl, SecretStr

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.remote_state_guard import RemoteOperation, assert_remote_operation_allowed

from ......core import AuthProviderKind
from ......core.config import Settings
from ......core.i18n import tr
from ......tests.profile_capsule import open_test_profile_session
from ......tests.secure_sql import isolated_runtime_profile
from ......tests.user_profile import register_minimal_profile
from ...operator_progress import operator_progress_sink
from ..clave_movil import ClaveMovilAuthProvider, ClaveMovilConfigurationError
from ..clave_movil_support import (
    auth_browser_action_policy as _auth_browser_action_policy,
)
from ..clave_movil_support import classify_identity as _classify_identity
from ..clave_movil_support import render_progress_banner as _render_progress_banner
from ._clave_movil_support import _CLAVE_SURFACE, _DOMAINS, _aeat_url, _run, _settings_for

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture(autouse=True)
def _isolated_secure_session_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="38550e03-9b84-40f7-b9ef-48b6a8693f84"):
        yield


def test_auth_browser_action_policy_allows_own_name_and_refuses_unclassified_action(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)
    action = settings.external_constants().aeat.pre303.representation_own_name_action_label

    assert (
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action=action),
        ).decision
        == "allowed"
    )
    with pytest.raises(RegistryValidationError, match="explicit read-only allow-list"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="browser_action", action="representation-gate-represented-taxpayer-continue"),
        )


def test_auth_browser_action_policy_admits_aeat_sibling_and_refuses_external_host(tmp_path: Path) -> None:
    settings = _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z")
    policy = _auth_browser_action_policy(settings)
    sibling = _aeat_url(_DOMAINS.www2, _CLAVE_SURFACE.obtener_clave_movil_non_qr_path)

    assert (
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="http", method="GET", url=AnyUrl(sibling)),
        ).decision
        == "allowed"
    )
    with pytest.raises(RegistryValidationError, match="not in allowed read-only hosts"):
        assert_remote_operation_allowed(
            policy,
            RemoteOperation(kind="http", method="GET", url=AnyUrl("https://attacker.example/read/path")),
        )


@pytest.mark.parametrize(
    ("identity", "expected_kind"),
    [("12345678Z", "DNI"), ("X1234567L", "NIE")],
)
def test_identity_classification_accepts_supported_people(identity: str, expected_kind: str) -> None:
    assert _classify_identity(identity) == expected_kind


@pytest.mark.parametrize("identity", ["B12345674", ""])
def test_identity_classification_rejects_unsupported_identity(identity: str) -> None:
    with pytest.raises(ClaveMovilConfigurationError, match=r"NIF|NIE|identity|CIF|empty"):
        _classify_identity(identity)


@pytest.mark.parametrize("identity", ["12345678A", "X1234567M"])
def test_identity_classification_rejects_checksum_invalid_identity(identity: str) -> None:
    """A correctly-shaped identifier with the wrong checksum letter is refused locally.

    ``12345678`` checksums to ``Z`` and ``X1234567`` to ``L``, so both values
    carry a shape the provider supports but a letter no real document does.
    The shape-only gate accepted them and deferred the failure to the live AEAT
    portal; the checksum gate refuses the operator's typo at configuration time.

    The refusal carries a ``translated_message`` key (rendered in the operator's
    output language, never an English literal) and preserves the caught identity
    error's localised detail in ``context`` rather than flattening it to
    ``str(exc)``.
    """
    with pytest.raises(ClaveMovilConfigurationError) as excinfo:
        _classify_identity(identity)
    error = excinfo.value
    assert error.translated_message == "errors.auth.clave_movil_identity_checksum"
    resolved = tr(error.translated_message)
    assert error.translated_message not in resolved
    assert error.context is not None
    detail = error.context["detail"]
    assert isinstance(detail, str) and detail


def test_attempt_context_uses_profile_storage_and_redacts_identity_values() -> None:
    bucket_id = "25252525-2525-4252-8252-252525252525"
    with open_test_profile_session(bucket_id):
        register_minimal_profile(
            profile_id=bucket_id,
            display_name="Clave Movil Test",
            overrides={"identity.tax_id": "X1234567L"},
        )
        settings = Settings(
            cadrumo_clave_movil_dni_nie=SecretStr("X1234567L"),
            cadrumo_clave_movil_nie_soporte=SecretStr("support-marker"),
            cadrumo_clave_prefer_non_qr=True,
            cadrumo_clave_movil_timeout_ms=120_000,
        )
        context = ClaveMovilAuthProvider(settings)._attempt_context()

    serialized = json.dumps(context, sort_keys=True)
    assert context["auth_mode"] == "non_qr"
    assert context["identity_kind"] == "NIE"
    assert context["identity_alignment"] == "matches"
    assert context["profile_tax_id_present"] is True
    assert "X1234567L" not in serialized
    assert "support-marker" not in serialized


def test_fresh_login_overrides_the_shared_headless_browser_default(tmp_path: Path) -> None:
    """The QR page must be visible even though routine browser reads are headless."""
    configured = Settings(
        cadrumo_token_dir=tmp_path,
        cadrumo_local_storage_root=tmp_path / "storage",
        cadrumo_clave_movil_dni_nie=SecretStr("12345678Z"),
        cadrumo_browser_headless=True,
    )
    provider = ClaveMovilAuthProvider(configured)

    fresh = provider._fresh_login_settings()

    assert configured.cadrumo_browser_headless is True
    assert fresh.cadrumo_browser_headless is False
    assert provider._attempt_context()["headless"] is False


@pytest.mark.parametrize(
    ("identity", "configured", "available", "severity"),
    [(None, False, False, "info"), ("12345678Z", True, True, ""), ("BAD", True, False, "warning")],
)
def test_describe_reports_configuration_health(
    tmp_path: Path,
    identity: str | None,
    configured: bool,
    available: bool,
    severity: str,
) -> None:
    env = {} if identity is None else {"CADRUMO_CLAVE_MOVIL_DNI_NIE": identity}
    description = ClaveMovilAuthProvider(_settings_for(tmp_path, **env)).describe()
    assert description.configured is configured
    assert description.available is available
    if severity:
        assert description.health_severity == severity
    if identity == "12345678Z":
        assert description.identity_nif == identity
        assert description.kind == AuthProviderKind.CLAVE_MOVIL


def test_missing_identity_refuses_public_authenticate(tmp_path: Path) -> None:
    provider = ClaveMovilAuthProvider(_settings_for(tmp_path))

    async def run() -> None:
        with pytest.raises(ClaveMovilConfigurationError, match=r"identity|NIF|NIE|configuration"):
            await provider.authenticate()

    _run(run())


def test_probe_without_persisted_session_refuses_without_fresh_login(tmp_path: Path) -> None:
    provider = ClaveMovilAuthProvider(
        _settings_for(tmp_path, CADRUMO_CLAVE_MOVIL_DNI_NIE="12345678Z"),
    )

    async def run() -> None:
        from ......core.errors import AeatLoginAssertionError

        with pytest.raises(AeatLoginAssertionError, match="no persisted"):
            await provider.probe_persisted_session()

    _run(run())


def test_render_progress_banner_routes_only_to_armed_operator_sink() -> None:
    from ......core import OperatorProgress

    captured: list[OperatorProgress] = []
    _render_progress_banner(verification_code="YLL", timeout_seconds=120, used_non_qr_fallback=True)
    assert captured == []
    with operator_progress_sink(captured.append):
        _render_progress_banner(verification_code="YLL", timeout_seconds=120, used_non_qr_fallback=True)
    assert len(captured) == 1
    assert "YLL" in captured[0].message
    assert captured[0].timeout_seconds == 120
    assert "Time remaining 2:00" in captured[0].render()


def test_render_progress_banner_uses_structured_log_not_stdio(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with caplog.at_level(logging.INFO, logger="cadrumo.adapters.outbound.aeat.auth.clave_movil"):
        _render_progress_banner(
            verification_code="ABC123",
            timeout_seconds=120,
            used_non_qr_fallback=False,
        )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert any("auth.waiting_banner" in record.message for record in caplog.records)

