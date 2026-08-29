"""Tests for LedgerClassificationRule construction and ClassificationRuleError registry binding."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.errors import ERROR_REGISTRY, build_error_envelope, get_registered_error_code
from ..classification_rule import LedgerClassificationRule
from .._enums import BusinessClassification
from ..errors import ClassificationRuleError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_classification_rule_error_contract() -> None:
    code = get_registered_error_code(ClassificationRuleError)
    assert code is not None
    assert code.code in ERROR_REGISTRY
    assert issubclass(ClassificationRuleError, ValueError)
    exc = ClassificationRuleError("description_pattern is not a valid regex: unterminated")
    envelope = build_error_envelope(exc, trace_id=None)
    assert envelope.code == "ERROR_TRANSACTION_CLASSIFICATION_RULE"
    assert envelope.retryable is False


def test_invalid_regex_raises_classification_rule_error() -> None:
    """ClassificationRuleError is raised by the validator; Pydantic wraps it in ValidationError.

    The underlying cause is verified to be ClassificationRuleError so that the
    domain error identity is preserved through the Pydantic validation boundary.
    """
    with pytest.raises(ValidationError) as exc_info:
        LedgerClassificationRule.create(
            description_pattern="[invalid(regex",
            classification=BusinessClassification.BUSINESS,
            actor="test-actor",
        )
    errors = exc_info.value.errors()
    assert len(errors) == 1
    assert errors[0]["type"] == "value_error"
    assert "description_pattern is not a valid regex" in errors[0]["msg"]
    # The raw exception surfaced by Pydantic is the ClassificationRuleError itself.
    assert isinstance(exc_info.value.errors()[0].get("ctx", {}).get("error"), ClassificationRuleError)


def test_valid_regex_does_not_raise() -> None:
    rule = LedgerClassificationRule.create(
        description_pattern=r"AMAZON\s+\d+",
        classification=BusinessClassification.BUSINESS,
        actor="test-actor",
    )
    assert rule.description_pattern == r"AMAZON\s+\d+"
