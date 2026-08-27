"""Gate: a local path is spelled by what it IS, not by what its author guessed.

This is the half of the operator contract that the declared transport locus was
added to make checkable. Before the declaration existed, a spelling gate had to
infer which parameters carry local paths from their type or their name — and
both fail. ``app ledger classify --file`` and ``app ledger evidence pull-all
--folder`` are both ``str``; one is a file on the operator's disk and the other
is a Drive identifier. Reading the name to decide whether the name is right
proves nothing at all.

So this module reads the declaration. Every assertion below keys on
``TransportLocus``/``TransportShape``/``TransportRole`` and never on a type or a
substring, which is what makes it a property rather than a list of known-good
names.

The spelling table:

===========  ==========  =========  ==================================
locus        shape       role       spelling
===========  ==========  =========  ==================================
local-in     file        primary    ``--file``, or a positional
local-in     file        auxiliary  ``--<role>`` naming what it is
local-in     directory   primary    ``--directory``, or a positional
local-in     root        auxiliary  ``--<name>-root``
local-out    file        primary    ``--output``
local-out    directory   primary    ``--output-root``
remote-handle  --          --       free; a counterparty's identifier
none           --          --       free; outside this contract
===========  ==========  =========  ==================================

An auxiliary is NOT a lesser input. It is a different question, and its name is
the only place the job it does is written down: ``--verify-source``,
``--receipt``, ``--scenario`` and ``--m303-filing-evidence`` all say what they
are for, which ``--file2`` never would. The gate therefore refuses an auxiliary
that takes the PRIMARY's spelling, and otherwise leaves the name to the author.
"""

from __future__ import annotations

import pytest

from ....core.transport_locus import TransportLocus, TransportRole, TransportShape
from .._command_spec import OptionSpec, ParameterSpec
from .._command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: Local-path spellings the operator contract forbids outright, whatever the role.
_FORBIDDEN_LOCAL_SPELLINGS = ("--source", "--path", "--from-file")

#: Exemptions, keyed by the leaf path and the parameter they excuse, each with
#: the reason it is not a defect. A stale entry fails below rather than lingering.
_SPELLING_EXEMPTIONS: dict[tuple[str, str], str] = {
    ("aeat config google register", "client_json"): (
        "Credential enrolment is carved out of the transport grammar: the verb enrols a "
        "credential rather than moving data, and `--client-json` names the specific artefact "
        "Google issues. `--file` would be strictly less informative here."
    ),
}


def _local_parameters() -> list[tuple[str, ParameterSpec]]:
    """Every declared-local parameter in the live graph, with its leaf path."""
    found: list[tuple[str, ParameterSpec]] = []
    for node in COMMAND_GRAPH.nodes():
        if node.spec.kind != "leaf":
            continue
        for parameter in node.spec.parameters:
            if parameter.transport_locus in {TransportLocus.LOCAL_IN, TransportLocus.LOCAL_OUT}:
                found.append((" ".join(node.path), parameter))
    return found


def _declarations(parameter: ParameterSpec) -> tuple[str, ...]:
    if isinstance(parameter, OptionSpec):
        return parameter.declarations
    return ()


def _is_exempt(path: str, parameter: ParameterSpec) -> bool:
    return (path, parameter.name) in _SPELLING_EXEMPTIONS


def test_a_primary_local_input_is_spelled_file_or_positional() -> None:
    """The one input a verb is about takes the one name every operator knows."""
    offenders = [
        f"{path} :: {'/'.join(_declarations(p))}"
        for path, p in _local_parameters()
        if p.transport_locus is TransportLocus.LOCAL_IN
        and p.transport_shape is TransportShape.FILE
        and p.transport_role is TransportRole.PRIMARY
        and _declarations(p)
        and _declarations(p) != ("--file",)
        and not _is_exempt(path, p)
    ]
    assert not offenders, "primary local inputs not spelled `--file`: " + "; ".join(sorted(offenders))


def test_a_primary_local_output_is_spelled_output() -> None:
    offenders = [
        f"{path} :: {'/'.join(_declarations(p))}"
        for path, p in _local_parameters()
        if p.transport_locus is TransportLocus.LOCAL_OUT
        and p.transport_shape is TransportShape.FILE
        and p.transport_role is TransportRole.PRIMARY
        and _declarations(p) != ("--output",)
        and not _is_exempt(path, p)
    ]
    assert not offenders, "primary local outputs not spelled `--output`: " + "; ".join(sorted(offenders))


def test_a_primary_local_output_directory_is_spelled_output_root() -> None:
    offenders = [
        f"{path} :: {'/'.join(_declarations(p))}"
        for path, p in _local_parameters()
        if p.transport_locus is TransportLocus.LOCAL_OUT
        and p.transport_shape is TransportShape.DIRECTORY
        and _declarations(p) != ("--output-root",)
        and not _is_exempt(path, p)
    ]
    assert not offenders, "local output directories not spelled `--output-root`: " + "; ".join(sorted(offenders))


def test_a_resolution_root_is_spelled_with_a_root_suffix() -> None:
    """A root is a base other paths resolve against, and its name says so."""
    offenders = [
        f"{path} :: {'/'.join(_declarations(p))}"
        for path, p in _local_parameters()
        if p.transport_shape is TransportShape.ROOT
        and not all(declaration.endswith("-root") for declaration in _declarations(p))
        and not _is_exempt(path, p)
    ]
    assert not offenders, "resolution roots without a `-root` suffix: " + "; ".join(sorted(offenders))


def test_an_auxiliary_local_input_does_not_take_the_primary_spelling() -> None:
    """An auxiliary's name is the only place its job is written down."""
    offenders = [
        f"{path} :: {'/'.join(_declarations(p))}"
        for path, p in _local_parameters()
        if p.transport_role is TransportRole.AUXILIARY
        and _declarations(p) in {("--file",), ("--output",), ("--directory",)}
        and not _is_exempt(path, p)
    ]
    assert not offenders, "auxiliaries wearing a primary's spelling: " + "; ".join(sorted(offenders))


def test_no_local_parameter_uses_a_forbidden_spelling() -> None:
    """`--source`, `--path` and `--from-file` are refused on a local parameter.

    A parameter declaring locus ``none`` is outside this contract entirely,
    which is what keeps `app ledger evidence pull --source` -- a closed enum
    naming the link's source SYSTEM -- and `--from-year` out of scope.
    """
    offenders = []
    for path, parameter in _local_parameters():
        for declaration in _declarations(parameter):
            forbidden = declaration in _FORBIDDEN_LOCAL_SPELLINGS or declaration.endswith("-path")
            if forbidden and not _is_exempt(path, parameter):
                offenders.append(f"{path} :: {declaration}")
    assert not offenders, "forbidden local-path spellings: " + "; ".join(sorted(offenders))


def test_every_exemption_still_names_a_live_parameter() -> None:
    """A stale exemption is armed: it would silently excuse a future parameter."""
    live = {(path, parameter.name) for path, parameter in _local_parameters()}
    stale = [f"{path} :: {name}" for (path, name) in _SPELLING_EXEMPTIONS if (path, name) not in live]
    assert not stale, "exemptions naming no live local parameter: " + "; ".join(sorted(stale))


def test_the_gate_is_reading_a_populated_graph() -> None:
    """Anti-vacuity: every assertion above greens on an empty local-parameter set."""
    assert len(_local_parameters()) >= 40, f"declared local parameters collapsed to {len(_local_parameters())}"
