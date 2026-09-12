"""Audit resolved provenance against each binding's terminal-origin expectation.

The declaration side states where a binding's value must ultimately come from
(:func:`~domain.calculations.registry.binding_terminal_audit.effective_terminal_origins`);
the resolvers state where it actually came from
(:attr:`~.source_mesh.CalculationSourceProvenance.terminal_origin`). This module
is the join, and it is the only thing that makes either half falsifiable: a
value that resolves from a derived calculation where a filed casilla was
declared is a complete-looking figure reached by a route nobody authorised, and
nothing else on the resolution reports it.

Every disagreement becomes a ``terminal_origin_mismatch`` diagnostic. Nothing is
coerced, suppressed, or zeroed: the value stays on the resolution exactly as the
resolver produced it, and the operator is told the route disagrees with the
declaration. Only route-owned (``filing_grade``) families are audited -- a
``deferred`` kind is already reported by its own reason, a ``non_runtime`` kind
runs no resolver to produce provenance, and a mesh-only source has no
registration to derive an expectation from.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...domain.calculations.registry.binding_provider_registration import BINDING_PROVIDER_REGISTRATIONS
from ...domain.calculations.registry.binding_terminal_audit import effective_terminal_origins
from ...domain.calculations.registry.binding_terminal_origin import (
    TerminalOriginClass,
    TerminalOriginExpectation,
)
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .source_mesh import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)

__all__ = ["collect_terminal_origin_diagnostics"]


def _resolved_binding_ids(resolution: CalculationSourceResolution) -> frozenset[BindingId]:
    """Return every binding this resolution produced a value for, in any channel."""
    row_binding_ids = {binding_id for binding_id, _ in resolution.row_binding_values}
    return frozenset(
        {
            *resolution.binding_values,
            *resolution.enum_binding_values,
            *resolution.date_binding_values,
            *resolution.boolean_binding_values,
            *row_binding_ids,
        },
    )


def _primaries_by_source(
    provenance: Sequence[CalculationSourceProvenance],
) -> dict[BindingSourceKind, tuple[CalculationSourceProvenance, ...]]:
    """Group primary provenance nodes by the binding source they resolved.

    Provenance is keyed by source family rather than by binding id, because that
    is the only attribution a resolver records: one fold over the ledger stands
    behind every ledger binding of that family on the revision. The audit reads
    it the same way rather than inventing a per-binding attribution the data
    does not carry.
    """
    grouped: dict[BindingSourceKind, list[CalculationSourceProvenance]] = defaultdict(list)
    for row in provenance:
        if row.lineage_role is CalculationSourceLineageRole.PRIMARY:
            grouped[row.resolved_binding_source].append(row)
    return {source: tuple(rows) for source, rows in grouped.items()}


def _diagnostic(binding: BindingDefinition, message: str) -> CalculationSourceDiagnostic:
    return CalculationSourceDiagnostic(
        reason="terminal_origin_mismatch",
        source_kind=binding.source.value,
        binding_source=binding.source,
        binding_id=binding.id,
        message=message,
        legal_refs=binding.legal_refs,
        source_refs=binding.source_refs,
    )


def _class_diagnostics(
    binding: BindingDefinition,
    primaries: Sequence[CalculationSourceProvenance],
    admitted: frozenset[TerminalOriginClass],
) -> list[CalculationSourceDiagnostic]:
    """Report every resolved origin class the binding's expectation does not admit."""
    produced = {row.terminal_origin for row in primaries if row.terminal_origin is not None}
    undeclared = sorted(member.value for member in produced - admitted)
    if not undeclared:
        return []
    permitted = ", ".join(sorted(member.value for member in admitted))
    return [
        _diagnostic(
            binding,
            f"binding {binding.id!r} resolved from terminal origin {', '.join(undeclared)} "
            f"but its declaration admits only {permitted}",
        ),
    ]


def _cardinality_diagnostics(
    binding: BindingDefinition,
    primaries: Sequence[CalculationSourceProvenance],
    expectation: TerminalOriginExpectation,
) -> list[CalculationSourceDiagnostic]:
    """Report a terminal-node count the expectation's cardinality forbids."""
    matching = tuple(row for row in primaries if row.terminal_origin is expectation.source_class)
    if expectation.cardinality == "zero_or_more":
        return []
    if not matching:
        return [
            _diagnostic(
                binding,
                f"binding {binding.id!r} resolved a value with no {expectation.source_class.value!r} "
                f"terminal origin, which its declaration requires ({expectation.cardinality})",
            ),
        ]
    if expectation.cardinality == "exactly_one" and len(matching) > 1:
        return [
            _diagnostic(
                binding,
                f"binding {binding.id!r} resolved from {len(matching)} {expectation.source_class.value!r} "
                "terminal origins, but its declaration rests the value on exactly one",
            ),
        ]
    return []


def _fingerprint_diagnostics(
    binding: BindingDefinition,
    primaries: Sequence[CalculationSourceProvenance],
    expectation: TerminalOriginExpectation,
) -> list[CalculationSourceDiagnostic]:
    """Report terminal nodes missing the evidence fingerprint the expectation demands."""
    if expectation.fingerprint != "required":
        return []
    unfingerprinted = tuple(
        row for row in primaries if row.terminal_origin is expectation.source_class and row.fingerprint is None
    )
    if not unfingerprinted:
        return []
    return [
        _diagnostic(
            binding,
            f"binding {binding.id!r} resolved {len(unfingerprinted)} {expectation.source_class.value!r} "
            "terminal origin(s) with no evidence fingerprint, which its declaration requires",
        ),
    ]


def collect_terminal_origin_diagnostics(
    revision: ModeloRevision,
    resolution: CalculationSourceResolution,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return one diagnostic per way a resolved binding departs from its expectation.

    Audited per binding rather than per provenance node, so a fold over a
    thousand transactions reports once and the channel stays readable.
    """
    primaries = _primaries_by_source(resolution.provenance)
    resolved = _resolved_binding_ids(resolution)
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in revision.bindings:
        if binding.id not in resolved:
            continue
        registration = BINDING_PROVIDER_REGISTRATIONS.get(binding.source)
        if registration is None or registration.disposition != "filing_grade":
            continue
        expectations = effective_terminal_origins(binding)
        if not expectations:
            continue
        binding_primaries = primaries.get(binding.source, ())
        admitted = frozenset(expectation.source_class for expectation in expectations)
        diagnostics.extend(_class_diagnostics(binding, binding_primaries, admitted))
        produced = {row.terminal_origin for row in binding_primaries if row.terminal_origin is not None}
        for expectation in expectations:
            # A declaration admitting several classes is satisfied by any one of
            # them: demanding every admitted class at once would refuse the
            # families whose value legitimately rests on one alternative. The
            # per-class checks therefore run against the class that resolved,
            # and the "none of them resolved" case is reported once, below.
            if len(expectations) > 1 and expectation.source_class not in produced:
                continue
            diagnostics.extend(_cardinality_diagnostics(binding, binding_primaries, expectation))
            diagnostics.extend(_fingerprint_diagnostics(binding, binding_primaries, expectation))
        if len(expectations) > 1 and not produced:
            admitted_text = ", ".join(sorted(member.value for member in admitted))
            diagnostics.append(
                _diagnostic(
                    binding,
                    f"binding {binding.id!r} resolved a value with no terminal origin at all; "
                    f"its declaration requires one of {admitted_text}",
                ),
            )
    return tuple(diagnostics)
