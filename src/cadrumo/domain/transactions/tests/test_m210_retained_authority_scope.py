"""Nested M210 classification reads stay on the validation generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Never

import pytest
from pydantic import ValidationError

from ...calculations.registry import authority as authority_module
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.facts.schema import GovernedFactCatalogue
from ...calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    governed_facts_in_scope,
    validating_governed_facts,
)
from ...calculations.registry.schema import SupportedFilingYearsCatalogue
from ..errors import TransactionValidationError
from ..m210_income_classification import M210IncomeClassification, resolve_m210_payer_mode

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EFFECTIVE_DATE = date(2026, 7, 1)


def _unexpected_bundle() -> Never:
    """Fail if a scoped M210 validation attempts a second bundled lease."""
    raise AssertionError("M210 validation attempted to open another bundled authority lease")


def _candidate_authority() -> CandidateFactAuthority:
    """Build a real unpublished fact scope that must not become runtime authority."""
    return CandidateFactAuthority(
        catalogue=GovernedFactCatalogue(facts={}),
        support=SupportedFilingYearsCatalogue(floor=2022, horizon=2026),
    )


def test_m210_model_and_payer_mode_resolution_reuse_the_leased_published_generation(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both detail and revision validation use the one real retained operation."""
    monkeypatch.setattr(authority_module, "bundled_indexed_authority", _unexpected_bundle)

    with validating_governed_facts(authority_operation):
        assert governed_facts_in_scope() is authority_operation
        payer_mode = resolve_m210_payer_mode(effective_date=_EFFECTIVE_DATE)
        classification = M210IncomeClassification(
            official_tipo_renta_code="01",
            gross_income_amount=Decimal("1000.00"),
            applicable_rate=Decimal("0.19"),
        )

    assert classification.official_tipo_renta_code == "01"
    assert classification.gross_income_amount == Decimal("1000.00")
    assert classification.payer_mode == payer_mode


def test_m210_model_and_payer_mode_resolution_refuse_candidate_scope_without_bundle_fallback(
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A candidate's real fact source cannot substitute for a published pin."""
    with validating_governed_facts(authority_operation):
        payer_mode = resolve_m210_payer_mode(effective_date=_EFFECTIVE_DATE)

    monkeypatch.setattr(authority_module, "bundled_indexed_authority", _unexpected_bundle)
    with validating_governed_facts(_candidate_authority()):
        with pytest.raises(TransactionValidationError):
            resolve_m210_payer_mode(effective_date=_EFFECTIVE_DATE)
        with pytest.raises(ValidationError, match="published generation-pinned authority"):
            M210IncomeClassification(
                official_tipo_renta_code="01",
                gross_income_amount=Decimal("1000.00"),
                applicable_rate=Decimal("0.19"),
                payer_mode=payer_mode,
            )
