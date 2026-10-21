"""Method-specific synchronization prerequisites use the executable credential resolver."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from ....core.auth_provider import AuthProviderKind
from ....core.config import override_settings
from ...auth_credentials import ActiveCertificateCredentials
from ..auth_read_contracts import AuthReadProjection, AuthReadResult
from ..credentials import ActiveAuthProjectionSnapshot
from ..operator_probe_ports import CertificateHealthBand, CertificateHealthObservation, ClaveIdentityObservation
from ..sync_readiness import AuthSyncReadiness, project_auth_sync_readiness
from ._operator_probe_fakes import fake_operator_probe_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _read(
    provider: AuthProviderKind | None,
    values: dict[str, str],
    *,
    password: SecretStr | None = None,
    certificate: ActiveCertificateCredentials | None = None,
    nie: bool = False,
    expired: bool = False,
) -> AuthSyncReadiness:
    snapshot = ActiveAuthProjectionSnapshot(
        bucket_id=None,
        state=None,
        provider=provider,
        certificate_credentials=certificate,
        clave_permanente_password=password,
    )
    ports = fake_operator_probe_ports(
        clave_identity=ClaveIdentityObservation(kind="NIE" if nie else "DNI"),
        certificate_health=CertificateHealthObservation(
            severity=CertificateHealthBand.EXPIRED if expired else CertificateHealthBand.OK,
            days_until_expiry=-1 if expired else 100,
        ),
    )
    with override_settings(
        cadrumo_clave_movil_dni_nie=None,
        cadrumo_clave_movil_nie_soporte=None,
        cadrumo_clave_movil_dni_fecha=None,
        cadrumo_clave_prefer_non_qr=True,
    ) as settings:
        return project_auth_sync_readiness(snapshot, values=values, settings=settings, operator_probe_ports=ports)


def test_fresh_profile_requires_method_and_tax_identity() -> None:
    result = _read(None, {})
    assert not result.ready
    assert {item.field for item in result.requirements if not item.satisfied} == {"auth.provider", "identity.tax_id"}


@pytest.mark.parametrize("route,ready", [("qr", True), ("app_request", False)])
def test_qr_does_not_require_app_contrast(route: str, ready: bool) -> None:
    result = _read(
        AuthProviderKind.CLAVE_MOVIL,
        {"identity.tax_id": "12345678Z", "auth.dni_nie": "12345678Z", "auth.clave_movil_route": route},
    )
    assert result.ready is ready
    assert ("auth.fecha_validez" in {item.field for item in result.requirements}) is (route == "app_request")


def test_nie_requires_support_instead_of_date() -> None:
    result = _read(
        AuthProviderKind.CLAVE_MOVIL,
        {"identity.tax_id": "X1234567L", "auth.dni_nie": "X1234567L", "auth.numero_soporte": "E12345678"},
        nie=True,
    )
    assert result.ready
    assert "auth.numero_soporte" in {item.field for item in result.requirements}
    assert "auth.fecha_validez" not in {item.field for item in result.requirements}


def test_identity_mismatch_blocks_even_with_contrast() -> None:
    result = _read(
        AuthProviderKind.CLAVE_MOVIL,
        {"identity.tax_id": "12345678Z", "auth.dni_nie": "00000001R", "auth.fecha_validez": "2030-01-01"},
    )
    assert not result.ready
    assert any(item.field == "auth.identity_alignment" and not item.satisfied for item in result.requirements)


@pytest.mark.parametrize("password,ready", [(None, False), (SecretStr("private-password"), True)])
def test_permanente_needs_saved_password_and_never_releases_it(password: SecretStr | None, ready: bool) -> None:
    result = _read(
        AuthProviderKind.CLAVE_PERMANENTE,
        {"identity.tax_id": "12345678Z", "auth.dni_nie": "12345678Z"},
        password=password,
    )
    assert result.ready is ready
    assert "private-password" not in result.model_dump_json()
    assert "12345678Z" not in result.model_dump_json()
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000aa")
    response = AuthReadResult(profile_id=profile_id, kind="sync_readiness", sync_readiness=result)
    assert AuthReadResult.model_validate_json(response.model_dump_json()) == response
    projection = AuthReadProjection(profile_id=profile_id, kind="sync_readiness", sync_readiness=result)
    assert projection.to_result() == response


@pytest.mark.parametrize("expired", [False, True])
def test_real_certificate_health_controls_readiness(tmp_path: Path, expired: bool) -> None:
    path = tmp_path / "test.p12"
    path.write_bytes(b"bundle supplied to health boundary")
    result = _read(
        AuthProviderKind.CERTIFICATE,
        {"identity.tax_id": "12345678Z"},
        certificate=ActiveCertificateCredentials(certificate_path=path, password=SecretStr("certificate-password")),
        expired=expired,
    )
    assert result.ready is not expired


def test_readiness_cannot_claim_success_with_missing_fields() -> None:
    with pytest.raises(ValidationError):
        AuthSyncReadiness(ready=True)


@pytest.mark.parametrize("password", [None, SecretStr("")])
def test_certificate_requires_a_supported_nonempty_passphrase(tmp_path: Path, password: SecretStr | None) -> None:
    path = tmp_path / "test.p12"
    path.write_bytes(b"bundle supplied to health boundary")
    result = _read(
        AuthProviderKind.CERTIFICATE,
        {"identity.tax_id": "12345678Z"},
        certificate=ActiveCertificateCredentials(certificate_path=path, password=password),
    )
    assert not result.ready
    assert any(item.field == "certificate.passphrase" and not item.satisfied for item in result.requirements)
