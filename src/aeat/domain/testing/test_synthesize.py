"""Unit tests for :func:`aeat.domain.testing.synthesize_filing_draft` (#239 W1 P7).

The helper is a pure construction surface — no AEAT round-trip — so
every test is a strict pydantic validation + content-hash sanity
check. The five-layer write guard remains intact: this helper
constructs read-state shaped :class:`FilingDraft` records with no
mutation path back to AEAT.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import pytest
from pydantic import ValidationError

from ...domain.filing._schema import (
    FilingDraft,
    FilingDraftStatus,
    FilingValueKind,
    compute_draft_id,
)
from ._synthesize import (
    synthesize_filing_draft,
    synthesize_filing_draft_from_decimals,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class TestSynthesizeFilingDraft:
    """Construction invariants on :func:`synthesize_filing_draft`."""

    def test_returns_strict_frozen_filing_draft(self) -> None:
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )
        assert isinstance(draft, FilingDraft)
        # Frozen — assignment must raise pydantic's frozen-instance error.
        with pytest.raises(ValidationError):
            draft.status = FilingDraftStatus.DRAFT  # type: ignore[misc]

    def test_default_status_is_approved(self) -> None:
        draft = synthesize_filing_draft(
            modelo="130",
            period="1T",
            casilla_values={"03": Decimal("100.00")},
        )
        assert draft.status is FilingDraftStatus.APPROVED
        assert draft.approved_at is not None
        assert draft.approved_by == "synthesize_filing_draft"

    def test_explicit_non_approved_status(self) -> None:
        draft = synthesize_filing_draft(
            modelo="130",
            period="1T",
            casilla_values={"03": Decimal("100.00")},
            status=FilingDraftStatus.DRAFT,
        )
        assert draft.status is FilingDraftStatus.DRAFT
        assert draft.approved_at is None
        assert draft.approved_by is None

    def test_default_profile_tax_id_matches_fixture_corpus(self) -> None:
        # The committed fixture corpus uses Y0000001S as the
        # synthetic NIE; default keeps the contract aligned.
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("0")},
        )
        assert draft.profile_tax_id == "Y0000001S"

    def test_values_are_sorted_by_casilla_id(self) -> None:
        draft = synthesize_filing_draft(
            modelo="303",
            period="2T",
            casilla_values={
                "67": Decimal("200.00"),
                "01": Decimal("100.00"),
                "27": Decimal("150.00"),
            },
        )
        casilla_ids = [v.casilla_id for v in draft.values]
        assert casilla_ids == sorted(casilla_ids)

    def test_every_value_is_kind_literal(self) -> None:
        draft = synthesize_filing_draft(
            modelo="130",
            period="1T",
            casilla_values={"03": Decimal("100"), "07": Decimal("200")},
        )
        for value in draft.values:
            assert value.kind is FilingValueKind.LITERAL

    def test_source_label_is_propagated(self) -> None:
        draft = synthesize_filing_draft(
            modelo="130",
            period="1T",
            casilla_values={"03": Decimal("100")},
            source_label="audit-fixture m130/2024-1T",
        )
        for value in draft.values:
            assert value.source == "audit-fixture m130/2024-1T"

    def test_draft_id_is_deterministic(self) -> None:
        a = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )
        b = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )
        assert a.draft_id == b.draft_id

    def test_draft_id_matches_compute_draft_id(self) -> None:
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("5550.00")},
        )
        expected = compute_draft_id(
            modelo="100",
            period="0A",
            profile_tax_id="Y0000001S",
            schema_version=draft.schema_version,
            values=draft.values,
        )
        assert draft.draft_id == expected

    def test_explicit_created_at_is_used_for_all_timestamps(self) -> None:
        ts = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={"0511": Decimal("0")},
            created_at=ts,
        )
        assert draft.created_at == ts
        assert draft.updated_at == ts
        assert draft.approved_at == ts

    def test_empty_casilla_values_produces_zero_values_tuple(self) -> None:
        draft = synthesize_filing_draft(
            modelo="100",
            period="0A",
            casilla_values={},
        )
        assert draft.values == ()


class TestSynthesizeFilingDraftFromDecimals:
    """The string-coercion convenience wrapper."""

    def test_string_decimals_become_decimal(self) -> None:
        draft = synthesize_filing_draft_from_decimals(
            modelo="100",
            period="0A",
            casilla_decimals={"0511": "5550.00", "0512": "5550.00"},
        )
        for value in draft.values:
            assert isinstance(value.value, Decimal)

    def test_decimal_passthrough(self) -> None:
        draft = synthesize_filing_draft_from_decimals(
            modelo="130",
            period="1T",
            casilla_decimals={"03": Decimal("100.50")},
        )
        assert draft.values[0].value == Decimal("100.50")

    def test_invalid_decimal_string_raises(self) -> None:
        with pytest.raises(InvalidOperation):
            synthesize_filing_draft_from_decimals(
                modelo="100",
                period="0A",
                casilla_decimals={"0511": "not-a-decimal"},
            )

    def test_spanish_thousands_rejected_at_boundary(self) -> None:
        # The wrapper deliberately does NOT parse Spanish decimal
        # strings — callers must canonicalise upstream so the
        # decimal contract stays narrow.
        with pytest.raises(InvalidOperation):
            synthesize_filing_draft_from_decimals(
                modelo="100",
                period="0A",
                casilla_decimals={"0511": "5.550,00"},
            )
