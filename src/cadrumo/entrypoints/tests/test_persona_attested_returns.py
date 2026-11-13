"""The replay attests, on its own, only the returns a persona states a prior value for that nothing else calculates.

A return of the history and a return a stated value names are calculated
elsewhere, and attest their prior values after that calculation; only another
attested return is created and attested by the history replay itself. Real
catalogue persona under the bundled registry's year envelope.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from functools import cache
from uuid import uuid4

import pytest
from pydantic import BaseModel

from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.binding_targets import revision_bindings_by_id
from ...tests.personas import (
    AttestedPriorValue,
    PriorValueSource,
    YearEnvelope,
    YearToken,
    read_persona,
)
from .persona_materialisation import attested_returns_to_replay, year_envelope
from .persona_prior_values import PriorValueAttestationError, attest_return_prior_values, check_prior_value_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@cache
def _envelope() -> YearEnvelope:
    with bundled_indexed_authority().operation() as operation:
        return year_envelope(operation)


def _instalment_base(period: str) -> AttestedPriorValue:
    return AttestedPriorValue(
        modelo="202",
        period=period,
        year=YearToken.parse("horizon", where="test"),
        binding="instalment-base",
        value=Decimal("0.00"),
        sources=(PriorValueSource(modelo="200", year=YearToken.parse("horizon-2", where="test"), period="0A"),),
        derivation="test",
        legal_ref=("ley-27-2014:art-40",),
    )


def test_an_attested_return_nothing_calculates_is_replayed_once_per_return() -> None:
    envelope = _envelope()
    persona = read_persona("sociedad-limitada", envelope=envelope)
    widened = dataclasses.replace(
        persona,
        attested_prior_values=(
            *persona.attested_prior_values,
            _instalment_base("1P"),
            dataclasses.replace(_instalment_base("1P"), binding="another-binding"),
            _instalment_base("2P"),
        ),
    )
    assert attested_returns_to_replay(widened, envelope) == (
        ("202", envelope.horizon, "1P"),
        ("202", envelope.horizon, "2P"),
    )


def test_a_return_with_no_attested_entry_submits_nothing() -> None:
    def settle(definition_id: str, payload: BaseModel, *, subject: str | None = None) -> BaseModel | None:
        raise AssertionError(f"{definition_id} was submitted")

    attested = attest_return_prior_values(
        (_instalment_base("1P"),),
        envelope=_envelope(),
        profile_id=uuid4(),
        work_unit_id="work-unit",
        modelo="202",
        filing_year=_envelope().horizon,
        period="2P",
        settle=settle,
    )
    assert (attested.applied, attested.unoffered) == (None, ())


def test_a_binding_the_returns_edition_does_not_declare_is_refused_by_name() -> None:
    envelope = _envelope()
    (entry, *_) = read_persona("sociedad-limitada", envelope=envelope).attested_prior_values
    stale = dataclasses.replace(entry, binding="no-such-binding-in-any-edition")
    with bundled_indexed_authority().operation() as operation:
        check_prior_value_bindings((entry,), envelope, operation)
        with pytest.raises(PriorValueAttestationError) as refused:
            check_prior_value_bindings((entry, stale), envelope, operation)
    message = str(refused.value)
    assert "no-such-binding-in-any-edition" in message
    assert f"Modelo {entry.modelo}" in message


def _incn_entry(envelope: YearEnvelope) -> AttestedPriorValue:
    (entry, *_) = (
        item
        for item in read_persona("sociedad-limitada", envelope=envelope).attested_prior_values
        if item.binding == "modelo-200-incn-periodo-impositivo-anterior"
    )
    return entry


def _editions_declaring(
    operation: PinnedAuthorityOperation, envelope: YearEnvelope, entry: AttestedPriorValue
) -> dict[int, bool]:
    """Per supported filing year, whether the entry's return edition declares its binding."""
    return {
        year: entry.binding
        in revision_bindings_by_id(operation.revision_for_context(entry.modelo, filing_year=year, period=entry.period))
        for year in range(envelope.floor, envelope.horizon + 1)
    }


def _in_year(entry: AttestedPriorValue, envelope: YearEnvelope, year: int) -> AttestedPriorValue:
    return dataclasses.replace(entry, year=YearToken(anchor="horizon", offset=year - envelope.horizon))


def test_a_where_declared_entry_is_never_refused_and_a_strict_one_only_where_the_edition_lacks_the_binding() -> None:
    envelope = _envelope()
    entry = _incn_entry(envelope)
    strict = dataclasses.replace(entry, where_declared=False)
    assert entry.where_declared
    with bundled_indexed_authority().operation() as operation:
        declaring = _editions_declaring(operation, envelope, entry)
        undeclared = [year for year, declared in declaring.items() if not declared]
        declared = [year for year, declared in declaring.items() if declared]
        assert undeclared
        assert declared
        for year in (*undeclared, *declared):
            check_prior_value_bindings((_in_year(entry, envelope, year),), envelope, operation)
        for year in declared:
            check_prior_value_bindings((_in_year(strict, envelope, year),), envelope, operation)
        for year in undeclared:
            with pytest.raises(PriorValueAttestationError, match="is not a binding of edition"):
                check_prior_value_bindings((_in_year(strict, envelope, year),), envelope, operation)


def test_sociedad_limitada_passes_the_binding_check_at_a_horizon_whose_prior_year_lacks_the_incn_binding() -> None:
    envelope = _envelope()
    entry = _incn_entry(envelope)
    with bundled_indexed_authority().operation() as operation:
        declaring = _editions_declaring(operation, envelope, entry)
        lacking = max(year for year, declared in declaring.items() if not declared)
        lowered = dataclasses.replace(envelope, horizon=lacking + 1)
        persona = read_persona("sociedad-limitada", envelope=lowered, omit_below_floor=True)
        assert any(item.binding == entry.binding for item in persona.attested_prior_values)
        check_prior_value_bindings(persona.attested_prior_values, lowered, operation)
