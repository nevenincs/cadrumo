"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import pytest

from ......core.i18n import tr
from ._authenticator_support import (
    _SENSITIVE_HEALTH_PAYLOAD,
    _SENSITIVE_STORAGE_BASENAME,
    AEAT_SESSION_IDLE_TTL,
    SECRET_PASSPHRASE,
    UTC,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatLoginAssertionError,
    AeatSession,
    AuthProvider,
    AuthProviderDescription,
    AuthProviderKind,
    AuthValidationError,
    CertificateBackend,
    CertificateError,
    CertificateNifParseError,
    ClaveMovilLoginAssertionDetail,
    ClaveMovilSessionDetail,
    NameOID,
    NoReturn,
    Path,
    _build_bundle,
    _certificate_assertion,
    _certificate_session,
    _HandshakeVerifier,
    _load_cert,
    authenticator_module,
    datetime,
    extract_nif_from_subject,
    logging,
    select_provider,
    timedelta,
    x509,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_extract_nif_from_serial_with_idces_prefix(tmp_path: Path) -> None:
    cert = _load_cert(tmp_path)
    assert extract_nif_from_subject(cert) == "12345678Z"


def test_extract_nif_from_bare_serial(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ANYBODY"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "87654321A"),
        ],
    )
    assert extract_nif_from_subject(cert) == "87654321A"


def test_extract_nif_accepts_nie(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "X1234567L"),
            x509.NameAttribute(NameOID.COMMON_NAME, "RESIDENT PERSON"),
        ],
    )
    assert extract_nif_from_subject(cert) == "X1234567L"


def test_extract_nif_cn_fallback(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO - 22334455B"),
        ],
    )
    assert extract_nif_from_subject(cert) == "22334455B"


def test_extract_nif_rejects_cif(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "B12345674"),
            x509.NameAttribute(NameOID.COMMON_NAME, "EMPRESA SL"),
        ],
    )
    with pytest.raises(CertificateNifParseError, match=r"NIF|subject|certificate"):
        extract_nif_from_subject(cert)


def test_extract_nif_rejects_unparseable(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NO-NIF-HERE"),
        ],
    )
    with pytest.raises(CertificateNifParseError, match=r"NIF|subject|certificate"):
        extract_nif_from_subject(cert)


def test_aeat_session_is_stale_predicate(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )
    assert session.is_stale(authenticated_at) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=1)) is False
    assert session.is_stale(authenticated_at + timedelta(minutes=30)) is True


def test_aeat_session_model_dump_carries_no_secrets(tmp_path: Path) -> None:
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
        subject="CN=NOMBRE,SERIALNUMBER=12345678Z",
        storage_state_path=tmp_path / "storage.json",
    )
    dumped = session.model_dump_json()
    assert SECRET_PASSPHRASE not in dumped
    assert "_pkcs12_bytes" not in dumped


def test_aeat_login_assertion_is_valid_composite() -> None:
    assertion = _certificate_assertion()
    assert assertion.is_valid is True
    assert assertion.model_config.get("frozen") is True


def test_invalid_persisted_session_redacts_path_and_reason(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    auth = AeatAuthenticator(settings, handshake_verifier=_HandshakeVerifier())
    storage_state_path = tmp_path / _SENSITIVE_STORAGE_BASENAME

    caplog.set_level(logging.INFO, logger=authenticator_module.__name__)
    with pytest.raises(AeatLoginAssertionError) as exc_info:
        auth._raise_invalid_persisted_state(
            storage_state_path,
            f"persisted storage_state missing: {storage_state_path}",
        )

    rendered = str(exc_info.value)
    assert _SENSITIVE_STORAGE_BASENAME not in rendered
    assert str(storage_state_path) not in rendered
    assert rendered == "persisted AEAT browser session is invalid"
    assert exc_info.value.context == {
        "session": "<persisted-aeat-session>",
        "reason": "storage_state_missing",
    }
    assert exc_info.value.translated_message == "errors.auth.auth_auth_authenticator_persisted_session_invalid"

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_STORAGE_BASENAME not in log_text
    assert str(storage_state_path) not in log_text
    assert "<persisted-aeat-session>" in log_text
    assert "reason=storage_state_missing" in log_text


def test_describe_warns_when_password_missing(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path, aeat_certificate_password_secret=None)
    description = AeatAuthenticator(settings).describe()

    assert description.configured is True
    assert description.available is False
    assert description.health_summary == "AEAT_CERTIFICATE_PASSWORD_SECRET not set"


def test_describe_preserves_expired_certificate_severity(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(
        tmp_path,
        not_valid_after=datetime.now(UTC) - timedelta(hours=12),
    )
    settings = _settings_factory(bundle_path)
    description = AeatAuthenticator(settings).describe()

    assert description.available is True
    assert description.health_severity == "EXPIRED"
    assert description.days_until_expiry is not None
    assert description.days_until_expiry <= 0


def test_describe_redacts_certificate_health_error(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    def _certificate_health_error(*args: object, **kwargs: object) -> NoReturn:
        raise CertificateError(f"failed to inspect {_SENSITIVE_HEALTH_PAYLOAD}")

    caplog.set_level(logging.DEBUG, logger=authenticator_module.__name__)
    description = AeatAuthenticator(
        settings,
        certificate_health_check=_certificate_health_error,
    ).describe()

    assert description.available is False
    assert description.health_summary == tr("application.auth.certificate.health.unavailable")

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_HEALTH_PAYLOAD not in log_text
    assert "failure=CertificateError" in log_text


def test_describe_redacts_unexpected_certificate_health_error(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    def _unexpected_certificate_health_error(*args: object, **kwargs: object) -> NoReturn:
        raise RuntimeError(f"unexpected certificate probe {_SENSITIVE_HEALTH_PAYLOAD}")

    caplog.set_level(logging.DEBUG, logger=authenticator_module.__name__)
    with pytest.raises(AuthValidationError) as exc_info:
        AeatAuthenticator(
            settings,
            certificate_health_check=_unexpected_certificate_health_error,
        ).describe()

    assert str(exc_info.value) == "certificate health is unavailable"
    assert exc_info.value.translated_message == "application.auth.certificate.health.unavailable"
    assert _SENSITIVE_HEALTH_PAYLOAD not in str(exc_info.value)
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert _SENSITIVE_HEALTH_PAYLOAD not in log_text
    assert "failure=RuntimeError" in log_text


def test_describe_forwards_bundle_backend_and_friendly_name(
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    from pydantic import SecretStr

    settings = _settings_factory(bundle_path, aeat_certificate_friendly_name="operator cert")

    captured: dict[str, object] = {}
    real_certificate_health = authenticator_module.certificate_health

    def _capture_certificate_health(
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        backend: CertificateBackend = CertificateBackend.PLAYWRIGHT_CONTEXT,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ):
        captured["path"] = path
        captured["password"] = password
        captured["warn_days"] = warn_days
        captured["critical_days"] = critical_days
        captured["backend"] = backend
        captured["friendly_name"] = friendly_name
        return real_certificate_health(
            path,
            password=password,
            warn_days=warn_days,
            critical_days=critical_days,
            backend=backend,
            friendly_name=friendly_name,
            now=now,
        )

    description = AeatAuthenticator(
        settings,
        certificate_health_check=_capture_certificate_health,
    ).describe()

    assert description.available is True
    assert captured["path"] == bundle_path
    captured_password = captured["password"]
    assert isinstance(captured_password, SecretStr)
    assert captured_password.get_secret_value() == SECRET_PASSPHRASE
    assert captured["backend"] == CertificateBackend.HTTPX_FALLBACK
    assert captured["friendly_name"] == "operator cert"


def test_describe_does_not_touch_os_environ(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """``AeatAuthenticator.describe()`` carries the passphrase as a
    SecretStr directly to ``certificate_health`` via the
    :class:`CertificateBundle.password` field. It never writes the
    secret into ``os.environ``, so a pre-call snapshot of the
    relevant env vars must equal the post-call snapshot exactly.

    The Settings passphrase is injected via ContextVar-backed
    ``override_settings`` rather than env, so the os.environ delta
    is the only thing under test.
    """

    import os as _os

    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    before = dict(_os.environ)

    description = AeatAuthenticator(settings).describe()
    assert description.available is True

    after = dict(_os.environ)
    assert before == after, "describe() must not mutate os.environ"


def test_extract_nif_handles_escaped_comma_in_cn(tmp_path: Path) -> None:
    """RFC 4514 escaped commas in CN must not split the DN parser.

    The rfc4514_string emitted by cryptography quotes a literal
    comma in a CN as ``\\,``. A naive regex that splits on `,` would
    break ``CN=Doe\\, John,SERIALNUMBER=12345678Z`` into two halves
    and mis-attribute the serial number. This test asserts the
    x509-backed parser handles the escape correctly.
    """
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Doe, John"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678Z"),
        ],
    )
    assert extract_nif_from_subject(cert) == "12345678Z"


def test_extract_nif_handles_quoted_plus_in_cn(tmp_path: Path) -> None:
    """RFC 4514 escaped ``+`` in a value must not split RDNs."""
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COMMON_NAME, "Alice+Bob Industries"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "X1234567L"),
        ],
    )
    assert extract_nif_from_subject(cert) == "X1234567L"


def test_aeat_session_is_stale_with_naive_datetime(tmp_path: Path) -> None:
    """Naive datetimes passed to is_stale are coerced to UTC.

    Documents the existing behaviour so a regression is caught if
    the coercion is ever removed. A caller on a non-UTC workstation
    that supplies a naive ``datetime.now()`` will hit this path.
    """
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )
    naive_past = datetime(2020, 1, 1)
    naive_future = datetime(2100, 1, 1)
    assert session.is_stale(naive_past) is False
    assert session.is_stale(naive_future) is True


def test_auth_provider_protocol_conformance() -> None:
    class _NullAuthProvider:
        kind = AuthProviderKind.CLAVE_MOVIL

        async def authenticate(
            self,
            *,
            browser_session: object | None = None,
            target_url: str | None = None,
        ) -> AeatSession:
            now = datetime.now(UTC)
            return AeatSession(
                provider_kind=self.kind,
                authenticated_at=now,
                idle_deadline=now + AEAT_SESSION_IDLE_TTL,
                storage_state_path=None,
                identity_nif="X1234567L",
                provider_detail=ClaveMovilSessionDetail(dni_nie="X1234567L"),
            )

        async def verify(
            self,
            session: AeatSession,
            *,
            target_url: str | None = None,
        ) -> AeatLoginAssertion:
            return AeatLoginAssertion(
                target_url=target_url or "https://example.invalid/",
                is_valid=True,
                provider_kind=session.provider_kind,
                identity_nif=session.identity_nif,
                status_code=200,
                elapsed_ms=1,
                attempted_at=datetime.now(UTC),
                assertion_detail=ClaveMovilLoginAssertionDetail(session_cookie_present=True),
            )

        def describe(self) -> AuthProviderDescription:
            return AuthProviderDescription(
                kind=self.kind,
                label="Null provider",
                configured=True,
                available=True,
                identity_nif="X1234567L",
            )

    provider = _NullAuthProvider()
    assert isinstance(provider, AuthProvider)


def test_select_provider_returns_certificate_provider(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    provider = select_provider(AuthProviderKind.CERTIFICATE, settings=settings)

    assert isinstance(provider, AeatAuthenticator)
    assert isinstance(provider, AuthProvider)
