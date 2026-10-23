"""A failed interpolation names its key and error type, never an interpolated value."""

from __future__ import annotations

import logging

import pytest

from ..render import UnmatchedPlaceholderError, tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RENDER_LOGGER = "cadrumo.core.i18n.render"
_PRIVATE_VALUE = "synthetic-private-password"


def test_a_failed_format_logs_the_key_and_traceback_without_the_value(caplog: pytest.LogCaptureFixture) -> None:
    # Strict placeholder mode then refuses the partial rendering; the refusal names the template only.
    with caplog.at_level(logging.DEBUG, logger=_RENDER_LOGGER), pytest.raises(UnmatchedPlaceholderError) as refused:
        tr(
            "tests.i18n.synthetic_unformattable",
            default="Importe {amount:d}",
            locale="es",
            amount=_PRIVATE_VALUE,
        )

    assert _PRIVATE_VALUE not in str(refused.value)
    (record,) = [
        record
        for record in caplog.records
        if record.name == _RENDER_LOGGER and "unable to interpolate" in record.getMessage()
    ]
    assert "tests.i18n.synthetic_unformattable" in record.getMessage()
    assert "ValueError" in record.getMessage()
    assert record.exc_text is not None and "Traceback" in record.exc_text
    assert _PRIVATE_VALUE not in caplog.text
