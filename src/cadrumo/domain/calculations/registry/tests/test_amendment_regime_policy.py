"""The declared boundary models own the amendment policy's complete row set."""

from __future__ import annotations

from datetime import date

import pytest

from ..amendment_regime_policy import _policy
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
    policy = _policy(_entries(models))
    assert dict(policy.rectificativa_effective_from) == {modelo: date(2030, 1, 1) for modelo in models}
    assert policy.pre_rectificativa_kinds == frozenset({"prior"})
    assert policy.post_rectificativa_kinds == frozenset({"current"})


@pytest.mark.parametrize("missing", ["date", "source"])
def test_each_declared_model_requires_date_and_evidence(missing: str) -> None:
    entries = _entries(("100", "200"))
    del entries[f"boundary.200.{missing}"]
    with pytest.raises(RegistryValidationError):
        _policy(entries)


def test_missing_entire_declared_row_is_refused() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.date"]
    del entries["boundary.200.source"]
    with pytest.raises(RegistryValidationError, match=r"match boundary\.order"):
        _policy(entries)


@pytest.mark.parametrize("field", ["date", "source", "source_fact", "source_path"])
def test_undeclared_and_dangling_rows_are_refused(field: str) -> None:
    entries = _entries(("100", "200")) | {f"boundary.303.{field}": "2030-01-01"}
    with pytest.raises(RegistryValidationError, match=r"match boundary\.order"):
        _policy(entries)


@pytest.mark.parametrize("declaration", ["100,100", "100,bad", "100,\uff12\uff100"])
def test_duplicate_or_malformed_model_declarations_are_refused(declaration: str) -> None:
    entries = _entries(("100", "200")) | {"boundary.order": declaration}
    with pytest.raises(RegistryValidationError):
        _policy(entries)


@pytest.mark.parametrize("key", ["boundary.bad.date", "boundary.200.unknown", "boundary.200.date.extra"])
def test_malformed_boundary_entries_are_refused(key: str) -> None:
    with pytest.raises(RegistryValidationError):
        _policy(_entries(("100", "200")) | {key: "2030-01-01"})


def test_malformed_date_and_blank_evidence_are_refused() -> None:
    for replacement in ({"boundary.200.date": "not-a-date"}, {"boundary.200.source": " "}):
        with pytest.raises(RegistryValidationError):
            _policy(_entries(("100", "200")) | replacement)


def test_source_fact_can_supply_the_declared_evidence() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.source"]
    entries["boundary.200.source_fact"] = "synthetic-source-fact"
    entries["boundary.200.source_path"] = "facts/synthetic-source.toml"
    assert _policy(entries).rectificativa_effective_from["200"] == date(2030, 1, 1)


def test_source_path_alone_is_not_source_evidence() -> None:
    entries = _entries(("100", "200"))
    del entries["boundary.200.source"]
    entries["boundary.200.source_path"] = "facts/synthetic-source.toml"
    with pytest.raises(RegistryValidationError, match="lacks source evidence"):
        _policy(entries)
