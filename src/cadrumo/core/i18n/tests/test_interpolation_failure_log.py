"""A failed interpolation names its key and error type, never an interpolated value."""

from __future__ import annotations

import logging

import pytest

from ....tests.log_records import delivered_records, delivered_text
from ..render import UnmatchedPlaceholderError, tr

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RENDER_LOGGER = "cadrumo.core.i18n.render"
_PRIVATE_VALUE = "synthetic-private-password"
_PRIVATE_FORMAT_VALUE = "synthetic_private_value"


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
        record for record in delivered_records(caplog, _RENDER_LOGGER) if "unable to interpolate" in record.getMessage()
    ]
    assert "tests.i18n.synthetic_unformattable" in record.getMessage()
    assert "ValueError" in record.getMessage()
    assert record.exc_text is not None and "Traceback" in record.exc_text
    assert _PRIVATE_VALUE not in delivered_text(caplog)


@pytest.mark.parametrize(
    ("template", "values", "error_type"),
    [
        ("Value %{value}", {"value": "{" + _PRIVATE_FORMAT_VALUE + "}"}, "KeyError"),
        ("Value {value:{format_spec}}", {"value": "ordinary", "format_spec": _PRIVATE_FORMAT_VALUE}, "ValueError"),
    ],
)
def test_format_error_arguments_never_enter_diagnostics(
    caplog: pytest.LogCaptureFixture, template: str, values: dict[str, object], error_type: str
) -> None:
    """Private values reflected in formatter exceptions stay off every delivered record."""
    with caplog.at_level(logging.DEBUG, logger=_RENDER_LOGGER), pytest.raises(UnmatchedPlaceholderError):
        tr("tests.i18n.private_format_error", default=template, locale="en", **values)

    (record,) = [
        record for record in delivered_records(caplog, _RENDER_LOGGER) if "unable to interpolate" in record.getMessage()
    ]
    assert "tests.i18n.private_format_error" in record.getMessage()
    assert error_type in record.getMessage()
    assert record.exc_text is not None and "Traceback" in record.exc_text
    assert "_interpolate_with_status" in record.exc_text
    assert _PRIVATE_FORMAT_VALUE not in delivered_text(caplog)
