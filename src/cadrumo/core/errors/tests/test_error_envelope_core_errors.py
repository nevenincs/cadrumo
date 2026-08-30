import pytest

from ..error_codes import build_error_envelope
from ..hierarchy import DecimalFormatError, RedactionError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("error", "expected_code"),
    (
        (DecimalFormatError("test decimal format"), "ERROR_DECIMAL_FORMAT"),
        (RedactionError("test redaction error"), "ERROR_REDACTION"),
    ),
)
def test_error_envelope_roundtrip_for_core_error_classes(error: Exception, expected_code: str) -> None:
    envelope = build_error_envelope(error)

    assert envelope.code == expected_code
    assert envelope.message
