"""Focused unit tests for the describe_stale_reason mapper.

`describe_stale_reason` maps each :class:`ModeloApprovalStaleReason`
enum member to a short localized phrase displayed inline in the CLI
review UI. Currently no direct test coverage; if the
match-statement's case arms drift (e.g., DRAFT_REVIEW_CHANGED renamed
without updating the case arm), the helper would silently fall through
to the catch-all and render the raw enum value to the operator.

Tests here are mapper-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from ....core.i18n import tr
from .._review import ModeloApprovalStaleReason, describe_stale_reason

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPECTED_REASON_KEYS = {
    ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED: (
        "application.filing.review.stale_reasons.approval_basis_version_changed"
    ),
    ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED: "application.filing.review.stale_reasons.draft_payload_changed",
    ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED: "application.filing.review.stale_reasons.draft_review_changed",
    ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED: (
        "application.filing.review.stale_reasons.transaction_catalogue_changed"
    ),
    ModeloApprovalStaleReason.INVOICE_CATALOGUE_CHANGED: (
        "application.filing.review.stale_reasons.invoice_catalogue_changed"
    ),
    ModeloApprovalStaleReason.PRIOR_FILING_OBSERVATIONS_CHANGED: (
        "application.filing.review.stale_reasons.prior_filing_observations_changed"
    ),
    ModeloApprovalStaleReason.PROFILE_ACTIVITY_CHANGED: (
        "application.filing.review.stale_reasons.profile_activity_changed"
    ),
    ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED: (
        "application.filing.review.stale_reasons.category_profiles_changed"
    ),
    ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED: "application.filing.review.stale_reasons.schema_formula_changed",
    ModeloApprovalStaleReason.REVIEW_CHECKSUM_MISMATCH: (
        "application.filing.review.stale_reasons.review_checksum_mismatch"
    ),
}


def test_describe_stale_reason_renders_expected_phrase() -> None:
    for reason, expected_key in _EXPECTED_REASON_KEYS.items():
        assert describe_stale_reason(reason) == tr(expected_key), reason


def test_describe_stale_reason_renders_operator_phrase_for_each_reason() -> None:
    """Raw enum identifiers contain underscores; the rendered phrase
    must not (otherwise the operator sees `draft_payload_changed`
    bleed-through from the catch-all fallback)."""
    for reason in ModeloApprovalStaleReason:
        phrase = describe_stale_reason(reason)
        assert phrase, reason
        assert phrase.strip() == phrase, reason
        assert "_" not in phrase, reason


def test_describe_stale_reason_covers_every_enum_member() -> None:
    """Every concrete member must have an explicit case-arm rendering.
    The catch-all fallback exists for future-proofing only — if it
    fires for a current member, the explicit arms have drifted."""
    assert set(_EXPECTED_REASON_KEYS) == set(ModeloApprovalStaleReason)
