"""The unaccepted-registry-value refusal is registered and renders in every supported locale."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.errors.error_codes import ErrorCategory, build_error_envelope, resolve_error_message
from ..errors import UnacceptedLedgerRegistryValueError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _refusal() -> UnacceptedLedgerRegistryValueError:
    return UnacceptedLedgerRegistryValueError(
        field="concepto_ingreso",
        value="retired_concept",
        transaction_id="0123456789abcdef",
        effective_date=date(2026, 6, 30),
    )


def test_the_refusal_carries_its_registered_code_and_names_field_value_and_row() -> None:
    envelope = build_error_envelope(_refusal())

    assert envelope.code == "REFUSED_LEDGER_REGISTRY_VALUE_UNACCEPTED"
    assert envelope.category == ErrorCategory.REFUSED.value
    assert envelope.retryable is False
    assert envelope.context is not None
    assert envelope.context["field"] == "concepto_ingreso"
    assert envelope.context["value"] == "retired_concept"
    assert envelope.context["transaction_id"] == "0123456789abcdef"
    assert envelope.context["effective_date"] == "2026-06-30"


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_every_locale_renders_every_fact_into_the_sentence(locale: str) -> None:
    message = resolve_error_message(_refusal(), locale=locale)

    for fact in ("concepto_ingreso", "retired_concept", "0123456789abcdef", "2026-06-30"):
        assert fact in message, (locale, message)
    assert "%{" not in message
    assert "errors.refused" not in message
