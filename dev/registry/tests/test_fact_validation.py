"""Detector-teeth tests for governed-fact catalogue validation."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.facts.schema import GovernedFact, GovernedFactCatalogue

from ..compiler.fact_validation import governed_fact_catalogue_failures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _variant(
    variant_id: str,
    *,
    valid_from: date,
    valid_to: date | None = None,
    precedence_over: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "variant_id": variant_id,
        "date_axis": "filing_period",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": {"kind": "scalar", "value": "10", "unit": "EUR"},
        "legal_refs": ("law",),
        "source_refs": ("test-source",),
        "source_citations": ({"source_ref": "test-source", "required_text": ("text",)},),
        "review_status": "pending_review",
        "ownership": "authored",
        "precedence_over": precedence_over,
    }


def _failures(*variants: dict[str, object]) -> tuple[str, ...]:
    fact = GovernedFact.model_validate({"fact_id": "test.rate", "family": "scalar", "variants": variants})
    return governed_fact_catalogue_failures(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        legal_ref_ids={"law"},
        source_ref_ids={"test-source"},
    )


def test_validation_refuses_a_precedence_cycle() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1), precedence_over=("rate.b",)),
        _variant("rate.b", valid_from=date(2025, 1, 1), precedence_over=("rate.a",)),
    )

    assert any("precedence graph contains a cycle" in failure for failure in failures)


def test_validation_refuses_an_unresolved_overlap() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1)),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert any("overlap without explicit precedence" in failure for failure in failures)


def test_validation_refuses_precedence_across_non_overlapping_coordinates() -> None:
    failures = _failures(
        _variant(
            "rate.a",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 5, 31),
            precedence_over=("rate.b",),
        ),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert any("precedence across non-overlapping coordinates" in failure for failure in failures)


def test_validation_accepts_an_acyclic_ordered_overlap() -> None:
    failures = _failures(
        _variant("rate.a", valid_from=date(2025, 1, 1), precedence_over=("rate.b",)),
        _variant("rate.b", valid_from=date(2025, 6, 1)),
    )

    assert failures == ()


def test_facts_package_initializer_is_an_inert_namespace_marker() -> None:
    from cadrumo.domain.calculations.registry.facts import __dict__ as namespace

    assert "GovernedFact" not in namespace
    assert "ScalarFactPayload" not in namespace
