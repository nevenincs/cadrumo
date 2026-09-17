"""Contract tests for governed-fact queries and resolved results."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from ...errors import RegistryValidationError
from ...schema import SupportedFilingYearsCatalogue
from ...schema_base import DateAxis, SourceCitation
from ..resolution import (
    GovernedFactQuery,
    ResolvedGovernedFact,
    ScalarFactQuery,
    required_mapping_entry,
    resolve_governed_fact,
    unique_mapping_tokens,
)
from ..schema import (
    FactOwnership,
    FactSelector,
    GovernedFact,
    GovernedFactCatalogue,
    GovernedFactFamily,
    ScalarFactPayload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The registry's single filing-year envelope, as ``supported-filing-years.toml``
# declares it: a hard floor, an authored horizon and an open ceiling.
_SUPPORT = SupportedFilingYearsCatalogue(floor=2022, horizon=2025)
_CEILED_SUPPORT = SupportedFilingYearsCatalogue(floor=2022, horizon=2025, hard_ceiling=2026)


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
        support=_SUPPORT,
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
        resolve_governed_fact(GovernedFactCatalogue(), query, authority_digest="b" * 64, support=_SUPPORT)


def _scalar_fact(*rows: tuple[str, date | None, date | None, Decimal]) -> GovernedFact:
    return GovernedFact.model_validate(
        {
            "fact_id": "iva.temporal.rate",
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


def _query(fact: GovernedFact, effective_date: date) -> GovernedFactQuery:
    return TypeAdapter(ScalarFactQuery).validate_python(
        {
            "family": "scalar",
            "fact_id": fact.fact_id,
            "date_axis": "transaction_date",
            "effective_date": effective_date,
            "selectors": ({"name": "territory", "value": "peninsula"},),
        },
    )


def _resolve(
    fact: GovernedFact,
    effective_date: date,
    *,
    support: SupportedFilingYearsCatalogue = _SUPPORT,
) -> ResolvedGovernedFact:
    return resolve_governed_fact(
        GovernedFactCatalogue(facts={fact.fact_id: fact}),
        _query(fact, effective_date),
        authority_digest="d" * 64,
        support=support,
    )


def test_an_authored_window_resolves_with_its_full_provenance() -> None:
    fact = _scalar_fact(("iva.temporal.rate.early", date(2023, 1, 1), date(2023, 12, 31), Decimal("0.21")))

    resolved = _resolve(fact, date(2023, 6, 1))

    assert resolved.projection_direction == "authored"
    assert resolved.projected_from_date is None
    assert resolved.valid_from == date(2023, 1, 1)
    assert resolved.valid_to == date(2023, 12, 31)
    assert resolved.payload == ScalarFactPayload(value=Decimal("0.21"), unit="ratio")
    assert resolved.source_citations == (
        SourceCitation(source_ref="test-source-early", required_text=("test source",)),
    )
    assert resolved.ownership == FactOwnership.AUTHORED
    assert resolved.source_revision_ids == ("iva.temporal.rate.early",)


@pytest.mark.parametrize("effective_date", [date(2023, 6, 1), date(2022, 6, 1)])
def test_an_explicit_endpoint_is_a_legal_boundary_nothing_projects_past(effective_date: date) -> None:
    """A date after an explicit valid_to, or before an explicit valid_from, has no variant."""
    fact = _scalar_fact(("iva.temporal.rate.late", date(2022, 7, 1), date(2022, 12, 31), Decimal("0.23")))

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        _resolve(fact, effective_date)


def test_a_gap_between_explicit_windows_resolves_to_nothing() -> None:
    fact = _scalar_fact(
        ("iva.temporal.rate.early", date(2022, 1, 1), date(2022, 6, 30), Decimal("0.21")),
        ("iva.temporal.rate.late", date(2022, 7, 11), None, Decimal("0.23")),
    )

    with pytest.raises(RegistryValidationError, match="no variant for the exact query context"):
        _resolve(fact, date(2022, 7, 8))


def test_an_omitted_valid_from_reaches_the_shared_support_floor() -> None:
    fact = _scalar_fact(("iva.temporal.rate.base", None, date(2024, 12, 31), Decimal("0.21")))

    resolved = _resolve(fact, date(2022, 1, 1))

    assert resolved.projection_direction == "authored"
    assert resolved.valid_from == date(2022, 1, 1)
    assert resolved.authored_valid_from is None
    assert fact.validity_window(fact.variants[0], _SUPPORT.date_envelope()).valid_from == date(2022, 1, 1)


def test_only_the_first_variant_of_a_track_may_omit_valid_from() -> None:
    with pytest.raises(ValidationError, match="only the first declaration can reach the support floor"):
        _scalar_fact(
            ("iva.temporal.rate.a", None, date(2022, 12, 31), Decimal("0.21")),
            ("iva.temporal.rate.b", None, None, Decimal("0.23")),
        )


def test_an_open_final_window_carries_forward_past_the_horizon() -> None:
    fact = _scalar_fact(("iva.temporal.rate.base", date(2022, 1, 1), None, Decimal("0.21")))

    resolved = _resolve(fact, date(2027, 6, 1))

    assert resolved.projection_direction == "forward"
    assert resolved.projected_from_date == date(2025, 12, 31)


@pytest.mark.parametrize(
    ("effective_date", "support"),
    [(date(2021, 12, 31), _SUPPORT), (date(2027, 1, 1), _CEILED_SUPPORT)],
)
def test_the_shared_support_envelope_refuses_queries_outside_its_gates(
    effective_date: date,
    support: SupportedFilingYearsCatalogue,
) -> None:
    fact = _scalar_fact(("iva.temporal.rate.base", None, None, Decimal("0.21")))

    with pytest.raises(RegistryValidationError, match="falls outside the supported filing years"):
        _resolve(fact, effective_date, support=support)


def test_a_governed_fact_cannot_declare_its_own_support_envelope() -> None:
    with pytest.raises(ValidationError, match="support"):
        GovernedFact.model_validate(
            {
                "fact_id": "iva.temporal.rate",
                "family": "scalar",
                "support": {"floor": date(2020, 1, 1), "horizon": date(2025, 12, 31)},
                "variants": (
                    {
                        "variant_id": "iva.temporal.rate.base",
                        "date_axis": "transaction_date",
                        "valid_from": date(2022, 1, 1),
                        "payload": {"kind": "scalar", "value": Decimal("0.21"), "unit": "ratio"},
                        "legal_refs": ("test-law",),
                        "review_status": "pending_review",
                        "ownership": "authored",
                    },
                ),
            }
        )


def test_a_required_mapping_entry_is_returned_stripped() -> None:
    assert required_mapping_entry({"order": "  a,b  "}, "order", subject="demo catalogue") == "a,b"


@pytest.mark.parametrize("entries", [{}, {"order": ""}, {"order": "   "}])
def test_an_absent_or_blank_mapping_entry_is_refused_in_the_subjects_words(entries: dict[str, str]) -> None:
    with pytest.raises(RegistryValidationError) as raised:
        required_mapping_entry(entries, "order", subject="demo catalogue")

    assert str(raised.value) == "demo catalogue is missing 'order'"


def test_unique_mapping_tokens_are_split_stripped_and_ordered() -> None:
    assert unique_mapping_tokens({"order": " a , b,,c "}, "order", subject="demo catalogue") == ("a", "b", "c")


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ({"order": "a,a"}, "demo catalogue 'order' must declare unique tokens"),
        ({"order": " , "}, "demo catalogue 'order' must declare unique tokens"),
        ({}, "demo catalogue is missing 'order'"),
    ],
)
def test_repeated_empty_or_absent_tokens_are_refused_in_the_consumers_words(
    entries: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(RegistryValidationError) as raised:
        unique_mapping_tokens(entries, "order", subject="demo catalogue", requirement="must declare unique tokens")

    assert str(raised.value) == message
