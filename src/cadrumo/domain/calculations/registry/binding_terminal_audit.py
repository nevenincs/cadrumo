"""The effective terminal-origin expectation of one binding.

:mod:`.binding_terminal_origin` defines what an expectation says;
:mod:`.binding_provider_registration` declares which terminal origin classes a
provider kind is able to rest on at all. Neither on its own answers the question
a runtime audit has to ask: for THIS binding, what should the resolved
provenance graph look like?

A binding may author :attr:`~.schema.BindingDefinition.terminal_origins`
explicitly, and when it does that authored claim is the whole answer -- it is
narrower than the registration by construction, because the compiler already
refuses an authored class the registration cannot produce. Where a binding
authors none (the ordinary case across the corpus), the expectation falls back
to the one its registration implies, so that "the author wrote nothing" and "no
expectation exists" stay different statements. A derived default is still
falsifiable: it is read off declared registration data, not assumed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....core.aggregation import BindingAggregationOp, BindingSourceKind, CalculationSourceLineageRole
from .binding_provider_registration import BindingProviderRegistration, registration_for
from .binding_terminal_origin import (
    TerminalOriginCardinality,
    TerminalOriginExpectation,
    TerminalOriginFingerprint,
)

if TYPE_CHECKING:
    from .schema import BindingDefinition

__all__ = [
    "effective_terminal_origins",
    "expected_terminal_origins",
]

_CARRY_ONLY_OPS = frozenset({BindingAggregationOp.COPY})
"""The operation set of a family that carries ONE terminal fact into a value."""

_FINGERPRINTED_ORIGIN_KINDS = frozenset(
    {
        BindingSourceKind.PROFILE,
        BindingSourceKind.ATRIBUCION_MEMBER,
        BindingSourceKind.FOREIGN_ASSET,
        BindingSourceKind.INVENTORY,
        BindingSourceKind.PAYABLE_INVOICE,
        BindingSourceKind.COLLECTIBLE_INVOICE,
        BindingSourceKind.M347_THIRD_PARTY_OPERATION,
    },
)
"""Filing-grade families whose terminal fact is an individually addressable record.

A fingerprint is demanded where the terminal fact is ONE persisted record that
can be hashed on its own -- a profile field, an invoice, a detail row. A fold
over classified ledger transactions or over an already-filed modelo's casillas
has no single record to fingerprint, so demanding one there would produce a
standing advisory that no resolver could ever satisfy, which trains an operator
to stop reading the channel. Absence of a demand is not permission to drop a
fingerprint that IS produced; it is the statement that this family's terminal
fact is a fold.
"""


def _default_cardinality(registration: BindingProviderRegistration) -> TerminalOriginCardinality:
    """Return how many terminal nodes one value of this kind must rest on.

    ``exactly_one`` is claimed only for a scalar family that carries a single
    fact -- its permitted operations are the carry alone. A family permitted to
    fold (``sum``, ``count_distinct``) or to emit rows rests on as many terminal
    nodes as the taxpayer has facts, so its floor is ``at_least_one``: emptiness
    stays a violation, plurality does not.
    """
    if registration.output == "scalar" and registration.permitted_aggregation_ops <= _CARRY_ONLY_OPS:
        return "exactly_one"
    return "at_least_one"


def _default_fingerprint(registration: BindingProviderRegistration) -> TerminalOriginFingerprint:
    """Return whether each terminal node of this kind must carry a fingerprint."""
    if registration.disposition == "filing_grade" and registration.kind in _FINGERPRINTED_ORIGIN_KINDS:
        return "required"
    return "optional"


def expected_terminal_origins(kind: BindingSourceKind) -> tuple[TerminalOriginExpectation, ...]:
    """Return the expectation a binding of ``kind`` carries when it authors none.

    One expectation per terminal origin class the registration permits, in
    stable class order, each in the primary lineage role: the provenance node a
    resolver names as the terminal fact behind the value is primary by
    definition, and a contributor node hangs off one of those.
    """
    registration = registration_for(kind)
    cardinality = _default_cardinality(registration)
    fingerprint = _default_fingerprint(registration)
    return tuple(
        TerminalOriginExpectation(
            source_class=source_class,
            role=CalculationSourceLineageRole.PRIMARY,
            cardinality=cardinality,
            fingerprint=fingerprint,
        )
        for source_class in sorted(registration.permitted_terminal_origins, key=lambda member: member.value)
    )


def effective_terminal_origins(binding: BindingDefinition) -> tuple[TerminalOriginExpectation, ...]:
    """Return the expectation a resolved value of ``binding`` is audited against."""
    if binding.terminal_origins:
        return binding.terminal_origins
    return expected_terminal_origins(binding.source)
