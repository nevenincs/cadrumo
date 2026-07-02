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


def test_calc_sheets_error_is_aeat_error() -> None:
    for error_cls in (
        CalcSheetsEngineError,
        CalcSheetsRecordError,
        CalcSheetsParityError,
    ):
        assert issubclass(error_cls, AeatError)


# ---------------------------------------------------------------------------
# calc_sheets error code registration and envelope roundtrip
# ---------------------------------------------------------------------------


def test_calc_sheets_error_code_registered() -> None:
    """Each calc_sheets error must be bound to its declared ErrorCode."""
    from ..core.errors import get_registered_error_code

    cases: tuple[tuple[type[AeatError], str], ...] = (
        (CalcSheetsEngineError, "ERROR_CALC_SHEETS_ENGINE"),
        (CalcSheetsRecordError, "ERROR_CALC_SHEETS_RECORD"),
        (CalcSheetsParityError, "ERROR_CALC_SHEETS_PARITY"),
    )

    for error_cls, expected_code in cases:
        ec = get_registered_error_code(error_cls)
        assert ec is not None, f"{error_cls.__name__} has no registered ErrorCode"
        assert ec.code == expected_code


def test_calc_sheets_error_envelope_roundtrip() -> None:
    """Envelope construction and JSON roundtrip must not raise."""
    instances: tuple[AeatError, ...] = (
        CalcSheetsEngineError("unsupported rounding code 'bad'"),
        CalcSheetsRecordError("column index must be 1-based"),
        CalcSheetsParityError("unknown casilla ids [999]"),
    )

    for instance in instances:
        envelope = build_error_envelope(instance)
        assert isinstance(envelope, ErrorEnvelope)
        json_bytes = envelope.model_dump_json()
        reloaded = ErrorEnvelope.model_validate_json(json_bytes)
        assert reloaded == envelope


# ---------------------------------------------------------------------------
# MRO does not leak ValueError
# ---------------------------------------------------------------------------


def test_validation_error_mro_does_not_include_value_error() -> None:
    cases: tuple[tuple[type[AeatError], type[AeatError]], ...] = (
        (BucketValidationError, BucketError),
        (GoogleAuthValidationError, GoogleAuthError),
    )

    for error_cls, base_cls in cases:
        assert not issubclass(error_cls, ValueError), error_cls
        assert issubclass(error_cls, base_cls), error_cls
        assert issubclass(error_cls, AeatError), error_cls
