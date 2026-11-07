"""The declared boundary models own the amendment policy's complete row set."""

from __future__ import annotations

from datetime import date

import pytest

from .....core.amendment_kind_regime import resolve_amendment_kind_regime
from .....core.period import Period
from ..amendment_regime_policy import amendment_regime_policy
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _entries(models: tuple[str, ...]) -> dict[str, str]:
    entries = {
        "procedure.order": "prior,current",
        "procedure.prior.value": "prior",
        "procedure.current.value": "current",
        "regime.pre_order": "prior",
        "regime.post_order": "current",
        "boundary.order": ",".join(models),
    }
    for modelo in models:
        entries[f"boundary.{modelo}.date"] = "2030-01-01"
        entries[f"boundary.{modelo}.source"] = "synthetic independently declared evidence"
    return entries


@pytest.mark.parametrize("models", [("100", "200"), ("100", "200", "303", "390")])
def test_declared_support_can_have_two_or_four_models(models: tuple[str, ...]) -> None:
    policy = amendment_regime_policy(_entries(models))
    assert dict(policy.rectificativa_effective_from) == {modelo: date(2030, 1, 1) for modelo in models}
    assert policy.pre_rectificativa_kinds == frozenset({"prior"})
    assert policy.post_rectificativa_kinds == frozenset({"current"})


@pytest.mark.parametrize("missing", ["date", "source"])
def test_each_declared_model_requires_date_and_evidence(missing: str) -> None:
    entries = _entries(("100", "200"))
    del entries[f"boundary.200.{missing}"]
    with pytest.raises(RegistryValidationError):
        amendment_regime_policy(entries)


def test_missing_entire_declared_row_is_refused() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.date"]
    del entries["boundary.200.source"]
    with pytest.raises(RegistryValidationError, match=r"match boundary\.order"):
        amendment_regime_policy(entries)


@pytest.mark.parametrize("field", ["date", "source", "source_fact", "source_path"])
def test_undeclared_and_dangling_rows_are_refused(field: str) -> None:
    entries = _entries(("100", "200")) | {f"boundary.303.{field}": "2030-01-01"}
    with pytest.raises(RegistryValidationError, match=r"match boundary\.order"):
        amendment_regime_policy(entries)


@pytest.mark.parametrize("declaration", ["100,100", "100,bad", "100,\uff12\uff100"])
def test_duplicate_or_malformed_model_declarations_are_refused(declaration: str) -> None:
    entries = _entries(("100", "200")) | {"boundary.order": declaration}
    with pytest.raises(RegistryValidationError):
        amendment_regime_policy(entries)


@pytest.mark.parametrize("key", ["boundary.bad.date", "boundary.200.unknown", "boundary.200.date.extra"])
def test_malformed_boundary_entries_are_refused(key: str) -> None:
    with pytest.raises(RegistryValidationError):
        amendment_regime_policy(_entries(("100", "200")) | {key: "2030-01-01"})


def test_malformed_date_and_blank_evidence_are_refused() -> None:
    for replacement in ({"boundary.200.date": "not-a-date"}, {"boundary.200.source": " "}):
        with pytest.raises(RegistryValidationError):
            amendment_regime_policy(_entries(("100", "200")) | replacement)


def test_source_fact_can_supply_the_declared_evidence() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.source"]
    entries["boundary.200.source_fact"] = "synthetic-source-fact"
    entries["boundary.200.source_path"] = "facts/synthetic-source.toml"
    assert amendment_regime_policy(entries).rectificativa_effective_from["200"] == date(2030, 1, 1)


def test_source_path_alone_is_not_source_evidence() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.source"]
    entries["boundary.200.source_path"] = "facts/synthetic-source.toml"
    with pytest.raises(RegistryValidationError, match="lacks source evidence"):
        amendment_regime_policy(entries)


def _restricted_entries() -> dict[str, str]:
    return _entries(("100", "200")) | {
        "restriction.order": "130",
        "restriction.130.date": "2020-04-01",
        "restriction.130.kinds": "prior",
        "restriction.130.source": "synthetic-restriction-evidence",
    }


def test_optional_restriction_projects_a_dated_closed_intersection() -> None:
    assert not amendment_regime_policy(_entries(("100", "200"))).kind_restrictions
    restriction = amendment_regime_policy(_restricted_entries()).kind_restrictions["130"]
    assert restriction.effective_from == date(2020, 4, 1)
    assert restriction.permitted_kinds == frozenset({"prior"})


@pytest.mark.parametrize(
    ("year", "code", "expected", "effective"),
    [
        (2030, "08", {"prior", "replacement"}, False),
        (2030, "2T", {"prior", "replacement"}, False),
        (2030, "09", {"current"}, True),
        (2030, "3T", {"current"}, True),
        (2031, "0A", {"current"}, True),
    ],
)
def test_parsed_restriction_intersects_the_selected_regime_at_its_period_end_boundary(
    year: int, code: str, expected: set[str], effective: bool
) -> None:
    entries = _entries(("100",)) | {
        "procedure.order": "prior,current,replacement",
        "procedure.replacement.value": "replacement",
        "regime.pre_order": "prior,replacement",
        "regime.post_order": "current,replacement",
        "boundary.100.date": "2030-09-30",
        "restriction.order": "100",
        "restriction.100.date": "2030-09-30",
        "restriction.100.kinds": "current",
        "restriction.100.source": "synthetic-procedure-guidance",
    }
    policy = amendment_regime_policy(entries)
    regime = resolve_amendment_kind_regime("100", Period.from_year_and_code(year, code), policy=policy)
    assert regime.permitted_kinds == frozenset(expected)
    assert regime.rectificativa_effective is effective
    assert policy.post_rectificativa_kinds == frozenset({"current", "replacement"})


@pytest.mark.parametrize(
    "missing", ["restriction.order", "restriction.130.date", "restriction.130.kinds", "restriction.130.source"]
)
def test_restrictions_require_the_complete_declared_row(missing: str) -> None:
    entries = _restricted_entries()
    del entries[missing]
    with pytest.raises(RegistryValidationError):
        amendment_regime_policy(entries)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("restriction.order", "130,130"),
        ("restriction.order", "130,bad"),
        ("restriction.order", "130,\uff11\uff13\uff11"),
        ("restriction.order", "130,"),
        ("restriction.order", " "),
        ("restriction.130.date", "invalid"),
        ("restriction.130.date", "2020-02-30"),
        ("restriction.130.date", "20200401"),
        ("restriction.130.date", " "),
        ("restriction.130.kinds", "unknown"),
        ("restriction.130.kinds", "prior,prior"),
        ("restriction.130.kinds", "prior,,current"),
        ("restriction.130.kinds", " "),
        ("restriction.130.source", " "),
        ("restriction.131.source", "undeclared-row"),
        ("restriction.130.unknown", "unknown-field"),
        ("restriction.130.date.extra", "2020-04-01"),
    ],
)
def test_malformed_restriction_fields_fail_closed(key: str, value: str) -> None:
    with pytest.raises(RegistryValidationError):
        amendment_regime_policy(_restricted_entries() | {key: value})
