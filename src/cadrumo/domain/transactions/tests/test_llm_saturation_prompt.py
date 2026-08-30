"""Real-behavior tests for the saturation extension of the LLM classifier.

Covers the IVA-category saturation contract (llm-ledger-classification decision):

* :class:`LLMClassificationResponse` carries the ``iva_category`` *selection*
  and a proposed ``business_pct`` — and structurally REFUSES any regulated
  numeric tax field (``iva_rate`` / ``taxable_base`` / ``iva_amount``), so the
  model can never originate a number;
* :func:`prompt_spec_with_saturation_fields` builds the IVA-category allow-list
  from the registry-grounded :class:`cadrumo.domain.iva.IvaCatalogue`;
* the rendered prompt asks for the category only (never a rate/base/amount);
* :func:`parse_response` accepts a grounded ``iva_category`` and rejects a
  hallucinated one, and rejects an ``iva_category`` emitted against a spec that
  did not ask for one.

No test doubles: every assertion runs the real prompt-render and parse path.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ...iva.schema import IvaCategory
from ..enums import BusinessClassification, TransactionDirection
from ..llm import (
    LLMClassificationResponse,
    LLMClassifierError,
    default_iva_category_choices,
    default_prompt_spec,
    parse_response,
    prompt_spec_with_saturation_fields,
)
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_NOW = datetime(2026, 4, 6, 12, 0, tzinfo=UTC)


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="row-saturate",
        booked_date=date(2025, 3, 1),
        value_date=date(2025, 3, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Restaurante Sol",
        description="client lunch",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="f" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"Concepto": "client lunch"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "group_label": None, "source_jurisdiction": "ES"},
    )


# ---------------------------------------------------------------------------
# response schema: selection allowed, numeric tax fields structurally refused
# ---------------------------------------------------------------------------


def test_response_carries_iva_category_and_business_pct() -> None:
    response = LLMClassificationResponse(
        classification=BusinessClassification.MIXED,
        confidence=Decimal("0.8"),
        reason="part business, part personal use",
        iva_category=IvaCategory.DOMESTIC_GENERAL,
        business_pct=Decimal("0.6"),
    )
    assert response.iva_category is IvaCategory.DOMESTIC_GENERAL
    assert response.business_pct == Decimal("0.6")


def test_response_defaults_iva_fields_to_none() -> None:
    response = LLMClassificationResponse(
        classification=BusinessClassification.BUSINESS,
        confidence=Decimal("0.9"),
        reason="clearly a business expense",
    )
    assert response.iva_category is None
    assert response.business_pct is None


def test_response_structurally_refuses_numeric_tax_fields() -> None:
    """The model must never carry a regulated number — extra fields are forbidden."""
    for numeric_field in ("iva_rate", "taxable_base", "iva_amount"):
        try:
            with pytest.raises(ValidationError):
                LLMClassificationResponse.model_validate(
                    {
                        "classification": "BUSINESS",
                        "confidence": Decimal("0.9"),
                        "reason": "a business expense",
                        "iva_category": "domestic_general",
                        numeric_field: "21.00",
                    },
                )
        except AssertionError as exc:
            raise AssertionError(f"numeric tax field was accepted: {numeric_field}") from exc


def test_response_rejects_business_pct_out_of_range() -> None:
    with pytest.raises(ValidationError, match="business_pct must be within"):
        LLMClassificationResponse(
            classification=BusinessClassification.MIXED,
            confidence=Decimal("0.8"),
            reason="mixed use",
            business_pct=Decimal("1.5"),
        )


# ---------------------------------------------------------------------------
# grounded allow-list
# ---------------------------------------------------------------------------


def test_iva_choices_cover_every_grounded_category() -> None:
    choices = default_iva_category_choices()
    assert {choice.value for choice in choices} == set(IvaCategory)
    # Every choice carries a non-empty hint resolved from the catalogue label.
    assert all(choice.hint for choice in choices)


def test_saturation_spec_allow_list_matches_every_category() -> None:
    spec = prompt_spec_with_saturation_fields(year=2025)
    assert spec.allowed_iva_categories() == frozenset(IvaCategory)
    # The default spec asks for no IVA category at all.
    assert default_prompt_spec().allowed_iva_categories() == frozenset()


# ---------------------------------------------------------------------------
# rendered prompt: category only, no numbers
# ---------------------------------------------------------------------------


def test_rendered_prompt_requests_iva_category_without_numbers() -> None:
    prompt = prompt_spec_with_saturation_fields(year=2025).render(_transaction())
    assert "iva_category" in prompt
    assert IvaCategory.DOMESTIC_GENERAL.value in prompt
    # Explicitly instructs the model not to compute a figure.
    assert "do NOT compute" in prompt
    # The schema line offers iva_category as a selection, never a rate field.
    assert '"iva_rate"' not in prompt
    assert '"taxable_base"' not in prompt


# ---------------------------------------------------------------------------
# parse_response hallucination guard for iva_category
# ---------------------------------------------------------------------------


def test_parse_accepts_grounded_iva_category() -> None:
    spec = prompt_spec_with_saturation_fields(year=2025)
    stdout = (
        '{"classification": "BUSINESS", "confidence": 0.9, "reason": "business meal", '
        '"category": "manutencion_dietas_nacional", "iva_category": "domestic_reduced"}'
    )
    response = parse_response(stdout, spec=spec)
    assert response.iva_category is IvaCategory.DOMESTIC_REDUCED


def test_parse_rejects_hallucinated_iva_category() -> None:
    spec = prompt_spec_with_saturation_fields(year=2025)
    stdout = '{"classification": "BUSINESS", "confidence": 0.9, "reason": "x", "iva_category": "not_a_real_category"}'
    with pytest.raises(LLMClassifierError, match=r"no JSON candidate matched"):
        parse_response(stdout, spec=spec)


def test_parse_rejects_iva_category_when_spec_did_not_ask() -> None:
    # The default classification-only spec carries no IVA allow-list, so an
    # emitted iva_category is unexpected and must be refused.
    stdout = '{"classification": "BUSINESS", "confidence": 0.9, "reason": "x", "iva_category": "domestic_general"}'
    with pytest.raises(LLMClassifierError, match=r"no JSON candidate matched"):
        parse_response(stdout, spec=default_prompt_spec())


def test_every_iva_category_carries_a_curated_hint() -> None:
    """No category may fall back to its auto-derived hint.

    The choice builder falls back to ``category.value.replace("_", " ")`` for
    any category the hints map omits, so an unhinted category stays selectable
    and nothing fails — the omission is invisible. It was: two categories
    shipped without hints and no gate noticed.

    Silent is not harmless here. A derived hint can only restate the member
    name, so it conveys nothing the name does not, and the distinctions these
    hints exist to draw are exactly the ones the names collide on — an
    intra-community supply of goods and of services differ by which article
    relieves the Spanish cuota, not by their spelling.
    """
    unhinted = sorted(
        choice.value.value
        for choice in default_iva_category_choices()
        if choice.hint == choice.value.value.replace("_", " ")
    )

    assert unhinted == [], f"IVA categories falling back to a derived hint: {unhinted}"
