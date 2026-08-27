"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

import logging
from datetime import timezone

import pytest
from pydantic import ValidationError

from ......application.auth.session_types import (
    ClaveMovilSessionDetail,
    ClavePermanenteSessionDetail,
    is_exact_active_provider_session,
)
from ......core.errors import AeatLoginAssertionError
from ......core.i18n import tr
from .. import authenticator as authenticator
from ..authenticator import _require_exact_active_certificate_session
from ..errors import AuthConfigurationError
from ._authenticator_support import (
    _SENSITIVE_HEALTH_PAYLOAD,
    _SENSITIVE_STORAGE_BASENAME,
    AEAT_SESSION_IDLE_TTL,
    SECRET_PASSPHRASE,
    UTC,
    AeatAuthenticator,
    AeatLoginAssertion,
    AeatSession,
    AuthProvider,
    AuthProviderKind,
    AuthValidationError,
    CertificateError,
    CertificateNifParseError,
    NameOID,
    NoReturn,
    Path,
    _build_bundle,
    _certificate_assertion,
    _certificate_session,
    _load_cert,
    datetime,
    extract_nif_from_subject,
    select_provider,
    timedelta,
    unnamed_certificate_credentials,
    x509,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_exact_active_certificate_session_guard_rejects_copies_and_other_providers() -> None:
    current = datetime.now(UTC)
    active = _certificate_session(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        thumbprint="active-thumbprint",
        subject="CN=ACTIVE,SERIALNUMBER=12345678Z",
    )

    _require_exact_active_certificate_session(active, active)
    with pytest.raises(AeatLoginAssertionError, match="exact active certificate-bound session"):
        _require_exact_active_certificate_session(active.model_copy(), active)

    wrong_provider = AeatSession(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=ClaveMovilSessionDetail(dni_nie="12345678Z"),
    )
    with pytest.raises(AeatLoginAssertionError, match="exact active certificate-bound session"):
        _require_exact_active_certificate_session(wrong_provider, wrong_provider)


@pytest.mark.parametrize(
    ("kind", "detail"),
    [
        (AuthProviderKind.CLAVE_MOVIL, ClaveMovilSessionDetail(dni_nie="12345678Z")),
        (AuthProviderKind.CLAVE_PERMANENTE, ClavePermanenteSessionDetail(dni_nie="12345678Z")),
    ],
)
def test_exact_active_provider_session_predicate_rejects_equal_reconstructions(
    kind: AuthProviderKind,
    detail: ClaveMovilSessionDetail | ClavePermanenteSessionDetail,
) -> None:
    """Only the retained provider session object is browser-context-bound."""
    current = datetime.now(UTC)
    active = AeatSession(
        authenticated_at=current,
        idle_deadline=current + AEAT_SESSION_IDLE_TTL,
        storage_state_path=None,
        identity_nif="12345678Z",
        provider_detail=detail,
    )

    assert is_exact_active_provider_session(
        active,
        active,
        provider_kind=kind,
        detail_type=type(detail),
    )
    assert not is_exact_active_provider_session(
        active.model_copy(),
        active,
        provider_kind=kind,
        detail_type=type(detail),
    )


def test_extract_nif_from_serial_with_idces_prefix(tmp_path: Path) -> None:
    cert = _load_cert(tmp_path)
    assert extract_nif_from_subject(cert) == "12345678Z"


def test_extract_nif_from_bare_serial(tmp_path: Path) -> None:
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "ANYBODY"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "87654321X"),
        ],
    )
    assert extract_nif_from_subject(cert) == "87654321X"


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
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO - 22334455Y"),
        ],
    )
    assert extract_nif_from_subject(cert) == "22334455Y"


def test_extract_nif_rejects_checksum_invalid_serial(tmp_path: Path) -> None:
    """A serialNumber with a DNI shape but the wrong checksum letter is not accepted.

    ``12345678`` checksums to ``Z``, so ``12345678A`` is a shape no real FNMT
    subject carries. The shape-only gate returned it as the taxpayer identity.
    """
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678A"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NO-NIF-HERE"),
        ],
    )
    with pytest.raises(CertificateNifParseError, match=r"NIF|subject|certificate"):
        extract_nif_from_subject(cert)


def test_extract_nif_skips_checksum_invalid_serial_and_falls_back_to_cn(tmp_path: Path) -> None:
    """A checksum-invalid serialNumber is skipped, not fatal: the CN still resolves."""
    cert = _load_cert(
        tmp_path,
        subject_attrs=[
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678A"),
            x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO - 22334455Y"),
        ],
    )
    assert extract_nif_from_subject(cert) == "22334455Y"


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


def test_aeat_session_provider_kind_is_derived_not_stored() -> None:
    """Session detail is the sole provider-kind authority across roundtrip."""
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )

    payload = session.model_dump()

    assert session.provider_kind is AuthProviderKind.CERTIFICATE
    assert "provider_kind" not in AeatSession.model_fields
    assert "provider_kind" not in payload
    assert AeatSession.model_validate(payload) == session
    assert AeatSession.model_validate_json(session.model_dump_json()) == session
    with pytest.raises(ValidationError, match="provider_kind"):
        AeatSession.model_validate({**payload, "provider_kind": AuthProviderKind.CERTIFICATE})


def test_aeat_login_assertion_provider_kind_is_derived_not_stored() -> None:
    """Assertion detail is the sole provider-kind authority across roundtrip."""
    assertion = _certificate_assertion()

    payload = assertion.model_dump()

    assert assertion.provider_kind is AuthProviderKind.CERTIFICATE
    assert "provider_kind" not in AeatLoginAssertion.model_fields
    assert "provider_kind" not in payload
    assert AeatLoginAssertion.model_validate(payload) == assertion
    assert AeatLoginAssertion.model_validate_json(assertion.model_dump_json()) == assertion
    with pytest.raises(ValidationError, match="provider_kind"):
        AeatLoginAssertion.model_validate({**payload, "provider_kind": AuthProviderKind.CERTIFICATE})


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
    auth = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )
    storage_state_path = tmp_path / _SENSITIVE_STORAGE_BASENAME

    caplog.set_level(logging.INFO, logger=authenticator.__name__)
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
    settings = _settings_factory(bundle_path, cadrumo_certificate_password_secret=None)
    description = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ).describe()

    assert description.configured is True
    assert description.available is False
    assert description.health_summary == "CADRUMO_CERTIFICATE_PASSWORD_SECRET not set"


def test_describe_preserves_expired_certificate_severity(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(
        tmp_path,
        not_valid_after=datetime.now(UTC) - timedelta(hours=12),
    )
    settings = _settings_factory(bundle_path)
    description = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ).describe()

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

    caplog.set_level(logging.DEBUG, logger=authenticator.__name__)
    description = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
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

    caplog.set_level(logging.DEBUG, logger=authenticator.__name__)
    with pytest.raises(AuthValidationError) as exc_info:
        AeatAuthenticator(
            settings,
            credentials=unnamed_certificate_credentials(settings),
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


def test_describe_forwards_typed_bundle_and_friendly_name(
    tmp_path: Path,
    _settings_factory,
) -> None:
    bundle_path = _build_bundle(tmp_path)
    from pydantic import SecretStr

    settings = _settings_factory(bundle_path, cadrumo_certificate_friendly_name="operator cert")

    captured: dict[str, object] = {}
    real_certificate_health = authenticator.certificate_health

    def _capture_certificate_health(
        path: Path,
        *,
        password: SecretStr,
        warn_days: int,
        critical_days: int,
        friendly_name: str | None = None,
        now: datetime | None = None,
    ):
        captured["path"] = path
        captured["password"] = password
        captured["warn_days"] = warn_days
        captured["critical_days"] = critical_days
        captured["friendly_name"] = friendly_name
        return real_certificate_health(
            path,
            password=password,
            warn_days=warn_days,
            critical_days=critical_days,
            friendly_name=friendly_name,
            now=now,
        )

    description = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
        certificate_health_check=_capture_certificate_health,
    ).describe()

    assert description.available is True
    assert captured["path"] == bundle_path
    captured_password = captured["password"]
    assert isinstance(captured_password, SecretStr)
    assert captured_password.get_secret_value() == SECRET_PASSPHRASE
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

    description = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    ).describe()
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


def test_extract_nif_from_multi_valued_rdn(tmp_path: Path) -> None:
    """A genuine multi-valued RDN (``CN=X+SERIALNUMBER=Y``) yields the NIF.

    Distinct from the escaped-``+`` case above: here CN and serialNumber are
    two attributes of ONE relative distinguished name joined by an unescaped
    ``+``, so ``cert.subject`` round-trips as ``...+SERIALNUMBER=...``. The
    parser resolves the serialNumber via
    :meth:`cryptography.x509.Name.get_attributes_for_oid`, which a naive
    ``,``/``+`` split could not.
    """
    subject_name = x509.Name(
        [
            x509.RelativeDistinguishedName(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, "NOMBRE APELLIDO1 APELLIDO2"),
                    x509.NameAttribute(NameOID.SERIAL_NUMBER, "12345678Z"),
                ]
            ),
        ]
    )
    cert = _load_cert(tmp_path, subject_name=subject_name)
    assert "+" in cert.subject
    assert extract_nif_from_subject(cert) == "12345678Z"


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


def test_aeat_session_is_stale_with_aware_non_utc_datetime(tmp_path: Path) -> None:
    """Timezone-aware non-UTC datetimes are converted before comparison.

    Exercises the ``astimezone`` branch of ``coerce_utc_aware`` through
    ``is_stale``: the same instant expressed in a ``+05:00`` offset must
    compare identically to its UTC form, so the offset cannot flip the
    staleness verdict.
    """
    authenticated_at = datetime.now(UTC)
    session = _certificate_session(
        authenticated_at=authenticated_at,
        idle_deadline=authenticated_at + AEAT_SESSION_IDLE_TTL,
    )
    plus_five = timezone(timedelta(hours=5))
    aware_before = authenticated_at.astimezone(plus_five)
    aware_after = (authenticated_at + AEAT_SESSION_IDLE_TTL + timedelta(hours=1)).astimezone(plus_five)
    assert aware_before.utcoffset() == timedelta(hours=5)
    assert session.is_stale(aware_before) is False
    assert session.is_stale(aware_after) is True


@pytest.mark.asyncio
async def test_resolve_browser_session_without_factory_raises_configuration_error(
    tmp_path: Path,
    _settings_factory,
) -> None:
    """A missing browser-session factory is a configuration refusal, not a login assertion.

    ``_resolve_browser_session`` guards the async entry points; with no factory
    injected and the default Playwright factory unwired, it must raise the
    configuration-taxonomy error rather than ``AeatLoginAssertionError`` (which
    denotes a produced-but-untrusted login assertion).
    """
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)
    authenticator = AeatAuthenticator(
        settings,
        credentials=unnamed_certificate_credentials(settings),
    )

    with pytest.raises(AuthConfigurationError, match=r"browser.*session factory") as exc_info:
        await authenticator._resolve_browser_session()
    # The refusal must not be classified as a login-assertion failure.
    assert not isinstance(exc_info.value, AeatLoginAssertionError)


def test_auth_provider_protocol_conformance(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    providers = tuple(
        select_provider(
            kind,
            settings=settings,
            certificate_credentials=unnamed_certificate_credentials(settings),
        )
        for kind in AuthProviderKind
    )

    assert {provider.kind for provider in providers} == set(AuthProviderKind)
    assert all(isinstance(provider, AuthProvider) for provider in providers)


def test_select_provider_returns_certificate_provider(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    provider = select_provider(
        AuthProviderKind.CERTIFICATE,
        settings=settings,
        certificate_credentials=unnamed_certificate_credentials(settings),
    )

    assert isinstance(provider, AeatAuthenticator)
    assert isinstance(provider, AuthProvider)
    assert callable(provider.verify)
    assert not hasattr(provider, "verify_login")


def test_outbound_certificate_factory_requires_typed_credentials(tmp_path: Path, _settings_factory) -> None:
    bundle_path = _build_bundle(tmp_path)
    settings = _settings_factory(bundle_path)

    with pytest.raises(AuthConfigurationError, match="ActiveCertificateCredentials"):
        select_provider(AuthProviderKind.CERTIFICATE, settings=settings)
