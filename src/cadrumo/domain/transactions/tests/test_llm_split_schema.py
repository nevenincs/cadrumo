"""Schema tests for the evidence-driven N-way split proposal.

The model proposes proportions (fractions), category, and iva_category per child;
it never carries a euro amount or a regulated tax number. The application derives
amounts from the parent gross and the tax substrate from the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...iva.schema import IvaCategory
from ..enums import TransactionDirection
from ..llm import (
    LLMClassifierError,
    LLMSplitChild,
    LLMSplitResponse,
    build_split_prompt,
    parse_split_response,
    prompt_spec_with_saturation_fields,
)
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_VALID_SPLIT_JSON = (
    '{"reason": "two lines on the invoice",'
    ' "children": ['
    '{"proportion": 0.6, "iva_category": "domestic_general", "evidence_citation": "line 1"},'
    '{"proportion": 0.4, "iva_category": "domestic_general", "evidence_citation": "line 2"}'
    "]}"
)


def _child(proportion: str) -> LLMSplitChild:
    return LLMSplitChild(proportion=Decimal(proportion), iva_category=IvaCategory.DOMESTIC_GENERAL)


def _assert_validation_error(case_id: str, build: Callable[[], object], match: str) -> None:
    """Assert ``build()`` raises a ``ValidationError`` naming the expected failure.

    A bare ``except ValidationError: return`` cannot distinguish the intended
    failure (a specific field, a specific reason) from an unrelated field
    failing for an unrelated reason — exactly the false pass this helper must
    not produce. ``match`` pins the reason and is checked against ``str(exc)``;
    ``case_id`` documents the call site for the reader, matching the shape of
    the other case-driven loops in this module.
    """
    with pytest.raises(ValidationError, match=match):
        build()


def test_split_response_verdicts_build() -> None:
    verdicts = (
        ("two-way-split", (_child("0.6"), _child("0.4")), True),
        ("single-child-no-split", (_child("1.0"),), False),
    )
    for case_id, children, expected_recommends_split in verdicts:
        response = LLMSplitResponse(children=children, reason=case_id)
        assert len(response.children) == len(children), case_id
        assert sum(c.proportion for c in response.children) == Decimal("1.0"), case_id
        assert response.recommends_split is expected_recommends_split, case_id


def test_invalid_split_schema_payloads_are_rejected() -> None:
    invalid_builders: tuple[tuple[str, Callable[[], object], str], ...] = (
        (
            "empty-children",
            lambda: LLMSplitResponse(children=(), reason="no children"),
            "must carry at least one child",
        ),
        (
            "oversum",
            lambda: LLMSplitResponse(children=(_child("0.6"), _child("0.6")), reason="oversum"),
            "must sum to approximately 1.0",
        ),
        (
            "zero-proportion",
            lambda: LLMSplitChild(proportion=Decimal("0")),
            r"proportion must be within \(0, 1\]",
        ),
        (
            "above-one-proportion",
            lambda: LLMSplitChild(proportion=Decimal("1.5")),
            r"proportion must be within \(0, 1\]",
        ),
        (
            "numeric-amount",
            lambda: LLMSplitChild.model_validate({"proportion": "0.5", "amount": "100.00"}),
            r"amount\s+Extra inputs are not permitted",
        ),
        (
            "numeric-iva-amount",
            lambda: LLMSplitChild.model_validate({"proportion": "0.5", "iva_amount": "100.00"}),
            r"iva_amount\s+Extra inputs are not permitted",
        ),
        (
            "numeric-taxable-base",
            lambda: LLMSplitChild.model_validate({"proportion": "0.5", "taxable_base": "100.00"}),
            r"taxable_base\s+Extra inputs are not permitted",
        ),
        (
            "numeric-iva-rate",
            lambda: LLMSplitChild.model_validate({"proportion": "0.5", "iva_rate": "100.00"}),
            r"iva_rate\s+Extra inputs are not permitted",
        ),
    )
    for case_id, build, match in invalid_builders:
        _assert_validation_error(case_id, build, match)


def test_parse_split_extracts_nested_json_amid_prose() -> None:
    noisy = "Here is the split:\n" + _VALID_SPLIT_JSON + "\nHope that helps!"
    response = parse_split_response(noisy, spec=prompt_spec_with_saturation_fields(year=2025))
    assert len(response.children) == 2
    assert response.children[0].iva_category is IvaCategory.DOMESTIC_GENERAL


def test_parse_split_rejects_invalid_outputs() -> None:
    rejection_cases = (
        ("disallowed-iva-category", lambda: parse_split_response(_VALID_SPLIT_JSON)),
        ("no-json", lambda: parse_split_response("no json here", spec=prompt_spec_with_saturation_fields(year=2025))),
    )
    for case_id, parse in rejection_cases:
        try:
            parse()
        except LLMClassifierError:
            continue
        pytest.fail(f"{case_id} split output was accepted")


def test_build_split_prompt_includes_evidence_and_no_numbers_guard() -> None:
    raw = RawTransaction(
        provider_transaction_id="row-split",
        booked_date=date(2025, 3, 1),
        value_date=date(2025, 3, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Acme SL",
        description="mixed invoice",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "mixed invoice"},
    )
    txn = Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )
    prompt = build_split_prompt(
        txn, spec=prompt_spec_with_saturation_fields(year=2025), evidence_text="line 1 ... line 2 ..."
    )
    assert "begin evidence" in prompt
    assert "EXACTLY ONE child with proportion 1.0" in prompt
    assert "one child per line" in prompt
    assert "Do NOT output any euro amount" in prompt
    assert '"proportion"' in prompt
