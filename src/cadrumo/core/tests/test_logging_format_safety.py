"""Redacted operands remain compatible with stdlib logging conversions."""

from __future__ import annotations

import io
import logging

import pytest

from ..logging import SecretScrubbingFilter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("message", "args", "expected"),
    [
        (
            "input_tokens=%d output_tokens=%d count=%04d elapsed=%.2f",
            (321, 12, 7, 1.25),
            "input_tokens=<redacted> output_tokens=<redacted> count=0007 elapsed=1.25",
        ),
        ("token=%08x count=%d", (0xCAFE, 7), "token=<redacted> count=7"),
        ("credential=%.*f elapsed=%*.2f", (3, 123.456, 6, 1.25), "credential=<redacted> elapsed=  1.25"),
        ("cookie=%*.*s count=%d", (12, 3, "CANARY-COOKIE", 7), "cookie=<redacted> count=7"),
        ("literal=%%s token=%d count=%d", (123, 7), "literal=%s token=<redacted> count=7"),
        ("token=%%s count=%d", (7,), "token=<redacted> count=7"),
        ("token=%c count=%d", (65, 7), "token=<redacted> count=7"),
        (
            "token=%(token)08d count=%(count)04d elapsed=%(elapsed).2f",
            ({"token": 123, "count": 7, "elapsed": 1.25},),
            "token=<redacted> count=0007 elapsed=1.25",
        ),
        (
            "count=%(value)d credential=%(value).2f repeated=%(value)d",
            ({"value": 123},),
            "count=<redacted> credential=<redacted> repeated=<redacted>",
        ),
        (
            "credential=%(value)d count=%(count)d literal=%%d",
            ({"value": 123, "count": 7},),
            "credential=<redacted> count=7 literal=%d",
        ),
        (
            "payload=%s count=%d",
            ({"token": 123, "region": "es"}, 7),
            "payload={'token': '<redacted>', 'region': 'es'} count=7",
        ),
    ],
)
def test_redaction_preserves_formatting_across_two_real_handlers(
    message: str, args: tuple[object, ...], expected: str
) -> None:
    """Repeated handler filters emit the same safe, fully formatted message."""
    record = logging.LogRecord("cadrumo.format-contract", logging.INFO, __file__, 1, message, args, None)
    outputs = [io.StringIO(), io.StringIO()]
    for output in outputs:
        handler = logging.StreamHandler(output)
        handler.addFilter(SecretScrubbingFilter())
        handler.handle(record)

    assert [output.getvalue() for output in outputs] == [expected + "\n", expected + "\n"]


def test_a_non_sensitive_invalid_numeric_operand_retains_stdlib_refusal() -> None:
    """Scrubbing does not make an invalid ordinary diagnostic format valid."""
    record = logging.LogRecord("cadrumo.format-contract", logging.INFO, __file__, 1, "count=%d", ("invalid",), None)

    SecretScrubbingFilter().filter(record)

    with pytest.raises(TypeError):
        record.getMessage()
