"""The bank statement's printed reference is private banking data that no log line or failure context names."""

from __future__ import annotations

import pytest

from ...log_scrubbing import scrub_text, scrub_value
from ..rules import is_sensitive_redaction_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REFERENCE = "0049-7731-REF-000184"


@pytest.mark.parametrize("key", ["statement_reference", "statementReference", "STATEMENT-REFERENCE"])
def test_the_statement_reference_key_is_sensitive_in_every_spelling(key: str) -> None:
    assert is_sensitive_redaction_key(key)


def test_a_log_line_naming_the_statement_reference_loses_its_value() -> None:
    scrubbed = scrub_text(f"import row statement_reference={_REFERENCE} rows=1")

    assert _REFERENCE not in scrubbed
    assert "rows=1" in scrubbed


def test_a_structured_log_field_holding_the_statement_reference_loses_its_value() -> None:
    scrubbed = scrub_value({"statement_reference": _REFERENCE, "rows": "1"})

    assert _REFERENCE not in str(scrubbed)
    assert scrubbed["rows"] == "1"
