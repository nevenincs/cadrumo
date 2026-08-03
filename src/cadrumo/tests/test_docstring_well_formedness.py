"""A docstring that misdescribes its own contract, where no gate was looking.

The nitpicky ``-n -W`` Sphinx build proves every cross-reference
RESOLVES. It says nothing about whether a docstring is WELL-FORMED, and
the difference is not cosmetic: a duplicated ``Returns:`` and an
``Args:`` entry naming a parameter the signature does not have both
build clean, and both were shipped and found by a human reading a diff.

That matters here more than it would elsewhere. This project
deliberately carries its reasoning in docstrings — why a cast is safe,
why a guard is narrow, which core struct a module hangs off — so the one
surface treated as authoritative had no structural check at all.

Two checks, chosen because they are decidable from the source alone:

* **A repeated section.** Napoleon renders the second one badly and the
  two disagree in practice: the live instance said the function returned
  a tuple in one block and a single diagnostic in the other.
* **An ``Args:`` entry naming a parameter that does not exist.** This is
  the one closest to correctness rather than style — the docstring is
  describing a contract the function does not have. The live instance
  documented an ``extra_events`` argument, in prose describing a
  different function's relabel, that no caller could ever pass.

**What this does NOT catch, stated plainly so the gate is not read as
covering more than it does.** Of eight prose-asserting-a-property-the-
code-lacks defects found in one session, these checks would have caught
two. The other six were semantic — prose describing behaviour that never
existed anywhere, a comment claiming a regex handled a case it did not.
No structural check reaches those; they need a reader. A ``Raises:``
naming an exception the body does not raise is deliberately absent too,
because a raise legitimately comes from a callee, so the obvious
implementation would fail on correct code.

A hard cut with no stored baseline, which the tree affords: the whole
production surface carried exactly two violations, both fixed in the
commit that added this. A ratchet over an unknown backlog is how a gate
gets disabled; a measured backlog of two is how one gets enforced.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from typing import TYPE_CHECKING

import pytest
from sphinx.ext.napoleon.docstring import GoogleDocstring

from ._inventory import production_ast_items, repo_relative

if TYPE_CHECKING:
    from collections.abc import Iterable

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def _napoleon_section_names() -> frozenset[str]:
    """Every section header Napoleon recognises, read from Napoleon.

    Asked of the library rather than hand-listed, so a section this gate
    does not know about cannot quietly become one it ignores. The names
    are built per instance, so an empty docstring is parsed purely to
    obtain them.
    """
    return frozenset(GoogleDocstring("")._sections)


SECTION_NAMES = _napoleon_section_names()

_HEADER = re.compile(r"^(?P<indent>[ \t]*)(?P<name>[A-Za-z][A-Za-z ]*):[ \t]*$")
_ENTRY = re.compile(r"^(?P<indent>[ \t]+)(?P<name>\*{0,2}[A-Za-z_][A-Za-z0-9_]*)[ \t]*(?:\([^)]*\))?[ \t]*:")

#: Sections whose entries name function parameters.
_ARG_SECTIONS = ("Args", "Arguments", "Parameters")


def _section_headers(doc: str) -> list[tuple[int, str]]:
    """Return ``(line index, canonical name)`` for each recognised section header."""
    headers = []
    for index, line in enumerate(doc.splitlines()):
        match = _HEADER.match(line)
        if match and match.group("name").strip().casefold() in SECTION_NAMES:
            headers.append((index, match.group("name").strip()))
    return headers


def _section_body(doc: str, wanted: str) -> list[str]:
    """Return the lines between ``wanted``'s header and the next header."""
    lines = doc.splitlines()
    headers = _section_headers(doc)
    for position, (index, name) in enumerate(headers):
        if name != wanted:
            continue
        end = headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        return lines[index + 1 : end]
    return []


def documented_parameters(doc: str) -> list[str]:
    """Names declared in a docstring's argument section.

    An entry sits at the block's own indent and a wrapped continuation
    line is indented deeper. That constraint is load-bearing rather than
    tidiness: without it every prose line containing a colon ("... is
    handed to: the write door") reads as an entry. Measured on this tree,
    the unconstrained form reported fifteen missing parameters of which
    fourteen were wrapped prose — a detector that would have spent its
    credibility on noise before catching the one real defect.
    """
    for header in _ARG_SECTIONS:
        body = [line for line in _section_body(doc, header) if line.strip()]
        if not body:
            continue
        base = min(len(line) - len(line.lstrip()) for line in body)
        return [
            match.group("name").lstrip("*")
            for line in body
            if len(line) - len(line.lstrip()) == base and (match := _ENTRY.match(line))
        ]
    return []


def repeated_sections(doc: str) -> list[str]:
    """Return every section name appearing more than once in one docstring."""
    counts = Counter(name for _, name in _section_headers(doc))
    return sorted(name for name, total in counts.items() if total > 1)


def signature_parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Every name the function can actually be passed, less the bound receiver."""
    args = node.args
    names = {parameter.arg for parameter in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names - {"self", "cls"}


def _documented_nodes(tree: ast.AST) -> Iterable[tuple[ast.AST, str]]:
    """Yield every node carrying a docstring, paired with it."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        doc = ast.get_docstring(node)
        if doc:
            yield node, doc


def _describe(path_label: str, node: ast.AST) -> str:
    return f"{path_label}:{getattr(node, 'lineno', 1)} {getattr(node, 'name', '<module>')}"


def test_no_docstring_repeats_a_section() -> None:
    """A section written twice renders badly and says two things.

    The instance that prompted this gate declared ``Returns:`` twice,
    once describing a tuple and once a single diagnostic. A reader
    consulting the contract found whichever they read first.
    """
    offenders = [
        f"{_describe(repo_relative(path), node)} -> {names}"
        for path, tree in production_ast_items()
        for node, doc in _documented_nodes(tree)
        if (names := repeated_sections(doc))
    ]
    assert not offenders, "these docstrings declare the same section more than once: " + "; ".join(offenders)


def test_no_docstring_documents_a_parameter_that_does_not_exist() -> None:
    """An argument entry naming nothing in the signature misstates the contract.

    Not a formatting complaint: a caller reading it would pass an
    argument the function rejects, and a reviewer would believe a
    behaviour nothing implements. The instance that prompted this
    documented an ``extra_events`` parameter, in prose lifted from a
    different function, that no caller could pass.
    """
    offenders = []
    for path, tree in production_ast_items():
        for node, doc in _documented_nodes(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            real = signature_parameters(node)
            ghosts = sorted(set(documented_parameters(doc)) - real)
            if ghosts:
                offenders.append(
                    f"{_describe(repo_relative(path), node)} -> documents {ghosts}, accepts {sorted(real)}"
                )
    assert not offenders, (
        "these docstrings document parameters the signature does not have; "
        "remove the entry or restore the parameter: " + "; ".join(offenders)
    )


# ── proof that each check bites, and that neither bites at random ────────


_REPEATED = '''"""Do a thing.

    Returns:
        A tuple.

    Returns:
        A diagnostic.
    """'''

_WELL_FORMED = '''"""Do a thing.

    Args:
        value: The input.

    Returns:
        A tuple.
    """'''

_GHOST_ARG = '''"""Do a thing.

    Args:
        value: The input.
        extra_events: A parameter this function does not take.
    """'''

_WRAPPED_PROSE = '''"""Do a thing.

    Args:
        value: The input, which the caller is expected to have already
            handed to: the write door, before this runs.
    """'''


def _docstring_of(source: str) -> str:
    """Parse a constructed function and hand back its docstring."""
    tree = ast.parse(f"def f(value):\n    {source}\n")
    function = tree.body[0]
    assert isinstance(function, ast.FunctionDef)
    doc = ast.get_docstring(function)
    assert doc is not None
    return doc


def test_the_repeated_section_check_catches_a_doubled_block() -> None:
    """Driven with a constructed docstring, so the tree is never made wrong."""
    assert repeated_sections(_docstring_of(_REPEATED)) == ["Returns"]


def test_the_repeated_section_check_clears_a_well_formed_docstring() -> None:
    """The negative half: a check that flagged either way would prove nothing."""
    assert not repeated_sections(_docstring_of(_WELL_FORMED))


def test_the_parameter_check_catches_an_entry_with_no_parameter() -> None:
    """The ghost-argument direction, against a signature taking only ``value``."""
    documented = documented_parameters(_docstring_of(_GHOST_ARG))
    assert sorted(set(documented) - {"value"}) == ["extra_events"]


def test_the_parameter_check_reads_wrapped_prose_as_prose() -> None:
    """The precision half, and the reason the indent constraint exists.

    A continuation line mentioning a colon is not an entry. Without this
    the check reports a ghost for ordinary wrapped prose, and a gate that
    cries wolf on correct code is one somebody switches off.
    """
    assert documented_parameters(_docstring_of(_WRAPPED_PROSE)) == ["value"]


def test_the_section_vocabulary_really_came_from_napoleon() -> None:
    """A vocabulary that silently emptied would make both checks vacuous.

    Napoleon builds its section table per instance, so this reads a
    private attribute; if that ever stops existing the set would fall to
    empty and every docstring above would pass for want of a header the
    gate recognises.
    """
    assert {"args", "returns", "raises", "attributes"} <= SECTION_NAMES, (
        f"the Napoleon section vocabulary looks wrong: {sorted(SECTION_NAMES)}"
    )
