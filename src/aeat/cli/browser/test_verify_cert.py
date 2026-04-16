"""Unit tests for ``aeat browser verify-cert``."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic_settings import SettingsConfigDict
from typer.testing import CliRunner

from aeat.auth import CertificateLoadError, HandshakeResult
from aeat.cli.browser import app
from aeat.cli.browser import verify_cert as verify_module
from aeat.config import Settings

_RUNNER = CliRunner()


class _SuccessfulVerifier:
    async def verify(self) -> verify_module.CertificateVerificationResult:
        return verify_module.CertificateVerificationResult(
            subject="CN=Test Operator",
            handshake_status_code=200,
            handshake_url="https://sede.agenciatributaria.gob.es/",
            expedientes_count=3,
            sample_expediente_ids=("E-1", "E-2"),
            verified_at=datetime(2026, 4, 16, tzinfo=UTC),
        )


class _HandshakeFailVerifier:
    async def verify(self) -> HandshakeResult:
        return HandshakeResult(
            success=False,
            status_code=0,
            server_cert_chain=(),
            elapsed_ms=123,
            attempted_at=datetime(2026, 4, 16, tzinfo=UTC),
            error_message="SSLError: bad certificate",
        )


class _ReadFailVerifier:
    async def verify(self) -> verify_module.CertificateVerificationResult:
        raise RuntimeError("expedientes parse failed")


class _CertFailVerifier:
    async def verify(self) -> verify_module.CertificateVerificationResult:
        raise CertificateLoadError("AEAT_CERTIFICATE_PATH is not set")


def _install_factory(
    monkeypatch: pytest.MonkeyPatch,
    verifier_type: type[object],
) -> None:
    monkeypatch.setattr(verify_module, "VERIFY_FACTORY", lambda settings: verifier_type())


@pytest.mark.unit
def test_verify_cert_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _SuccessfulVerifier)
    result = _RUNNER.invoke(app, ["verify-cert"])
    assert result.exit_code == 0
    assert "expedientes_count=3" in result.stdout


@pytest.mark.unit
def test_verify_cert_success_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _SuccessfulVerifier)
    result = _RUNNER.invoke(app, ["verify-cert", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["expedientes_count"] == 3
    assert payload["sample_expediente_ids"] == ["E-1", "E-2"]


@pytest.mark.unit
def test_verify_cert_cert_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _CertFailVerifier)
    result = _RUNNER.invoke(app, ["verify-cert"])
    assert result.exit_code == 2
    assert "before handshake" in result.stdout


@pytest.mark.unit
def test_verify_cert_handshake_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _HandshakeFailVerifier)
    result = _RUNNER.invoke(app, ["verify-cert"])
    assert result.exit_code == 3
    assert "during handshake" in result.stdout


@pytest.mark.unit
def test_verify_cert_authenticated_read_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_factory(monkeypatch, _ReadFailVerifier)
    result = _RUNNER.invoke(app, ["verify-cert"])
    assert result.exit_code == 4
    assert "authenticated read" in result.stdout


@pytest.mark.unit
def test_verify_cert_rejects_verify_only_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    class IsolatedSettings(Settings):
        model_config = SettingsConfigDict(env_file=None)

    monkeypatch.setattr(verify_module, "Settings", IsolatedSettings)
    monkeypatch.setenv("AEAT_CERTIFICATE_BACKEND", "HTTPX_FALLBACK")

    result = _RUNNER.invoke(app, ["verify-cert"])

    assert result.exit_code == 2
    assert "PLAYWRIGHT_CONTEXT" in result.stdout
