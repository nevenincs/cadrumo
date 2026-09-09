"""Contract tests for governed-fact queries and resolved results."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ...schema_base import DateAxis, SourceCitation
from ..resolution import GovernedFactQuery, ResolvedGovernedFact
from ..schema import FactOwnership, FactSelector, GovernedFactFamily, ScalarFactPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_query_union_hydrates_the_exact_family_and_context() -> None:
    query = TypeAdapter(GovernedFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": "iva.general.rate",
            "date_axis": "transaction_date",
            "effective_date": date(2026, 1, 15),
            "selectors": ({"name": "territory", "value": "peninsula"},),
        },
    )

    assert query.family is GovernedFactFamily.SCALAR
    assert query.date_axis is DateAxis.TRANSACTION_DATE
    assert query.selectors == (FactSelector(name="territory", value="peninsula"),)


def test_query_union_refuses_unknown_families_and_ambiguous_coordinates() -> None:
    adapter = TypeAdapter(GovernedFactQuery)

    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "family": "free_form",
                "fact_id": "iva.general.rate",
                "date_axis": "transaction_date",
                "effective_date": date(2026, 1, 15),
            },
        )
    with pytest.raises(ValidationError, match="selector names must be unique"):
        adapter.validate_python(
            {
                "family": "scalar",
                "fact_id": "iva.general.rate",
                "date_axis": "transaction_date",
                "effective_date": date(2026, 1, 15),
                "selectors": (
                    {"name": "territory", "value": "peninsula"},
                    {"name": "territory", "value": "canarias"},
                ),
            },
        )


def _resolved_scalar_data() -> dict[str, object]:
    return {
        "family": "scalar",
        "fact_id": "iva.general.rate",
        "variant_id": "iva.general.rate.2025",
        "date_axis": "transaction_date",
        "effective_date": date(2026, 1, 15),
        "valid_from": date(2025, 1, 1),
        "valid_to": None,
        "matched_selectors": ({"name": "territory", "value": "peninsula"},),
        "payload": {"kind": "scalar", "value": Decimal("0.21"), "unit": "ratio"},
        "legal_refs": ("ley-37-1992-art-90",),
        "source_refs": ("aeat-iva-rates",),
        "source_citations": (
            SourceCitation(source_ref="aeat-iva-rates", required_text=("Tipo general",)),
        ),
        "review_status": "pending_review",
        "ownership": "authored",
        "authority_digest": "a" * 64,
    }


def test_resolved_union_preserves_payload_identity_context_and_provenance() -> None:
    resolved = TypeAdapter(ResolvedGovernedFact).validate_python(_resolved_scalar_data())

    assert resolved.payload == ScalarFactPayload(value=Decimal("0.21"), unit="ratio")
    assert resolved.ownership is FactOwnership.AUTHORED
    assert resolved.authority_digest == "a" * 64
    assert resolved.source_citations[0].source_ref == "aeat-iva-rates"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("effective_date", date(2024, 12, 31), "must fall within its validity window"),
        ("authority_digest", "not-an-authority", "string_pattern_mismatch"),
        (
            "source_citations",
            (SourceCitation(source_ref="unknown-source", required_text=("text",)),),
            "must name a declared source_ref",
        ),
    ],
)
def test_resolved_union_fails_closed_on_invalid_context_or_provenance(
    field: str,
    value: object,
    message: str,
) -> None:
    data = _resolved_scalar_data()
    data[field] = value

    with pytest.raises(ValidationError, match=message):
        TypeAdapter(ResolvedGovernedFact).validate_python(data)


def test_resolved_union_refuses_a_payload_from_another_family() -> None:
    data = _resolved_scalar_data()
    data["payload"] = {"kind": "entity_set", "entities": ["ES"]}

    with pytest.raises(ValidationError):
        TypeAdapter(ResolvedGovernedFact).validate_python(data)
