"""Tests for operator-facing review queue projections."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core.config import Settings, override_settings
from ....core.errors import resolve_error_message
from ....core.i18n import tr
from ....tests.profile_capsule import open_test_profile_session
from ....tests.user_profile import register_minimal_profile
from .. import ReviewSeverity, ReviewState
from .._errors import ReviewError, ReviewKindReservedError
from .._models import FindingReviewItem
from .._operator import (
    ACCEPTED_KINDS,
    ReviewQueueRow,
    _resolve_internal_kinds,
    _row_matches,
    _to_row,
    project_review_item,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "70707070-7070-4070-8070-707070707070"


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

    bucket_id = "23232323-2323-4232-8232-232323232323"
    with open_test_profile_session(bucket_id):
        # Registered first: the engine refuses to materialise a bucket custody
        # never published, which would mask the refusal actually under test.
        register_minimal_profile(profile_id=bucket_id, overrides={"identity.tax_id": "00000000T"})
        with pytest.raises(ReviewError) as exc_info:
            project_review_item(sensitive_item_id, settings=Settings())

    assert exc_info.value.translated_message == "review.operator.errors.item_not_found"
    assert exc_info.value.context is None
    assert sensitive_item_id not in str(exc_info.value)


def test_reserved_review_kind_error_omits_raw_operator_value() -> None:
    sensitive_kind = "client-tax-id-12345678Z-private-note"
    with override_settings(cadrumo_output_language="en"):
        error = ReviewKindReservedError(sensitive_kind, "classification decisions are not emitted review items")
        rendered = resolve_error_message(error)

    assert error.translated_message == "review.operator.errors.reserved_kind"
    assert error.context == {"reason": "classification decisions are not emitted review items"}
    assert rendered == "Review kind is reserved and is not an emitted review item."
    assert sensitive_kind not in str(error)
    assert sensitive_kind not in repr(error.context)


def _finding_item() -> FindingReviewItem:
    return FindingReviewItem(
        item_id="finding-1",
        modelo="303",
        severity=ReviewSeverity.HIGH,
        summary=tr("review.operator.tests.finding_summary"),
        drill_command="aeat app modelo verify",
        since=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        source=None,
        draft_id="draft-1",
        draft_path="db://filing/drafts/draft-1",
    )


def test_finding_row_carries_the_advertised_token_on_both_filter_axes() -> None:
    """``modelo_finding`` is advertised for --kind and --source-kind, so both must match.

    ``_row_matches`` requires a non-None ``source_kind`` for a source filter.
    Emitting the finding row with ``source_kind=None`` therefore made the same
    advertised token select the row as ``--kind`` and silently drop it as
    ``--source-kind`` -- no refusal, no diagnostic, one fewer finding.
    """
    row = _to_row(_finding_item(), state=ReviewState.PENDING, bucket_id=_BUCKET_ID)

    assert row.kind == "modelo_finding"
    assert row.source_kind == "modelo_finding"
    assert _row_matches(row, frozenset({"modelo_finding"}), frozenset()) is True
    assert _row_matches(row, frozenset(), frozenset({"modelo_finding"})) is True
    assert _row_matches(row, frozenset({"modelo_finding"}), frozenset({"modelo_finding"})) is True


def test_finding_row_still_refuses_a_foreign_source_filter() -> None:
    """The parity fix must not make the row match every source filter."""
    row = _to_row(_finding_item(), state=ReviewState.PENDING, bucket_id=_BUCKET_ID)

    assert _row_matches(row, frozenset(), frozenset({"ledger_transaction"})) is False


def test_every_advertised_kind_is_selectable_on_both_axes() -> None:
    """No advertised token may select on one filter axis and not the other.

    Locks the class of defect rather than the one branch: a future row type
    that advertises a kind but leaves ``source_kind`` unset fails here.
    """
    row = _to_row(_finding_item(), state=ReviewState.PENDING, bucket_id=_BUCKET_ID)
    assert row.kind in ACCEPTED_KINDS
    assert row.source_kind is not None
    assert row.source_kind == row.kind


def _row_fields(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "item_id": "finding-1",
        "kind": "modelo_finding",
        "source_kind": "modelo_finding",
        "affected_object_id": "draft-1",
        "bucket_id": _BUCKET_ID,
        "severity": ReviewSeverity.HIGH,
        "state": ReviewState.PENDING,
        "blocking": True,
        "current_owner_surface": "app modelo",
        "canonical_next_command": "aeat app modelo verify",
        "since": datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
        "summary": "s",
    }
    base.update(overrides)
    return base


def test_queue_row_accepts_a_utc_aware_instant() -> None:
    row = ReviewQueueRow.model_validate(_row_fields())

    assert row.since.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 4, 6, 12, 0),
        datetime(2026, 4, 6, 12, 0, tzinfo=timezone(timedelta(hours=1))),
    ],
    ids=["naive", "offset-plus-one"],
)
def test_queue_row_refuses_a_naive_or_non_utc_instant(instant: datetime) -> None:
    """The projection must not re-admit what the canonical review item refuses.

    ``ReviewItem.since`` validates UTC-awareness; the operator row redeclared
    it as a bare ``datetime``, so a naive or ``+01:00`` instant entered the
    projection and cross-source sorting stopped being deterministic.
    """
    with pytest.raises(ValidationError):
        ReviewQueueRow.model_validate(_row_fields(since=instant))
