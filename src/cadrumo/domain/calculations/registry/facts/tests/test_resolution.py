"""Contract tests for governed-fact queries and resolved results."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ...errors import RegistryValidationError
from ...schema_base import DateAxis, SourceCitation
from ..resolution import GovernedFactQuery, ResolvedGovernedFact, ScalarFactQuery, resolve_governed_fact
from ..schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactCatalogue,
    GovernedFactFamily,
    ScalarFactPayload,
)

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
        "source_citations": (SourceCitation(source_ref="aeat-iva-rates", required_text=("Tipo general",)),),
        "review_status": "pending_review",
        "ownership": "authored",
        "authority_digest": "a" * 64,
        "source_variant_id": "iva.general.rate.2025",
        "source_revision_ids": ("iva.general.rate.2025",),
    }


def test_resolved_union_preserves_payload_identity_context_and_provenance() -> None:
    resolved = TypeAdapter(ResolvedGovernedFact).validate_python(_resolved_scalar_data())

    assert resolved.payload == ScalarFactPayload(value=Decimal("0.21"), unit="ratio")
    assert resolved.ownership is FactOwnership.AUTHORED
    assert resolved.authority_digest == "a" * 64
    assert resolved.source_variant_id == "iva.general.rate.2025"
    assert resolved.source_revision_ids == ("iva.general.rate.2025",)
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


def test_authority_resolver_returns_a_provenance_bearing_result_for_exact_context() -> None:
    fact = GovernedFact.model_validate(
        {
            "fact_id": "iva.general.rate",
            "family": "scalar",
            "variants": (
                {
                    "variant_id": "iva.general.rate.2025",
                    "selectors": ({"name": "territory", "value": "peninsula"},),
                    "date_axis": "transaction_date",
                    "valid_from": date(2025, 1, 1),
                    "payload": {"kind": "scalar", "value": Decimal("0.21"), "unit": "ratio"},
                    "legal_refs": ("ley-37-1992-art-90",),
                    "source_refs": ("aeat-iva-rates",),
                    "source_citations": ({"source_ref": "aeat-iva-rates", "required_text": ("Tipo general",)},),
                    "review_status": "pending_review",
                    "ownership": "authored",
                },
            ),
        },
    )
    query = TypeAdapter(GovernedFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": fact.fact_id,
            "date_axis": "transaction_date",
            "effective_date": date(2026, 1, 15),
            "selectors": ({"name": "territory", "value": "peninsula"},),
        },
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        query,
        authority_digest="b" * 64,
    )

    assert resolved.variant_id == "iva.general.rate.2025"
    assert resolved.payload == fact.variants[0].payload
    assert resolved.authority_digest == "b" * 64


def test_authority_resolver_refuses_an_unregistered_fact() -> None:
    query = TypeAdapter(GovernedFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": "missing.fact",
            "date_axis": "filing_period",
            "effective_date": date(2026, 1, 1),
        },
    )

    with pytest.raises(RegistryValidationError, match="is not registered"):
        resolve_governed_fact(GovernedFactCatalogue(), query, authority_digest="b" * 64)


def _temporally_supported_scalar_fact(
    *,
    valid_from: date | None = date(2022, 1, 1),
    valid_to: date | None = date(2025, 12, 31),
) -> GovernedFact:
    return GovernedFact.model_validate(
        {
            "fact_id": "iva.temporal.rate",
            "family": "scalar",
            "support": {
                "floor": date(2020, 1, 1),
                "horizon": date(2025, 12, 31),
                "hard_ceiling": date(2026, 12, 31),
            },
            "variants": (
                {
                    "variant_id": "iva.temporal.rate.2022",
                    "date_axis": "transaction_date",
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "payload": {"kind": "scalar", "value": Decimal("0.21"), "unit": "ratio"},
                    "legal_refs": ("ley-37-1992-art-90",),
                    "review_status": "pending_review",
                    "ownership": "authored",
                },
            ),
        }
    )


def _supportless_scalar_fact(
    *rows: tuple[str, date, date, Decimal],
) -> GovernedFact:
    return GovernedFact.model_validate(
        {
            "fact_id": "iva.supportless.temporal.rate",
            "family": "scalar",
            "variants": tuple(
                {
                    "variant_id": variant_id,
                    "selectors": ({"name": "territory", "value": "peninsula"},),
                    "date_axis": "transaction_date",
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "payload": {"kind": "scalar", "value": value, "unit": "ratio"},
                    "legal_refs": ("test-law",),
                    "source_refs": (source_ref := f"test-source-{variant_id.rsplit('.', 1)[-1]}",),
                    "source_citations": ({"source_ref": source_ref, "required_text": ("test source",)},),
                    "review_status": "pending_review",
                    "ownership": "authored",
                }
                for variant_id, valid_from, valid_to, value in rows
            ),
        },
    )


def _supportless_scalar_query(fact: GovernedFact, effective_date: date) -> GovernedFactQuery:
    return TypeAdapter(ScalarFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": fact.fact_id,
            "date_axis": "transaction_date",
            "effective_date": effective_date,
            "selectors": ({"name": "territory", "value": "peninsula"},),
        },
    )


def _assert_projected_authored_context(
    resolved: ResolvedGovernedFact,
    *,
    variant_id: str,
    valid_from: date,
    valid_to: date,
    value: Decimal,
) -> None:
    assert resolved.variant_id == variant_id
    assert resolved.valid_from == valid_from
    assert resolved.valid_to == valid_to
    assert resolved.authored_valid_from == valid_from
    assert resolved.authored_valid_to == valid_to
    assert resolved.payload == ScalarFactPayload(value=value, unit="ratio")
    assert resolved.legal_refs == ("test-law",)
    source_ref = f"test-source-{variant_id.rsplit('.', 1)[-1]}"
    assert resolved.source_refs == (source_ref,)
    assert resolved.source_citations == (SourceCitation(source_ref=source_ref, required_text=("test source",)),)
    assert resolved.ownership == FactOwnership.AUTHORED
    assert resolved.source_variant_id == variant_id
    assert resolved.source_revision_ids == (variant_id,)


def test_supportless_fact_projects_forward_from_the_nearest_authored_window() -> None:
    fact = _supportless_scalar_fact(
        ("iva.supportless.temporal.rate.early", date(2022, 1, 1), date(2022, 12, 31), Decimal("0.21")),
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        _supportless_scalar_query(fact, date(2023, 6, 1)),
        authority_digest="d" * 64,
    )

    assert resolved.projection_direction == "forward"
    assert resolved.projected_from_date == date(2022, 12, 31)
    assert resolved.authority_digest == "d" * 64
    _assert_projected_authored_context(
        resolved,
        variant_id="iva.supportless.temporal.rate.early",
        valid_from=date(2022, 1, 1),
        valid_to=date(2022, 12, 31),
        value=Decimal("0.21"),
    )


def test_supportless_fact_propagates_backward_from_the_nearest_authored_window() -> None:
    fact = _supportless_scalar_fact(
        ("iva.supportless.temporal.rate.late", date(2024, 1, 1), date(2024, 12, 31), Decimal("0.23")),
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        _supportless_scalar_query(fact, date(2023, 6, 1)),
        authority_digest="e" * 64,
    )

    assert resolved.projection_direction == "backward"
    assert resolved.projected_from_date == date(2024, 1, 1)
    assert resolved.authority_digest == "e" * 64
    _assert_projected_authored_context(
        resolved,
        variant_id="iva.supportless.temporal.rate.late",
        valid_from=date(2024, 1, 1),
        valid_to=date(2024, 12, 31),
        value=Decimal("0.23"),
    )


def test_supportless_fact_internal_gap_uses_the_nearest_authored_side() -> None:
    fact = _supportless_scalar_fact(
        ("iva.supportless.temporal.rate.early", date(2022, 1, 1), date(2022, 6, 30), Decimal("0.21")),
        ("iva.supportless.temporal.rate.late", date(2022, 7, 11), date(2022, 12, 31), Decimal("0.23")),
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        _supportless_scalar_query(fact, date(2022, 7, 8)),
        authority_digest="f" * 64,
    )

    assert resolved.projection_direction == "backward"
    assert resolved.projected_from_date == date(2022, 7, 11)
    _assert_projected_authored_context(
        resolved,
        variant_id="iva.supportless.temporal.rate.late",
        valid_from=date(2022, 7, 11),
        valid_to=date(2022, 12, 31),
        value=Decimal("0.23"),
    )


def test_supportless_fact_equal_distance_prefers_the_earlier_authored_source() -> None:
    fact = _supportless_scalar_fact(
        ("iva.supportless.temporal.rate.early", date(2022, 1, 1), date(2022, 6, 30), Decimal("0.21")),
        ("iva.supportless.temporal.rate.late", date(2022, 7, 4), date(2022, 12, 31), Decimal("0.23")),
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        _supportless_scalar_query(fact, date(2022, 7, 2)),
        authority_digest="a" * 64,
    )

    assert resolved.projection_direction == "forward"
    assert resolved.projected_from_date == date(2022, 6, 30)
    _assert_projected_authored_context(
        resolved,
        variant_id="iva.supportless.temporal.rate.early",
        valid_from=date(2022, 1, 1),
        valid_to=date(2022, 6, 30),
        value=Decimal("0.21"),
    )


@pytest.mark.parametrize(
    ("effective_date", "direction", "projected_from"),
    [
        (date(2021, 6, 1), "backward", date(2022, 1, 1)),
        (date(2023, 6, 1), "authored", None),
        (date(2026, 6, 1), "forward", date(2025, 12, 31)),
    ],
)
def test_fact_support_projects_only_between_its_hard_floor_and_ceiling(
    effective_date: date,
    direction: str,
    projected_from: date | None,
) -> None:
    fact = _temporally_supported_scalar_fact()
    query = TypeAdapter(GovernedFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": fact.fact_id,
            "date_axis": "transaction_date",
            "effective_date": effective_date,
        }
    )

    resolved = resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        query,
        authority_digest="c" * 64,
    )

    assert resolved.projection_direction == direction
    assert resolved.projected_from_date == projected_from
    assert resolved.source_variant_id == "iva.temporal.rate.2022"
    assert resolved.source_revision_ids == ("iva.temporal.rate.2022",)


@pytest.mark.parametrize("effective_date", [date(2019, 12, 31), date(2027, 1, 1)])
def test_fact_support_refuses_queries_outside_its_hard_boundaries(effective_date: date) -> None:
    fact = _temporally_supported_scalar_fact()
    query = TypeAdapter(GovernedFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": fact.fact_id,
            "date_axis": "transaction_date",
            "effective_date": effective_date,
        }
    )

    with pytest.raises(RegistryValidationError, match="outside its hard support boundaries"):
        resolve_governed_fact(
            GovernedFactCatalogue(facts={fact.fact_id: fact}),
            query,
            authority_digest="c" * 64,
        )


def test_omitted_fact_bounds_materialize_to_the_support_floor_and_ceiling() -> None:
    fact = _temporally_supported_scalar_fact(valid_from=None, valid_to=None)

    window = fact.validity_window(fact.variants[0])

    assert window.valid_from == date(2020, 1, 1)
    assert window.valid_to == date(2026, 12, 31)
