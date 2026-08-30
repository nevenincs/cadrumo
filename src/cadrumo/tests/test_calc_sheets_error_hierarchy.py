"""calc_sheets error hierarchy and bucket/google-auth MRO invariants.

Verifies:
- calc_sheets cluster error classes are CadrumoError subclasses with distinct
  registered error codes.
- calc_sheets errors envelope-roundtrip through ErrorEnvelope.
- BucketValidationError and GoogleAuthValidationError no longer leak
  ValueError from their MRO.
"""

from __future__ import annotations

import pytest

from ..adapters.outbound.google.errors import GoogleAuthError, GoogleAuthValidationError
from ..adapters.persistence.storage.bucket import (
    BucketError,
    BucketValidationError,
)
from ..application.storage.calc_sheets import (
    CalcSheetsEngineError,
    CalcSheetsParityError,
    CalcSheetsRecordError,
)
from ..core.errors import CadrumoError, ErrorEnvelope, build_error_envelope, get_registered_error_code

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_CALC_SHEETS_ERROR_CASES: tuple[tuple[type[CadrumoError], str, CadrumoError], ...] = (
    (
        CalcSheetsEngineError,
        "ERROR_CALC_SHEETS_ENGINE",
        CalcSheetsEngineError("unsupported rounding code 'bad'"),
    ),
    (
        CalcSheetsRecordError,
        "ERROR_CALC_SHEETS_RECORD",
        CalcSheetsRecordError("column index must be 1-based"),
    ),
    (
        CalcSheetsParityError,
        "ERROR_CALC_SHEETS_PARITY",
        CalcSheetsParityError("unknown casilla ids [999]"),
    ),
)


@pytest.mark.parametrize(
    ("error_cls", "expected_code", "instance"),
    _CALC_SHEETS_ERROR_CASES,
    ids=lambda case: case.__name__ if isinstance(case, type) else str(case),
)
def test_calc_sheets_error_contracts_are_registered_and_serializable(
    error_cls: type[CadrumoError],
    expected_code: str,
    instance: CadrumoError,
) -> None:
    """Each calc_sheets error keeps its hierarchy, registry, and envelope contract."""
    assert issubclass(error_cls, CadrumoError), error_cls.__name__
    ec = get_registered_error_code(error_cls)
    assert ec is not None, f"{error_cls.__name__} has no registered ErrorCode"
    assert ec.code == expected_code
    envelope = build_error_envelope(instance)
    assert isinstance(envelope, ErrorEnvelope)
    json_text = envelope.model_dump_json()
    reloaded = ErrorEnvelope.model_validate_json(json_text)
    assert reloaded == envelope


# ---------------------------------------------------------------------------
# MRO does not leak ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("error_cls", "base_cls"),
    [
        (BucketValidationError, BucketError),
        (GoogleAuthValidationError, GoogleAuthError),
    ],
)
def test_validation_error_mro_does_not_include_value_error(
    error_cls: type[CadrumoError],
    base_cls: type[CadrumoError],
) -> None:
    assert not issubclass(error_cls, ValueError), error_cls
    assert issubclass(error_cls, base_cls), error_cls
    assert issubclass(error_cls, CadrumoError), error_cls
