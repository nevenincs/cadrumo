"""calc_sheets error hierarchy and bucket/google-auth MRO invariants.

Verifies:
- calc_sheets cluster error classes are AeatError subclasses with distinct
  registered error codes.
- calc_sheets errors envelope-roundtrip through ErrorEnvelope.
- BucketValidationError and GoogleAuthValidationError no longer leak
  ValueError from their MRO.
"""

from __future__ import annotations

import pytest

from ..adapters.outbound.google._errors import (
    GoogleAuthError,
    GoogleAuthValidationError,
)
from ..adapters.persistence.storage.bucket._errors import (
    BucketError,
    BucketValidationError,
)
from ..application.storage.calc_sheets._errors import (
    CalcSheetsEngineError,
    CalcSheetsParityError,
    CalcSheetsRecordError,
)
from ..core.errors import AeatError, build_error_envelope
from ..core.errors._registry import ErrorEnvelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


# ---------------------------------------------------------------------------
# calc_sheets error class hierarchy
# ---------------------------------------------------------------------------


def test_calc_sheets_engine_error_is_aeat_error() -> None:
    assert issubclass(CalcSheetsEngineError, AeatError)


def test_calc_sheets_record_error_is_aeat_error() -> None:
    assert issubclass(CalcSheetsRecordError, AeatError)


def test_calc_sheets_parity_error_is_aeat_error() -> None:
    assert issubclass(CalcSheetsParityError, AeatError)


# ---------------------------------------------------------------------------
# calc_sheets error code registration and envelope roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error_cls,expected_code",
    [
        (CalcSheetsEngineError, "ERROR_CALC_SHEETS_ENGINE"),
        (CalcSheetsRecordError, "ERROR_CALC_SHEETS_RECORD"),
        (CalcSheetsParityError, "ERROR_CALC_SHEETS_PARITY"),
    ],
)
def test_calc_sheets_error_code_registered(error_cls: type[AeatError], expected_code: str) -> None:
    """Each calc_sheets error must be bound to its declared ErrorCode."""
    from ..core.errors import get_registered_error_code

    ec = get_registered_error_code(error_cls)
    assert ec is not None, f"{error_cls.__name__} has no registered ErrorCode"
    assert ec.code == expected_code


@pytest.mark.parametrize(
    "instance",
    [
        CalcSheetsEngineError("unsupported rounding code 'bad'"),
        CalcSheetsRecordError("column index must be 1-based"),
        CalcSheetsParityError("unknown casilla ids [999]"),
    ],
)
def test_calc_sheets_error_envelope_roundtrip(instance: AeatError) -> None:
    """Envelope construction and JSON roundtrip must not raise."""
    envelope = build_error_envelope(instance)
    assert isinstance(envelope, ErrorEnvelope)
    json_bytes = envelope.model_dump_json()
    reloaded = ErrorEnvelope.model_validate_json(json_bytes)
    assert reloaded == envelope


# ---------------------------------------------------------------------------
# MRO does not leak ValueError
# ---------------------------------------------------------------------------


def test_bucket_validation_error_mro_does_not_include_value_error() -> None:
    """BucketValidationError must not inherit ValueError."""
    assert not issubclass(BucketValidationError, ValueError)
    assert issubclass(BucketValidationError, BucketError)
    assert issubclass(BucketValidationError, AeatError)


def test_google_auth_validation_error_mro_does_not_include_value_error() -> None:
    """GoogleAuthValidationError must not inherit ValueError."""
    assert not issubclass(GoogleAuthValidationError, ValueError)
    assert issubclass(GoogleAuthValidationError, GoogleAuthError)
    assert issubclass(GoogleAuthValidationError, AeatError)
