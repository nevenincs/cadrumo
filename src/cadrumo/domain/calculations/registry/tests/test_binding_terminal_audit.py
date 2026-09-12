"""Tests for the expectation a resolved binding value is audited against.

What these pin is that the two halves of the terminal-origin contract stay
distinguishable: a binding that authors an expectation is held to its own claim,
and a binding that authors none is held to the one its provider registration
implies rather than to nothing at all. The derived default is read off shipped
registration data, so a registration that changes its permitted origins, its
output shape, or its disposition changes the expectation with it.
"""

from __future__ import annotations

import pytest

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ..binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS, registration_for
from ..binding_terminal_audit import effective_terminal_origins, expected_terminal_origins
from ..binding_terminal_origin import TerminalOriginClass, TerminalOriginExpectation
from ..profile_bindings import ProfileProvider
from ..schema import BindingDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _binding(provider: object, terminal_origins: tuple[TerminalOriginExpectation, ...] = ()) -> BindingDefinition:
    return BindingDefinition(
        id="test.binding",
        provider=provider,
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COPY),
        terminal_origins=terminal_origins,
        legal_refs=("ley-37-1992:art-1",),
        source_refs=("aeat-modelo-303-diseno-registro",),
    )


@pytest.mark.parametrize("kind", sorted(BINDING_PROVIDER_REGISTRATIONS, key=lambda member: member.value))
def test_every_registered_kind_derives_one_expectation_per_permitted_origin(kind: BindingSourceKind) -> None:
    """The default states every class the registration permits, and nothing else."""
    registration = registration_for(kind)

    expectations = expected_terminal_origins(kind)

    assert frozenset(expectation.source_class for expectation in expectations) == (
        registration.permitted_terminal_origins
    )
    assert len(expectations) == len(registration.permitted_terminal_origins)
    assert all(expectation.role.value == "primary" for expectation in expectations)


def test_a_carry_only_scalar_family_rests_on_exactly_one_terminal_node() -> None:
    """``manual_input`` carries one operator answer, so plurality is not admitted."""
    (expectation,) = expected_terminal_origins(BindingSourceKind.MANUAL_INPUT)

    assert expectation.source_class is TerminalOriginClass.OPERATOR_INPUT
    assert expectation.cardinality == "exactly_one"


def test_a_folding_family_admits_many_terminal_nodes_but_never_none() -> None:
    """A ledger fold rests on as many transactions as exist, and emptiness stays a violation."""
    (expectation,) = expected_terminal_origins(BindingSourceKind.LEDGER_IVA_AGGREGATION)

    assert expectation.source_class is TerminalOriginClass.LEDGER_AGGREGATE
    assert expectation.cardinality == "at_least_one"


def test_an_addressable_record_family_demands_an_evidence_fingerprint() -> None:
    """A profile field is one persisted record, so its terminal node must be hashable."""
    (expectation,) = expected_terminal_origins(BindingSourceKind.PROFILE)

    assert expectation.fingerprint == "required"


def test_a_folded_family_does_not_demand_a_fingerprint_it_cannot_produce() -> None:
    """A fold over an already-filed modelo has no single record to fingerprint."""
    (expectation,) = expected_terminal_origins(BindingSourceKind.PREVIOUS_FILING)

    assert expectation.fingerprint == "optional"


def test_a_deferred_or_non_runtime_kind_never_demands_a_fingerprint() -> None:
    """Only a filing-grade family can be held to an evidence demand."""
    for kind in (BindingSourceKind.MANUAL_INPUT, BindingSourceKind.REFUND_OPERATION):
        assert all(expectation.fingerprint == "optional" for expectation in expected_terminal_origins(kind))


def test_effective_expectation_prefers_the_authored_claim() -> None:
    """An authored expectation is the whole answer; the registration default stands down."""
    authored = (
        TerminalOriginExpectation(
            source_class=TerminalOriginClass.PROFILE_FIELD,
            role="primary",
            cardinality="exactly_one",
            fingerprint="optional",
        ),
    )
    binding = _binding(ProfileProvider(profile_key="declarante.nif"), authored)

    assert effective_terminal_origins(binding) == authored
    assert effective_terminal_origins(binding) != expected_terminal_origins(BindingSourceKind.PROFILE)


def test_effective_expectation_falls_back_to_the_registration_default() -> None:
    """A binding authoring nothing is still audited -- silence is not absence of expectation."""
    binding = _binding(ProfileProvider(profile_key="declarante.nif"))

    assert binding.terminal_origins == ()
    assert effective_terminal_origins(binding) == expected_terminal_origins(BindingSourceKind.PROFILE)
