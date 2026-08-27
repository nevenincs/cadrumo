"""Gate: a parameter that carries a filesystem path declares which way it moves.

The spelling convention for local-path options is only checkable if something
says which parameters carry local paths. Nothing else in the graph can answer
that. Type cannot: ``app ledger classify --file`` and ``app ledger evidence
pull-all --folder`` are both ``str``, and one is a file on the operator's disk while the
other is a Drive identifier. Spelling cannot either, because a gate that reads
the option's name to decide whether the option's name is correct proves nothing.

So the locus is declared, and this module is what makes the declaration
mandatory rather than optional. A ``pathlib.Path`` parameter is unambiguous
evidence of a filesystem path, so leaving one at :attr:`TransportLocus.NONE` is
an author who did not fill the field in, and it is refused here.

The converse is deliberately NOT gated. A ``str`` parameter may be a local path
(``evidence add`` takes one positionally), a remote handle (``pull-folder``), or
neither, and no mechanical signal separates those. Declaring them is author
discipline; only the ``Path``-typed subset has a tell this gate can key on.
Claiming to enforce more than that would be the name list this design exists to
avoid.

The companion invariant is arithmetic rather than evidential: a verb has at most
one primary local input and at most one primary local output. A second primary
means two parameters both claim to be the thing the verb is about, and the role
axis has stopped carrying information.
"""

from __future__ import annotations

import pytest

from ....core.transport_locus import TransportLocus, TransportRole
from .._command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _leaves() -> tuple:
    return tuple(node for node in COMMAND_GRAPH.nodes() if node.spec.kind == "leaf")


def _is_path_typed(parameter: object) -> bool:
    value = getattr(parameter, "value", None)
    annotation = getattr(value, "annotation", None)
    return getattr(annotation, "module", None) == "pathlib" and getattr(annotation, "qualname", None) == "Path"


def test_every_path_typed_parameter_declares_a_transport_locus() -> None:
    """A ``Path`` parameter left undeclared is an unfilled field, not a choice."""
    undeclared = [
        f"{' '.join(node.path)} :: {parameter.name}"
        for node in _leaves()
        for parameter in node.spec.parameters
        if _is_path_typed(parameter) and parameter.transport_locus is TransportLocus.NONE
    ]
    assert not undeclared, "Path-typed parameters without a declared transport locus: " + "; ".join(sorted(undeclared))


def test_a_declared_local_parameter_carries_both_a_shape_and_a_role() -> None:
    """Coherence holds across the live graph, not only at construction."""
    incoherent = []
    for node in _leaves():
        for parameter in node.spec.parameters:
            if parameter.transport_locus not in {TransportLocus.LOCAL_IN, TransportLocus.LOCAL_OUT}:
                continue
            if parameter.transport_role is TransportRole.NOT_APPLICABLE:
                incoherent.append(f"{' '.join(node.path)} :: {parameter.name}")
    assert not incoherent, "local parameters without a role: " + "; ".join(sorted(incoherent))


@pytest.mark.parametrize("locus", [TransportLocus.LOCAL_IN, TransportLocus.LOCAL_OUT])
def test_each_verb_declares_at_most_one_primary_per_locus_and_shape(locus: TransportLocus) -> None:
    """Two primaries of the SAME shape mean the role axis carries no information.

    Two primaries of DIFFERENT shapes are legitimate and the tree has one:
    ``app ledger evidence batch`` takes a positional directory and a repeatable
    ``--file``, and its own help says either combines with or replaces the
    other. Neither supports the other, so calling one auxiliary would be a
    false claim about which input the verb is about. The invariant is therefore
    keyed on shape as well as direction.
    """
    offenders = []
    for node in _leaves():
        by_shape: dict[object, list[str]] = {}
        for parameter in node.spec.parameters:
            if parameter.transport_locus is not locus or parameter.transport_role is not TransportRole.PRIMARY:
                continue
            by_shape.setdefault(parameter.transport_shape, []).append(parameter.name)
        for shape, names in by_shape.items():
            if len(names) > 1:
                offenders.append(f"{' '.join(node.path)} :: {shape.value} :: {', '.join(sorted(names))}")
    assert not offenders, f"verbs declaring more than one {locus.value} primary per shape: " + "; ".join(
        sorted(offenders)
    )


def test_a_remote_handle_declares_neither_shape_nor_role() -> None:
    """A counterparty's identifier has no filesystem shape to declare."""
    offenders = [
        f"{' '.join(node.path)} :: {parameter.name}"
        for node in _leaves()
        for parameter in node.spec.parameters
        if parameter.transport_locus is TransportLocus.REMOTE_HANDLE
        and parameter.transport_role is not TransportRole.NOT_APPLICABLE
    ]
    assert not offenders, "remote handles carrying a role: " + "; ".join(sorted(offenders))


def test_the_declaration_is_actually_reaching_the_live_graph() -> None:
    """Anti-vacuity: the gates above pass trivially if nothing is ever declared.

    A refactor that dropped the field, or a graph that stopped materialising
    parameters, would green every assertion in this module while enforcing
    nothing. This floor is deliberately far below the current count so it
    detects a collapse rather than encoding today's total.
    """
    declared = sum(
        1
        for node in _leaves()
        for parameter in node.spec.parameters
        if parameter.transport_locus is not TransportLocus.NONE
    )
    assert declared >= 40, f"transport locus declarations collapsed to {declared}"
