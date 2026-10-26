"""Focused contracts for the governed-fact envelope."""

from datetime import date

import pytest
from pydantic import ValidationError

from ..facts.schema import GovernedFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _scalar_fact() -> dict[str, object]:
    return {
        "fact_id": "m347.threshold",
        "family": "scalar",
        "variants": (
            {
                "variant_id": "m347.threshold:2011",
                "date_axis": "filing_period",
                "valid_from": date(2011, 1, 1),
                "payload": {"kind": "scalar", "value": "3005.06", "unit": "EUR"},
                "legal_refs": ("ley-37-1992",),
                "source_refs": ("aeat-m347-instructions",),
                "source_citations": ({"source_ref": "aeat-m347-instructions", "required_text": ("3.005,06 euros",)},),
                "review_status": "pending_review",
                "ownership": "authored",
            },
        ),
    }


def test_governed_fact_hydrates_closed_scalar_payload_and_identity() -> None:
    fact = GovernedFact.model_validate(_scalar_fact())

    assert fact.fact_id == "m347.threshold"
    assert fact.family == "scalar"
    assert fact.variants[0].payload.kind == "scalar"


def test_governed_fact_refuses_payload_outside_declared_family() -> None:
    raw = _scalar_fact()
    raw["family"] = "entity_set"

    with pytest.raises(ValidationError, match="declared"):
        GovernedFact.model_validate(raw)


def test_governed_fact_refuses_unknown_precedence_target() -> None:
    raw = _scalar_fact()
    variants = raw["variants"]
    assert isinstance(variants, tuple)
    variant = variants[0]
    assert isinstance(variant, dict)
    variant["precedence_over"] = ("m347.threshold:missing",)

    with pytest.raises(ValidationError, match="unknown variants"):
        GovernedFact.model_validate(raw)
