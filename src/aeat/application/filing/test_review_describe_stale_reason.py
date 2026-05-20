"""Focused unit tests for the describe_stale_reason mapper.

`describe_stale_reason` maps each :class:`ModeloApprovalStaleReason`
enum member to a short user-facing English phrase displayed inline in
the CLI review UI. Currently no direct test coverage; if the
match-statement's case arms drift (e.g., DRAFT_REVIEW_CHANGED renamed
without updating the case arm), the helper would silently fall through
to the catch-all and render the raw enum value to the operator.

Tests here are mapper-contract assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from . import ModeloApprovalStaleReason, describe_stale_reason

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_describe_stale_reason_renders_approval_basis_version_changed() -> None:
    assert (
        describe_stale_reason(ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED)
        == "approval basis version changed"
    )


def test_describe_stale_reason_renders_draft_payload_changed() -> None:
    assert describe_stale_reason(ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED) == "draft payload changed"


def test_describe_stale_reason_renders_draft_review_changed() -> None:
    """DRAFT_REVIEW_CHANGED is re-described as 'draft validation surface
    changed' so the operator phrase matches the human-readable concept
    (validation surface), not the raw enum identifier."""
    assert describe_stale_reason(ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED) == "draft validation surface changed"


def test_describe_stale_reason_renders_transaction_catalogue_changed() -> None:
    assert (
        describe_stale_reason(ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED)
        == "transaction catalogue changed"
    )


def test_describe_stale_reason_renders_category_profiles_changed() -> None:
    assert describe_stale_reason(ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED) == "category profiles changed"


def test_describe_stale_reason_renders_schema_formula_changed() -> None:
    """SCHEMA_FORMULA_CHANGED is re-described as 'schema or formula
    provenance changed' to communicate the broader concept (provenance
    invalidation, not just the schema or formula bytes themselves)."""
    assert (
        describe_stale_reason(ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED)
        == "schema or formula provenance changed"
    )


@pytest.mark.parametrize("reason", list(ModeloApprovalStaleReason))
def test_describe_stale_reason_returns_lowercase_phrase(reason: ModeloApprovalStaleReason) -> None:
    """The docstring promises a 'lowercase imperative phrase'. Walking
    every enum member catches the case where a new variant is added
    without an explicit case arm — the catch-all fallback would render
    `reason.value.lower().replace("_", " ")`, which is still lowercase
    but the per-member tests above pin the exact text."""
    phrase = describe_stale_reason(reason)

    assert phrase == phrase.lower()


@pytest.mark.parametrize("reason", list(ModeloApprovalStaleReason))
def test_describe_stale_reason_returns_non_empty_phrase(reason: ModeloApprovalStaleReason) -> None:
    phrase = describe_stale_reason(reason)

    assert phrase
    assert phrase.strip() == phrase


@pytest.mark.parametrize("reason", list(ModeloApprovalStaleReason))
def test_describe_stale_reason_phrase_contains_no_underscores(reason: ModeloApprovalStaleReason) -> None:
    """Raw enum identifiers contain underscores; the rendered phrase
    must not (otherwise the operator sees `draft_payload_changed`
    bleed-through from the catch-all fallback)."""
    assert "_" not in describe_stale_reason(reason)


def test_describe_stale_reason_covers_every_enum_member() -> None:
    """Every concrete member must have an explicit case-arm rendering.
    The catch-all fallback exists for future-proofing only — if it
    fires for a current member, the explicit arms have drifted."""
    explicit = {
        ModeloApprovalStaleReason.APPROVAL_BASIS_VERSION_CHANGED: "approval basis version changed",
        ModeloApprovalStaleReason.DRAFT_PAYLOAD_CHANGED: "draft payload changed",
        ModeloApprovalStaleReason.DRAFT_REVIEW_CHANGED: "draft validation surface changed",
        ModeloApprovalStaleReason.TRANSACTION_CATALOGUE_CHANGED: "transaction catalogue changed",
        ModeloApprovalStaleReason.CATEGORY_PROFILES_CHANGED: "category profiles changed",
        ModeloApprovalStaleReason.SCHEMA_FORMULA_CHANGED: "schema or formula provenance changed",
    }

    # Every current enum member is covered by the explicit map.
    assert set(explicit.keys()) == set(ModeloApprovalStaleReason)
    for reason, expected_phrase in explicit.items():
        assert describe_stale_reason(reason) == expected_phrase
