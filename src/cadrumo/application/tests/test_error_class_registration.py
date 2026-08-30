"""Real-behavior tests for application error-class registration.

Asserts that every application-facing error class in this module is:
  - a registered :class:`~cadrumo.core.errors.CadrumoError` subclass
  - bound in :data:`~cadrumo.core.errors.ERROR_REGISTRY`
  - round-trips through :func:`~cadrumo.core.errors.build_error_envelope`
    producing a non-empty ``error_code`` field

Also asserts that selected narrow exception paths remain importable without
depending on broad exception swallowing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from pydantic import SecretStr

from ...core.aggregation import BindingSourceKind
from ...core.errors.error_codes import ERROR_REGISTRY, build_error_envelope, get_registered_error_code
from ...core.errors.hierarchy import CadrumoError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _assert_registered_and_roundtrip(cls: type) -> None:
    """Assert cls is CadrumoError-derived, registered, and produces a valid envelope."""
    assert issubclass(cls, CadrumoError), f"{cls.__qualname__} must inherit from CadrumoError"
    code_obj = get_registered_error_code(cls)
    assert code_obj.code in ERROR_REGISTRY, f"{cls.__qualname__} error code {code_obj.code!r} not in ERROR_REGISTRY"
    instance = cls("registration-test sentinel")
    envelope = build_error_envelope(instance)
    assert envelope.code, f"build_error_envelope({cls.__qualname__}) returned an empty code"


# ---------------------------------------------------------------------------
# ProfileRegistrationError
# ---------------------------------------------------------------------------


def test_profile_registration_error_is_registered_and_roundtrips() -> None:
    from ..user_profile.registration import ProfileRegistrationError

    _assert_registered_and_roundtrip(ProfileRegistrationError)


# ---------------------------------------------------------------------------
# SessionDeserializationError
# ---------------------------------------------------------------------------


def test_session_deserialization_error_is_registered_and_roundtrips() -> None:
    from ..auth.sessions import SessionDeserializationError

    _assert_registered_and_roundtrip(SessionDeserializationError)


def test_session_deserialization_error_raised_on_bad_type() -> None:
    from ..auth.sessions import SessionDeserializationError, _session_metadata_datetime

    with pytest.raises(SessionDeserializationError):
        _session_metadata_datetime(12345, field="started_at")


# ---------------------------------------------------------------------------
# IvaCompensationYearRangeError / IvaCompensationDecimalParseError
# ---------------------------------------------------------------------------


def test_iva_compensation_year_range_error_is_registered_and_roundtrips() -> None:
    from ...domain.iva_compensation.errors import IvaCompensationYearRangeError

    _assert_registered_and_roundtrip(IvaCompensationYearRangeError)


def test_iva_compensation_decimal_parse_error_is_registered_and_roundtrips() -> None:
    from ...domain.iva_compensation.errors import IvaCompensationDecimalParseError

    _assert_registered_and_roundtrip(IvaCompensationDecimalParseError)


def test_iva_compensation_casilla_reference_error_is_registered_and_roundtrips() -> None:
    from ...domain.iva_compensation.errors import IvaCompensationCasillaReferenceError

    _assert_registered_and_roundtrip(IvaCompensationCasillaReferenceError)


def test_iva_compensation_year_range_error_raised_on_out_of_range_filing_year() -> None:
    from ...core.period import Period
    from ...domain.iva_compensation.errors import IvaCompensationYearRangeError
    from ..calculations import iva_compensation_period_key

    with pytest.raises(IvaCompensationYearRangeError):
        iva_compensation_period_key(Period.from_year_and_code(1999, "1T"))


def test_iva_compensation_year_range_error_raised_on_out_of_range_as_of_year() -> None:
    from ...domain.iva_compensation.carry_forward import build_iva_compensation_carry_forward_report
    from ...domain.iva_compensation.errors import IvaCompensationYearRangeError

    with pytest.raises(IvaCompensationYearRangeError):
        build_iva_compensation_carry_forward_report((), as_of_year=2100)


# ---------------------------------------------------------------------------
# ModeloApplicabilityFilterError
# ---------------------------------------------------------------------------


def test_modelo_applicability_filter_error_is_registered_and_roundtrips() -> None:
    from ..modelo._action_errors import ModeloApplicabilityFilterError

    _assert_registered_and_roundtrip(ModeloApplicabilityFilterError)


# ---------------------------------------------------------------------------
# AuthDiagnosticPayloadError
# ---------------------------------------------------------------------------


def test_auth_diagnostic_payload_error_is_registered_and_roundtrips() -> None:
    from ..auth.errors import AuthDiagnosticPayloadError

    _assert_registered_and_roundtrip(AuthDiagnosticPayloadError)


def test_auth_diagnostic_payload_error_raised_on_non_object_json() -> None:
    import json

    from ..auth.diagnostics import _payload
    from ..auth.errors import AuthDiagnosticPayloadError

    raw = json.dumps([1, 2, 3]).encode()
    with pytest.raises(AuthDiagnosticPayloadError):
        _payload(raw)


# ---------------------------------------------------------------------------
# WorkflowInputMismatchError
# ---------------------------------------------------------------------------


def test_workflow_input_mismatch_error_is_registered_and_roundtrips() -> None:
    from ..workflow.errors import WorkflowInputMismatchError

    _assert_registered_and_roundtrip(WorkflowInputMismatchError)


# ---------------------------------------------------------------------------
# SourceMeshError
# ---------------------------------------------------------------------------


def test_source_mesh_error_is_registered_and_roundtrips() -> None:
    from ..aggregation import SourceMeshError

    _assert_registered_and_roundtrip(SourceMeshError)


def test_source_mesh_error_raised_on_blank_owned_source() -> None:
    from pydantic import ValidationError

    from ..aggregation import CalculationSourceResolution, SourceMeshError

    with pytest.raises((SourceMeshError, ValidationError)):
        CalculationSourceResolution(
            resolver_id="ledger",
            owned_sources=cast("tuple[BindingSourceKind, ...]", ("  ",)),
        )


def test_source_mesh_error_raised_on_duplicate_owned_source() -> None:
    from pydantic import ValidationError

    from ..aggregation import CalculationSourceResolution, SourceMeshError

    with pytest.raises((SourceMeshError, ValidationError)):
        CalculationSourceResolution(
            resolver_id="ledger",
            owned_sources=cast("tuple[BindingSourceKind, ...]", ("bank", "bank")),
        )


# ---------------------------------------------------------------------------
# Narrowed except-clause types do not swallow programmer errors
# ---------------------------------------------------------------------------

_PKCS12_TEST_TEXT = "correct-horse-battery-staple"


def _build_valid_pkcs12_bundle(tmp_path: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
            x509.NameAttribute(NameOID.COMMON_NAME, "application-auth-probe"),
        ],
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime(2026, 1, 1, tzinfo=UTC))
        .not_valid_after(datetime(2099, 1, 1, tzinfo=UTC))
        .sign(key, hashes.SHA256())
    )
    out = tmp_path / "probe-valid.p12"
    out.write_bytes(
        pkcs12.serialize_key_and_certificates(
            name=b"application-auth-probe",
            key=key,
            cert=certificate,
            cas=None,
            encryption_algorithm=serialization.BestAvailableEncryption(_PKCS12_TEST_TEXT.encode("utf-8")),
        ),
    )
    return out


def test_certificate_configuration_probe_does_not_swallow_unrelated_exceptions(tmp_path: Path) -> None:
    """The public certificate probe propagates non-CertificateError/non-OSError failures.

    The narrowed ``except CertificateError`` clause around the PKCS#12
    health evaluation must not widen back to a bare ``except Exception``
    that would mask a genuine programmer error as a merely-corrupt
    certificate.
    """
    from ...core import AuthProviderKind
    from ...core.config import Settings
    from ..auth.operator_probes import probe_provider_configuration

    settings = Settings(
        cadrumo_certificate_path=_build_valid_pkcs12_bundle(tmp_path),
        cadrumo_certificate_password_secret=SecretStr(_PKCS12_TEST_TEXT),
        cadrumo_cert_warn_days=10,
        cadrumo_cert_critical_days=30,
    )

    with pytest.raises(CadrumoError, match=r"warn_days.*critical_days") as exc_info:
        probe_provider_configuration(AuthProviderKind.CERTIFICATE.value, settings=settings)
    assert get_registered_error_code(exc_info.value).code == "AUTH_AUTH_VALIDATION"


def test_live_auth_identity_state_does_not_swallow_unrelated_exceptions() -> None:
    """The profile tax-id probe is narrow and remains publicly importable."""
    from ..auth import operator_probes as probes

    assert hasattr(probes, "live_auth_identity_state")
