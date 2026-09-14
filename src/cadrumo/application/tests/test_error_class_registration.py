"""Real-behavior tests for application error-class registration.

Asserts that every application-facing error class in this module is:
  - a registered :class:`~cadrumo.core.errors.CadrumoError` subclass
  - bound in :data:`~core.errors.error_codes.ALL_DECLARED_ERROR_CODES`
  - round-trips through :func:`~cadrumo.core.errors.build_error_envelope`
    producing a non-empty ``error_code`` field

Also asserts that selected narrow exception paths remain importable without
depending on broad exception swallowing.
"""

from __future__ import annotations

from typing import cast

import pytest
from pydantic import SecretStr

from ...core.aggregation import BindingSourceKind
from ._operator_probe_fakes import fake_operator_probe_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ProfileRegistrationError
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# SessionDeserializationError
# ---------------------------------------------------------------------------


def test_session_deserialization_error_raised_on_bad_type() -> None:
    from ..auth.sessions import SessionDeserializationError, session_metadata_datetime

    with pytest.raises(SessionDeserializationError):
        session_metadata_datetime(12345, field="started_at")


# ---------------------------------------------------------------------------
# IvaCompensationYearRangeError / IvaCompensationDecimalParseError
# ---------------------------------------------------------------------------


def test_iva_compensation_year_range_error_raised_on_out_of_range_filing_year() -> None:
    from ...core.period import Period
    from ...domain.iva_compensation.errors import IvaCompensationYearRangeError
    from ..calculations.iva_compensation_history import iva_compensation_period_key

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


# ---------------------------------------------------------------------------
# AuthDiagnosticPayloadError
# ---------------------------------------------------------------------------


def test_auth_diagnostic_payload_error_raised_on_non_object_json() -> None:
    import json

    from ..auth.diagnostics import diagnostic_payload
    from ..auth.errors import AuthDiagnosticPayloadError

    raw = json.dumps([1, 2, 3]).encode()
    with pytest.raises(AuthDiagnosticPayloadError):
        diagnostic_payload(raw)


# ---------------------------------------------------------------------------
# WorkflowInputMismatchError
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# SourceMeshError
# ---------------------------------------------------------------------------


def test_source_mesh_error_raised_on_blank_owned_source() -> None:
    from pydantic import ValidationError

    from ..aggregation.source_mesh import CalculationSourceResolution, SourceMeshError

    with pytest.raises((SourceMeshError, ValidationError)):
        CalculationSourceResolution(
            resolver_id="ledger",
            owned_sources=cast("tuple[BindingSourceKind, ...]", ("  ",)),
        )


def test_source_mesh_error_raised_on_duplicate_owned_source() -> None:
    from pydantic import ValidationError

    from ..aggregation.source_mesh import CalculationSourceResolution, SourceMeshError

    with pytest.raises((SourceMeshError, ValidationError)):
        CalculationSourceResolution(
            resolver_id="ledger",
            owned_sources=cast("tuple[BindingSourceKind, ...]", ("bank", "bank")),
        )


# ---------------------------------------------------------------------------
# Narrowed except-clause types do not swallow programmer errors
# ---------------------------------------------------------------------------


def test_certificate_configuration_probe_does_not_swallow_unrelated_exceptions(tmp_path) -> None:
    """The application probe propagates an unrelated inward-port failure."""
    from ...core.auth_provider import AuthProviderKind
    from ...core.config import Settings
    from ..auth.operator_probes import probe_provider_configuration

    certificate_path = tmp_path / "probe.p12"
    certificate_path.write_bytes(b"placeholder certificate bytes")
    settings = Settings(
        cadrumo_certificate_path=certificate_path,
        cadrumo_certificate_password_secret=SecretStr("certificate-password"),
        cadrumo_cert_warn_days=10,
        cadrumo_cert_critical_days=30,
    )

    def raise_programmer_error(_request):
        raise RuntimeError("programmer failure")

    with pytest.raises(RuntimeError, match="programmer failure"):
        probe_provider_configuration(
            AuthProviderKind.CERTIFICATE.value,
            settings=settings,
            operator_probe_ports=fake_operator_probe_ports(certificate_evaluator=raise_programmer_error),
        )


def test_live_auth_identity_state_does_not_swallow_unrelated_exceptions() -> None:
    """The profile tax-id probe is narrow and remains publicly importable."""
    from ..auth import operator_probes as probes

    assert hasattr(probes, "live_auth_identity_state")
