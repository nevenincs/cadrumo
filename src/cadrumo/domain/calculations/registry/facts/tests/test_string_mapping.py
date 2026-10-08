"""Contract tests for the string-to-string projection of mapping facts."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ......core.errors.hierarchy import InternalInvariantError
from ......core.time.clock import today_madrid
from ...errors import RegistryValidationError
from ...governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from ...schema import SupportedFilingYearsCatalogue
from ...schema_base import DateAxis
from ...tests.fact_scope import outside_governed_fact_validation
from ..resolution import (
    GovernedFactQuery,
    MappingFactQuery,
    ResolvedGovernedFact,
    ScalarFactQuery,
    resolve_governed_fact,
)
from ..schema import GovernedFact, GovernedFactCatalogue
from ..string_mapping import (
    BooleanTokenCase,
    MappingValueWhitespace,
    StringMappingFact,
    StringMappingPolicy,
    require_resolved_mapping_fact,
    required_mapping_boolean,
    resolve_string_mapping_entries,
    string_mapping_entries,
    unique_mapping_legal_refs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SUPPORT = SupportedFilingYearsCatalogue(floor=2022, horizon=2025)
_FACT_ID = "demo.mapping.catalogue"
_QUERY = MappingFactQuery(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=date(2025, 3, 1))
_PRESERVE = StringMappingPolicy(subject="demo catalogue", value_whitespace=MappingValueWhitespace.PRESERVE)
_STRIP = StringMappingPolicy(subject="demo catalogue", value_whitespace=MappingValueWhitespace.STRIP)


def _variant(fact_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "variant_id": f"{fact_id}.2025",
        "date_axis": "filing_period",
        "valid_from": date(2025, 1, 1),
        "payload": payload,
        "legal_refs": ("test-law",),
        "source_refs": ("test-source",),
        "source_citations": ({"source_ref": "test-source", "required_text": ("test source",)},),
        "review_status": "pending_review",
        "ownership": "authored",
    }


def _authority(*entries: tuple[str, object]) -> CandidateFactAuthority:
    fact = GovernedFact.model_validate(
        {
            "fact_id": _FACT_ID,
            "family": "mapping",
            "variants": (
                _variant(
                    _FACT_ID,
                    {"kind": "mapping", "entries": tuple({"key": key, "value": value} for key, value in entries)},
                ),
            ),
        },
    )
    return CandidateFactAuthority(catalogue=GovernedFactCatalogue(facts={fact.fact_id: fact}), support=_SUPPORT)


def test_a_string_mapping_resolves_to_an_immutable_view_that_preserves_values() -> None:
    entries = resolve_string_mapping_entries(
        _authority(("order", "  a,b  "), ("a.value", "a")),
        _QUERY,
        policy=_PRESERVE,
    )

    assert dict(entries) == {"order": "  a,b  ", "a.value": "a"}
    assert not hasattr(entries, "__setitem__")


def test_a_strip_policy_removes_surrounding_whitespace_from_every_value() -> None:
    entries = resolve_string_mapping_entries(
        _authority(("order", "  a,b  "), ("a.value", "\ta\n")),
        _QUERY,
        policy=_STRIP,
    )

    assert dict(entries) == {"order": "a,b", "a.value": "a"}


def test_a_non_string_mapping_value_is_refused_with_the_canonical_registry_error() -> None:
    authority = _authority(("order", "a"), ("a.rate", Decimal("0.21")))

    with pytest.raises(RegistryValidationError, match=r"^demo catalogue entries must be string-to-string$"):
        resolve_string_mapping_entries(authority, _QUERY, policy=_PRESERVE)


def test_a_fact_resolving_to_another_family_is_refused_before_projection() -> None:
    scalar = GovernedFact.model_validate(
        {
            "fact_id": _FACT_ID,
            "family": "scalar",
            "variants": (_variant(_FACT_ID, {"kind": "scalar", "value": Decimal("0.21"), "unit": "ratio"}),),
        },
    )
    resolved_scalar = resolve_governed_fact(
        GovernedFactCatalogue(facts={scalar.fact_id: scalar}),
        ScalarFactQuery(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=date(2025, 3, 1)),
        authority_digest="a" * 64,
        support=_SUPPORT,
    )

    class _MisroutedSource:
        """An authority that answers a mapping query with another family."""

        def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
            del query
            return resolved_scalar

        def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
            return _SUPPORT

    with pytest.raises(RegistryValidationError, match=r"^demo catalogue must resolve as a mapping fact$"):
        require_resolved_mapping_fact(_MisroutedSource(), _QUERY, subject="demo catalogue")


def test_the_projection_reads_an_already_resolved_mapping_fact() -> None:
    resolved = require_resolved_mapping_fact(_authority(("order", " a ")), _QUERY, subject="demo catalogue")

    assert dict(string_mapping_entries(resolved, policy=_STRIP)) == {"order": "a"}
    assert dict(string_mapping_entries(resolved, policy=_PRESERVE)) == {"order": " a "}


@pytest.mark.parametrize(
    ("raw", "case", "expected"),
    [
        ("true", BooleanTokenCase.EXACT, True),
        ("false", BooleanTokenCase.EXACT, False),
        ("True", BooleanTokenCase.CASE_INSENSITIVE, True),
        (" FALSE ", BooleanTokenCase.CASE_INSENSITIVE, False),
    ],
)
def test_a_boolean_entry_reads_under_its_declared_case(raw: str, case: BooleanTokenCase, expected: bool) -> None:
    assert required_mapping_boolean({"flag": raw}, "flag", subject="demo catalogue", case=case) is expected


@pytest.mark.parametrize(
    ("entries", "case"),
    [
        ({"flag": "True"}, BooleanTokenCase.EXACT),
        ({"flag": "yes"}, BooleanTokenCase.CASE_INSENSITIVE),
        ({"flag": " "}, BooleanTokenCase.CASE_INSENSITIVE),
        ({}, BooleanTokenCase.EXACT),
    ],
)
def test_a_non_boolean_or_absent_entry_is_refused(entries: dict[str, str], case: BooleanTokenCase) -> None:
    with pytest.raises(RegistryValidationError, match="demo catalogue"):
        required_mapping_boolean(entries, "flag", subject="demo catalogue", case=case)


def test_legal_references_are_split_stripped_and_kept_in_order() -> None:
    refs = unique_mapping_legal_refs({"refs": " liva-art-1 , ,liva-art-2"}, "refs", subject="demo catalogue")

    assert refs == ("liva-art-1", "liva-art-2")


@pytest.mark.parametrize("raw", ["liva-art-1,liva-art-1", " , "])
def test_repeated_or_empty_legal_references_are_refused(raw: str) -> None:
    with pytest.raises(RegistryValidationError, match=r"^demo catalogue 'refs' must contain unique legal references$"):
        unique_mapping_legal_refs({"refs": raw}, "refs", subject="demo catalogue")


def test_a_catalogue_fact_resolves_at_the_callers_date_under_its_policy() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_STRIP)

    entries = fact.resolve_entries(_authority(("order", " a,b ")), effective_date=date(2025, 6, 30))

    assert dict(entries) == {"order": "a,b"}


def test_a_catalogue_fact_outside_its_variant_window_is_not_projected() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_STRIP)

    with pytest.raises(RegistryValidationError):
        fact.resolve_entries(_authority(("order", "a")), effective_date=date(2024, 6, 30))


def test_a_scoped_catalogue_fact_resolves_from_the_explicit_authority() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_STRIP)

    with outside_governed_fact_validation():
        entries = fact.resolve_scoped_entries(
            effective_date=date(2025, 6, 30),
            authority=_authority(("order", " a,b ")),
        )

    assert dict(entries) == {"order": "a,b"}


def test_a_scoped_catalogue_fact_resolves_from_the_validation_scope_in_progress() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_PRESERVE)

    with validating_governed_facts(_authority(("order", "a"))):
        entries = fact.resolve_scoped_entries(effective_date=date(2025, 6, 30), authority=None)

    assert dict(entries) == {"order": "a"}


def test_an_explicit_authority_wins_over_the_validation_scope() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_PRESERVE)

    with validating_governed_facts(_authority(("order", "scoped"))):
        entries = fact.resolve_scoped_entries(
            effective_date=date(2025, 6, 30),
            authority=_authority(("order", "explicit")),
        )

    assert dict(entries) == {"order": "explicit"}


def test_a_scoped_catalogue_fact_with_neither_authority_nor_scope_refuses_as_an_invariant() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_PRESERVE)

    with (
        outside_governed_fact_validation(),
        pytest.raises(
            InternalInvariantError, match=r"^demo catalogue requires an explicit generation-pinned governed-fact scope$"
        ),
    ):
        fact.resolve_scoped_entries(effective_date=date(2025, 6, 30), authority=None)


def test_an_absent_effective_date_resolves_at_todays_date_in_madrid() -> None:
    fact = StringMappingFact(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, policy=_PRESERVE)
    inner = _authority(("order", "a"))
    asked: list[date] = []

    class _RecordingSource:
        def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
            asked.append(query.effective_date)
            return inner.resolve_governed_fact(query.model_copy(update={"effective_date": date(2025, 6, 30)}))

        def supported_filing_years(self) -> SupportedFilingYearsCatalogue:
            return _SUPPORT

    before = today_madrid()
    fact.resolve_scoped_entries(effective_date=None, authority=_RecordingSource())
    after = today_madrid()

    assert asked and asked[0] in {before, after}
