"""Tests for operator-facing review queue projections."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.config import Settings, override_settings
from ....core.errors import resolve_error_message
from ...user_profile import profile_create_storage_span
from .. import ReviewSeverity, ReviewState
from .._errors import ReviewError, ReviewKindReservedError
from .._operator import ACCEPTED_KINDS, ReviewQueueRow, _resolve_internal_kinds, project_review_item

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_unknown_review_kind_error_omits_raw_operator_value() -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"

    with pytest.raises(ReviewError) as exc_info:
        _resolve_internal_kinds([sensitive_kind])

    assert exc_info.value.translated_message == "review.operator.errors.unknown_kind"
    assert sensitive_kind not in str(exc_info.value)
    assert sensitive_kind not in repr(exc_info.value.context)
    assert exc_info.value.context is not None
    # The accepted set rides on the context as a pre-joined string so the i18n
    # interpolation renders it without a Python repr; the rendered refusal then
    # names every accepted token (CLI-instructive-gate mandate).
    accepted_kinds = exc_info.value.context["accepted_kinds"]
    assert isinstance(accepted_kinds, str)
    assert accepted_kinds == ", ".join(ACCEPTED_KINDS)
    for accepted in ACCEPTED_KINDS:
        assert accepted in accepted_kinds
    rendered = resolve_error_message(exc_info.value)
    for accepted in ACCEPTED_KINDS:
        assert accepted in rendered


def test_review_queue_row_rejects_blank_legal_refs() -> None:
    """Review rows keep finding grounding on the typed registry legal-ref contract."""

    with pytest.raises(ValidationError, match="legal_refs"):
        ReviewQueueRow(
            item_id="review-001",
            kind="modelo_finding",
            affected_object_id="draft-abc",
            bucket_id="b" * 32,
            modelo="303",
            period=None,
            severity=ReviewSeverity.HIGH,
            state=ReviewState.PENDING,
            blocking=True,
            current_owner_surface="app modelo",
            canonical_next_command="aeat app modelo work verify draft-abc",
            since=datetime(2026, 4, 20, 12, 0, tzinfo=UTC),
            summary="modelo 303 finding",
            legal_refs=(" ",),
        )


def test_project_review_item_not_found_error_omits_raw_item_id() -> None:
    sensitive_item_id = "review-client-tax-id-12345678Z-private-note"

    with profile_create_storage_span("23232323-2323-4232-8232-232323232323"), pytest.raises(ReviewError) as exc_info:
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
