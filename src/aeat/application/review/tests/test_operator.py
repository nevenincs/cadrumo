"""Tests for operator-facing review queue projections."""

from __future__ import annotations

import pytest

from ....application.user_profile._orchestration import profile_create_storage_span
from ....core.config import Settings, override_settings
from ....core.errors import resolve_error_message
from .._errors import ReviewError, ReviewKindReservedError
from .._operator import _resolve_internal_kinds, project_review_item

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_unknown_review_kind_error_omits_raw_operator_value() -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"

    with pytest.raises(ReviewError) as exc_info:
        _resolve_internal_kinds([sensitive_kind])

    assert exc_info.value.translated_message == "review.operator.errors.unknown_kind"
    assert sensitive_kind not in str(exc_info.value)
    assert sensitive_kind not in repr(exc_info.value.context)
    assert exc_info.value.context is not None
    accepted_kinds = exc_info.value.context["accepted_kinds"]
    assert isinstance(accepted_kinds, (list, tuple, set, frozenset))
    assert "ledger_transaction" in accepted_kinds


def test_project_review_item_not_found_error_omits_raw_item_id() -> None:
    sensitive_item_id = "review-client-tax-id-12345678Z-private-note"

    with profile_create_storage_span("test"), pytest.raises(ReviewError) as exc_info:
        project_review_item(sensitive_item_id, settings=Settings())

    assert exc_info.value.translated_message == "review.operator.errors.item_not_found"
    assert exc_info.value.context is None
    assert sensitive_item_id not in str(exc_info.value)


def test_reserved_review_kind_error_omits_raw_operator_value() -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"
    with override_settings(aeat_output_language="en"):
        error = ReviewKindReservedError(sensitive_kind, "classification decisions are not emitted review items")
        rendered = resolve_error_message(error)

    assert error.translated_message == "review.operator.errors.reserved_kind"
    assert error.context == {"reason": "classification decisions are not emitted review items"}
    assert rendered == "Review kind is reserved and is not an emitted review item."
    assert sensitive_kind not in str(error)
    assert sensitive_kind not in repr(error.context)
