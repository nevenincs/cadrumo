"""Gate: a verb that demonstrably moves data does not wear a retired token.

The operator contract names three verb categories. A TRANSPORT verb moves data
and takes one of four tokens — ``pull``/``push`` for a remote counterparty,
``import``/``export`` for the local filesystem. A COMPUTATION verb names the
computation. A CREATING verb names the record it creates. In the latter two the
path or handle is declared on the parameters and never claims the verb.

Only part of that is mechanically decidable, and this module is deliberately
scoped to the part that is. Nothing on a leaf says "this verb's PRIMARY PURPOSE
is transport", and no signal separates ``app ledger evidence add`` (creates an
evidence record from a PDF) from a hypothetical ``evidence import`` that merely
moves one. Asking a gate to make that call would put it back in the business of
guessing intent, which is what the declared locus was introduced to stop.

What IS decidable: a leaf whose parameters declare a transport locus is
handling data movement in some capacity, and such a leaf must not be named with
a token the contract retired. ``aeat config google probe`` carries a retired token and passes, correctly: it
declares no locus, because a connectivity check moves no data. That is the
qualifier doing its work rather than a hole in the gate.

What the qualifier CANNOT see is a retired token on a locus-free verb that is
nonetheless a synonym split. ``config google folder get`` sat beside ``config
google credential-source view`` — same family, same shape, two read verbs — and
this gate passed it on both counts. It was found by reading the leaf-token
census, not by a gate, and the residue below is why.

The residue — whether a given creating or computation verb should really have
been a transport verb — is author judgement, and the contract's worked examples
are where it is argued, not here.
"""

from __future__ import annotations

import pytest

from ....core.transport_locus import TransportLocus
from .._command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Tokens the operator contract retired for data movement. ``file`` is included
#: because it keeps only its domain meaning, the act of filing a declaration.
_RETIRED_TRANSPORT_TOKENS = frozenset(
    {
        "capture",
        "download",
        "fetch",
        "file",
        "get",
        "mirror",
        "probe",
        "refresh",
        "send",
        "sync",
        "upload",
    }
)

#: The four tokens a transport verb may take.
_TRANSPORT_TOKENS = frozenset({"export", "import", "pull", "push"})


def _leaves() -> tuple:
    return tuple(node for node in COMMAND_GRAPH.nodes() if node.spec.kind == "leaf")


def _declares_a_locus(node: object) -> bool:
    return any(parameter.transport_locus is not TransportLocus.NONE for parameter in node.spec.parameters)


def test_no_data_moving_verb_wears_a_retired_token() -> None:
    """A leaf that declares a locus must not be named with a retired token."""
    offenders = []
    for node in _leaves():
        token = node.path[-1]
        head = token.split("-")[0]
        if not _declares_a_locus(node):
            continue
        if token in _RETIRED_TRANSPORT_TOKENS or head in _RETIRED_TRANSPORT_TOKENS:
            offenders.append(" ".join(node.path))
    assert not offenders, "data-moving verbs wearing a retired token: " + "; ".join(sorted(offenders))


def test_the_file_token_keeps_only_its_domain_meaning() -> None:
    """``file`` names the act of filing a declaration and nothing else.

    This is asserted separately from the rule above because it is the one
    retired token with a surviving legitimate use, and that use must stay
    singular: two leaves named ``file`` would mean the collision returned.
    """
    named_file = [" ".join(node.path) for node in _leaves() if node.path[-1] == "file"]
    assert named_file == ["aeat app modelo work file"], f"unexpected `file` leaves: {sorted(named_file)}"


def test_a_transport_compound_suffixes_a_subject_or_all() -> None:
    """``<token>-<locus>`` is refused because locus belongs in an option.

    ``pull-all`` is cardinality and ``pull-sources``/``pull-evidence``/
    ``pull-history`` name subjects. ``pull-folder`` named a LOCUS, which is why
    it became ``evidence pull-all --folder``.
    """
    offenders = [
        " ".join(node.path)
        for node in _leaves()
        if "-" in node.path[-1]
        and node.path[-1].split("-")[0] in _TRANSPORT_TOKENS
        and node.path[-1].split("-", 1)[1] in {"folder", "file", "directory", "path", "root", "local", "remote"}
    ]
    assert not offenders, "transport compounds suffixed with a locus: " + "; ".join(sorted(offenders))


def test_the_gate_is_reading_a_populated_graph() -> None:
    """Anti-vacuity: every assertion above greens on an empty or locus-free graph."""
    with_locus = sum(1 for node in _leaves() if _declares_a_locus(node))
    assert len(_leaves()) >= 200, f"leaves collapsed to {len(_leaves())}"
    assert with_locus >= 25, f"leaves declaring a transport locus collapsed to {with_locus}"
